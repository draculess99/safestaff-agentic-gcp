import streamlit as st
import asyncio
from google.adk.runners import InMemoryRunner
from google.genai import types

# Note: In a production app, the ADK app would likely run as a separate service.
# For this minimal hackathon setup, we import it directly.
from app import app as adk_app

st.set_page_config(page_title="SafeStaff Agentic", layout="wide")

st.title("SafeStaff Agentic GCP")
st.markdown("Healthcare staffing forecasting and approval workflow.")

# Initialize session state for runner and session ID
if 'runner' not in st.session_state:
    st.session_state.runner = InMemoryRunner(app=adk_app)
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'workflow_state' not in st.session_state:
    st.session_state.workflow_state = "idle"
if 'current_plan' not in st.session_state:
    st.session_state.current_plan = None
if 'interrupt_id' not in st.session_state:
    st.session_state.interrupt_id = None

async def run_workflow(message: str = None, interrupt_id: str = None, resume_input: str = None):
    kwargs = {
        "user_id": "demo_user",
        "app_name": adk_app.name,
    }
    
    if st.session_state.session_id:
        kwargs["session_id"] = st.session_state.session_id
    
    if interrupt_id and resume_input:
        kwargs["new_message"] = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=interrupt_id,
                        name="request_input",
                        response={"result": resume_input}
                    )
                )
            ]
        )
    else:
        kwargs["new_message"] = types.Content(role="user", parts=[types.Part.from_text(text=message or "Generate staffing plan for next week")])

    result_text = ""
    is_paused = False
    
    # In a real app with Firestore, we'd use a persistent session.
    # We create a session if it doesn't exist
    if not st.session_state.session_id:
        session = await st.session_state.runner.session_service.create_session(
            app_name=kwargs["app_name"],
            user_id=kwargs["user_id"]
        )
        st.session_state.session_id = session.id
        kwargs["session_id"] = session.id

    # Filter kwargs for run_async
    run_kwargs = {k: v for k, v in kwargs.items() if k in ["user_id", "session_id", "new_message"]}

    async for event in st.session_state.runner.run_async(**run_kwargs):
        if hasattr(event, "interrupt_id"):
            st.session_state.interrupt_id = event.interrupt_id
            st.session_state.workflow_state = "awaiting_approval"
            is_paused = True
            st.warning(event.message)
            break
        elif event.output is not None:
            # Output from final nodes or LLM
            if hasattr(event.output, "model_dump"):
                plan_dict = event.output.model_dump()
                if "shift_date" in plan_dict:
                    st.session_state.current_plan = plan_dict
            elif isinstance(event.output, dict) and "shift_date" in event.output:
                st.session_state.current_plan = event.output
            elif isinstance(event.output, str):
                result_text = event.output
                
    if not is_paused:
        st.session_state.workflow_state = "completed"
        if result_text:
            st.success(result_text)

# UI Layout
col1, col2 = st.columns(2)

with col1:
    st.subheader("Generate Staffing Plan")
    shift_date = st.date_input("Select Shift Date")
    if st.button("Run Forecast & Generate Plan", disabled=st.session_state.workflow_state == "awaiting_approval"):
        with st.spinner("Generating plan..."):
            st.session_state.session_id = None
            asyncio.run(run_workflow(message=f"Generate staffing plan for {shift_date}"))
            st.rerun()

with col2:
    st.subheader("Human-in-the-Loop Approval")
    
    if st.session_state.workflow_state == "awaiting_approval":
        st.info("A plan requires your review before committing to Firestore.")
        if st.session_state.current_plan:
            st.json(st.session_state.current_plan)
        
        col_app, col_rej = st.columns(2)
        with col_app:
            if st.button("Approve Plan", type="primary"):
                with st.spinner("Committing..."):
                    asyncio.run(run_workflow(interrupt_id=st.session_state.interrupt_id, resume_input="approve"))
                    st.rerun()
        with col_rej:
            if st.button("Reject Plan"):
                with st.spinner("Rejecting..."):
                    asyncio.run(run_workflow(interrupt_id=st.session_state.interrupt_id, resume_input="reject"))
                    st.rerun()
    elif st.session_state.workflow_state == "completed":
        st.success("Workflow finished.")
    else:
        st.write("No pending approvals.")
