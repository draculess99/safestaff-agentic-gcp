import os
os.environ["MOCK_MODE"] = "true"

import pytest
from unittest.mock import patch
from google.adk.runners import InMemoryRunner
from google.adk.apps import App
from google.genai import types
from google.adk.events.event import Event

from app.agent import safestaff_workflow, StaffingPlan

@pytest.fixture
def app_instance():
    return App(name="test_app", root_agent=safestaff_workflow)

@pytest.mark.asyncio
async def test_approved_recommendation_is_committed(app_instance):
    """Test 1: An approved recommendation is committed."""
    runner = InMemoryRunner(app=app_instance)
    session = await runner.session_service.create_session(app_name="test_app", user_id="test_user")
    
    with patch('app.agent.commit_plan') as mock_commit:
        mock_commit.return_value = "Successfully committed plan to Mock JSON (ID: mock)"
        
        # Run until pause for approval
        events = []
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text="Generate plan for 2026-08-25")])
        ):
            events.append(event)
            
        assert any(e.long_running_tool_ids and "approval" in e.long_running_tool_ids for e in events)
        
        # Resume with 'approve'
        resume_events = []
        resume_message = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id="approval",
                        name="request_input",
                        response={"result": "approve"}
                    )
                )
            ]
        )
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session.id,
            new_message=resume_message
        ):
            resume_events.append(event)
            
        # Verify commit_plan was called and workflow succeeded
        mock_commit.assert_called_once()
        assert "Successfully committed plan" in resume_events[-1].output

@pytest.mark.asyncio
async def test_rejected_recommendation_is_not_committed(app_instance):
    """Test 2: A rejected recommendation is not committed but audited."""
    runner = InMemoryRunner(app=app_instance)
    session = await runner.session_service.create_session(app_name="test_app", user_id="test_user")
    
    with patch('app.agent.commit_plan') as mock_commit, patch('app.agent.record_audit') as mock_audit:
        # Run until pause for approval
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text="Generate plan for 2026-08-25")])
        ):
            pass
            
        # Resume with 'reject'
        resume_events = []
        resume_message = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id="approval",
                        name="request_input",
                        response={"result": "reject"}
                    )
                )
            ]
        )
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session.id,
            new_message=resume_message
        ):
            resume_events.append(event)
            
        # Verify commit_plan was NOT called, but record_audit was
        mock_commit.assert_not_called()
        mock_audit.assert_called_once()
        assert "was rejected. No changes committed" in resume_events[-1].output

@pytest.mark.asyncio
async def test_firestore_failure_leaves_uncommitted(app_instance):
    """Test 3: Persistence failure leaves the workflow safely uncommitted."""
    runner = InMemoryRunner(app=app_instance)
    session = await runner.session_service.create_session(app_name="test_app", user_id="test_user")
    
    with patch('app.agent.commit_plan') as mock_commit:
        mock_commit.return_value = "Failed to commit to Firestore: Firestore unavailable"
        
        # Run until pause for approval
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text="Generate plan for 2026-08-25")])
        ):
            pass
            
        # Resume with 'approve'
        resume_events = []
        resume_message = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id="approval",
                        name="request_input",
                        response={"result": "approve"}
                    )
                )
            ]
        )
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session.id,
            new_message=resume_message
        ):
            resume_events.append(event)
            
        # Verify the tool caught the error and reported safely uncommitted
        mock_commit.assert_called_once()
        assert "Failed to commit to Firestore: Firestore unavailable" in resume_events[-1].output
