import os
from pydantic import BaseModel
from google.adk.workflow import Workflow, node
from google.adk.events.event import Event
from google.adk.agents.context import Context
from google.adk.agents import LlmAgent
from google.adk.events.request_input import RequestInput
from google.genai import types
from .tools import generate_forecast, apply_healthcare_rules, commit_plan, record_audit

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

# 3. Define the LLM Agent for generation
if os.getenv("MOCK_MODE", "").lower() == "true":
    @node(name="generator")
    def plan_generator(ctx: Context, node_input: str) -> StaffingPlan:
        # Mock mode deterministic plan
        return StaffingPlan(
            shift_date="2026-08-25",
            recommended_staff=10,
            rationale="Generated deterministically in mock mode.",
            compliance_notes=["Compliant with mock rules"]
        )
else:
    plan_generator = LlmAgent(
        name="generator",
        model="gemini-3.5-flash",
        instruction="""
        You are an expert healthcare staffing planner. Based on the forecasted demand and healthcare rules provided,
        generate a compliant and optimal staffing plan.
        """,
        output_schema=StaffingPlan,
    )

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
    # A rejected recommendation is not committed
    return f"Plan for {node_input.shift_date} was rejected. No changes committed."

# 6. Assemble Workflow
safestaff_workflow = Workflow(
    name="safestaff_workflow",
    edges=[
        ('START', prepare_data),
        (prepare_data, plan_generator),
        (plan_generator, human_approval),
        (human_approval, {"approved": execute_commit, "rejected": execute_reject}),
    ]
)
