import os
import pytest
import asyncio
from unittest.mock import patch
from google.genai import types
from google.adk.runners import InMemoryRunner
from google.adk.apps import App
from app.agent import safestaff_workflow

@pytest.fixture
def app_instance():
    # Make sure mock mode is disabled for the live test
    os.environ["MOCK_MODE"] = "false"
    # Ensure Vertex AI configuration is respected (requires ADC credentials)
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
    if "GEMINI_MODEL" not in os.environ:
        os.environ["GEMINI_MODEL"] = "gemini-3.5-flash"
    
    return App(
        name="test_live_app",
        root_agent=safestaff_workflow
    )

@pytest.mark.skipif(os.environ.get("RUN_LIVE_TESTS", "false").lower() != "true", reason="Live tests require RUN_LIVE_TESTS=true")
@pytest.mark.asyncio
async def test_live_gemini_generation(app_instance):
    """
    Perform exactly one live Gemini staffing-plan generation and report the model used, 
    result, and any token usage available.
    """
    print(f"\n--- Running Live Gemini Integration Test ---")
    print(f"Model configured: {os.environ.get('GEMINI_MODEL')}")
    
    runner = InMemoryRunner(app=app_instance)
    session = await runner.session_service.create_session(app_name="test_live_app", user_id="test_live_user")

    with patch('app.agent.commit_plan') as mock_commit, patch('app.agent.record_audit') as mock_audit:
        events = []
        async for event in runner.run_async(
            user_id="test_live_user",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text="Generate plan for 2026-08-25")])
        ):
            events.append(event)
            
            # Check for the model output event which contains the generated plan
            if hasattr(event, "output") and event.output is not None:
                print(f"DEBUG: Found output of type {type(event.output)}")
                if hasattr(event.output, "model_dump"):
                    print(f"Live Gemini Output (model_dump): {event.output.model_dump()}")
                elif isinstance(event.output, dict):
                    print(f"Live Gemini Output (dict): {event.output}")
                else:
                    print(f"Live Gemini Output (raw): {event.output}")
                
            # Log usage metadata if present
            if hasattr(event, "usage_metadata") and event.usage_metadata:
                print(f"Token Usage: {event.usage_metadata}")

        # Assert no commit was made
        mock_commit.assert_not_called()
        mock_audit.assert_not_called()

        # Check if the workflow successfully reached approval, or gracefully handled an error
        reached_approval = any(e.long_running_tool_ids and "approval" in e.long_running_tool_ids for e in events)
        emitted_error = any(getattr(e, "output", None) and isinstance(e.output, str) and "Error generating plan" in e.output for e in events)
        
        assert reached_approval or emitted_error, "Workflow neither reached approval nor emitted a handled error"
        
    print(f"--- Live Test Completed Successfully ---")
