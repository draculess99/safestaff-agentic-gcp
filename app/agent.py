import os
import re
from dotenv import load_dotenv

# Ensure .env is loaded before any Gemini model or Google configuration is constructed.
load_dotenv()
from pydantic import BaseModel
from google.adk.workflow import Workflow, node
from google.adk.events.event import Event
from google.adk.agents.context import Context
from google.adk.agents import LlmAgent
from google.adk.events.request_input import RequestInput
from google.genai import types
from .tools import generate_forecast, apply_healthcare_rules, commit_plan, record_audit
from google.adk.models import Gemini

# 1. Define schemas
class StaffingPlan(BaseModel):
    shift_date: str
    recommended_staff: int
    rationale: str
    compliance_notes: list[str]

# 2. Intake node to prepare data and state
@node
def prepare_data(ctx: Context, node_input: types.Content) -> str:
    # Extract text from the start node input
    text_input = node_input.parts[0].text if node_input.parts else ""
    
    # Generate forecast and rules
    forecast = generate_forecast({"scenario": text_input})
    rules = apply_healthcare_rules(forecast["predicted_demand"])
    
    # Keep track in memory for the audit record
    ctx.state["input_scenario"] = text_input
    ctx.state["forecast"] = forecast
    
    # Pass formatted prompt to LLM
    return f"User Request: {text_input}\nForecasted Demand: {forecast['predicted_demand']}\nConfidence: {forecast['confidence']}\nRules: {rules}"

_real_generator = LlmAgent(
    name="_real_generator",
    model=Gemini(model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash")),
    instruction="""
    You are an expert healthcare staffing planner. Based on the forecasted demand and healthcare rules provided,
    generate a compliant and optimal staffing plan.
    """,
    output_schema=StaffingPlan,
)

def _sanitize_exception_chain(e: Exception) -> list[dict]:
    chain = []
    current = e
    visited = set()
    while current and id(current) not in visited:
        visited.add(id(current))
        
        cls_name = type(current).__name__
        msg = str(current)
        
        # Redact credentials and keys
        msg = re.sub(r'(?i)(bearer\s+)[^\s"\'}]+', r'\1[REDACTED]', msg)
        msg = re.sub(r'(?i)(authorization:?\s*)[^\s"\'}]+', r'\1[REDACTED]', msg)
        msg = re.sub(r'AIza[0-9A-Za-z-_]{35}', '[REDACTED_API_KEY]', msg)
        msg = re.sub(r'AQ\.[0-9A-Za-z-_]+', '[REDACTED_API_KEY]', msg)
        
        status_code = getattr(current, "status_code", getattr(current, "code", None))
        
        info = {"class": cls_name, "message": msg}
        if status_code is not None:
            info["status_code"] = status_code
            
        chain.append(info)
        
        if getattr(current, "__cause__", None):
            current = current.__cause__
        else:
            current = getattr(current, "__context__", None)
            
    return chain

@node(name="generator", rerun_on_resume=True)
async def plan_generator(ctx: Context, node_input: str):
    if os.getenv("MOCK_MODE", "").lower() == "true":
        input_scenario = ctx.state.get("input_scenario", "")
        match = re.search(r'\d{4}-\d{2}-\d{2}', input_scenario)
        shift_date = match.group(0) if match else "2026-08-25"
        
        # Mock mode deterministic plan
        plan = StaffingPlan(
            shift_date=shift_date,
            recommended_staff=10,
            rationale="Generated deterministically in mock mode.",
            compliance_notes=["Compliant with mock rules"]
        )
        yield Event(output=plan, route="success")
        return

    try:
        result = await ctx.run_node(_real_generator, node_input=node_input)
        yield Event(output=result, route="success")
    except Exception as e:
        if os.getenv("DIAGNOSTIC_MODE", "").lower() == "true":
            diagnostics = _sanitize_exception_chain(e)
            print(f"DIAGNOSTIC_MODE Exception Chain:\n{diagnostics}")
            
        yield Event(output="Error generating plan: Gemini output was malformed or failed validation.", route="error")

# 4. Define the HITL node for human approval
@node(rerun_on_resume=True)
async def human_approval(ctx: Context, node_input: StaffingPlan):
    # Store Gemini's recommendation in state for the audit record
    ctx.state["recommendation"] = node_input.model_dump()
    
    # Yield a RequestInput to pause the workflow for human approval
    if not ctx.resume_inputs or "approval" not in ctx.resume_inputs:
        yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=f"Recommendation: {node_input.model_dump()}")]))
        yield RequestInput(
            interrupt_id="approval", 
            message=f"Review required for staffing plan on {node_input.shift_date}. Recommend {node_input.recommended_staff} staff. Reply with 'approve' or 'reject'."
        )
        return
        
    decision_input = ctx.resume_inputs["approval"]
    if isinstance(decision_input, dict) and "result" in decision_input:
        decision = decision_input["result"].lower()
    else:
        decision = str(decision_input).lower()
        
    ctx.state["human_decision"] = decision
    ctx.state["approval_status"] = "Approved" if decision == "approve" else "Rejected"
    
    # Route based on explicit human decision (never simulated by LLM)
    if decision == "approve":
        yield Event(output=node_input, route="approved")
    else:
        yield Event(output=node_input, route="rejected")

# 5. Define commit node that uses the custom ADK tool
@node
def execute_commit(ctx: Context, node_input: StaffingPlan) -> str:
    approval_status = ctx.state.get("approval_status", "")
    human_decision = ctx.state.get("human_decision", "")
    
    if approval_status != "Approved" or human_decision != "approve":
        return "Commit rejected: unauthorized approval status."
        
    # Use the custom commit_plan tool to write to Firestore
    result = commit_plan(
        workflow_id=ctx.session.id,
        input_scenario=ctx.state.get("input_scenario", ""),
        forecast=ctx.state.get("forecast", {}),
        recommendation=ctx.state.get("recommendation", {}),
        approval_status=approval_status,
        human_decision=human_decision,
        staffing_plan=node_input.model_dump()
    )
    if os.getenv("MOCK_MODE", "").lower() == "true" and "Failed" not in result:
        return f"Plan for {node_input.shift_date} was approved and successfully committed to the local mock audit."
    return result

@node
def execute_reject(ctx: Context, node_input: StaffingPlan) -> str:
    record_audit(
        workflow_id=ctx.session.id,
        input_scenario=ctx.state.get("input_scenario", ""),
        forecast=ctx.state.get("forecast", {}),
        recommendation=ctx.state.get("recommendation", {}),
        approval_status=ctx.state.get("approval_status", ""),
        human_decision=ctx.state.get("human_decision", ""),
        staffing_plan=node_input.model_dump()
    )
    if os.getenv("MOCK_MODE", "").lower() == "true":
        return f"Plan for {node_input.shift_date} was rejected. No staffing changes were committed."
    # A rejected recommendation is not committed
    return f"Plan for {node_input.shift_date} was rejected. No changes committed."

# 6. Assemble Workflow
safestaff_workflow = Workflow(
    name="safestaff_workflow",
    edges=[
        ('START', prepare_data),
        (prepare_data, plan_generator),
        (plan_generator, {"success": human_approval}),
        (human_approval, {"approved": execute_commit, "rejected": execute_reject}),
    ]
)
