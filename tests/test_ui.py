import os
import pytest
from streamlit.testing.v1 import AppTest
from unittest.mock import patch

@pytest.fixture
def mock_env():
    # Force mock mode for UI tests
    os.environ["MOCK_MODE"] = "true"
    yield
    # Cleanup if needed

def test_ui_mock_mode_banner_and_approval(mock_env):
    """Test that the UI shows the mock mode banner and correct output."""
    at = AppTest.from_file("../ui/streamlit_app.py").run()
    
    # 1. Verify the green mock mode banner
    assert any("SAFE MOCK MODE" in str(success.value) for success in at.success)
    
    # 2. Click generate button
    generate_button = at.button[0] # "Run Forecast & Generate Plan"
    generate_button.click().run()
    
    # Verify we hit the awaiting approval state
    assert any("recording in the local mock audit" in str(info.value) for info in at.info)
    
    # 3. Click approve button
    approve_button = at.button[1] # "Approve Plan" (button[0] is generate, button[1] is approve, button[2] is reject)
    approve_button.click().run()
    
    # Verify final success state
    assert any("Workflow finished" in str(success.value) for success in at.success)
    assert any("approved and successfully committed to the local mock audit" in str(info.value) for info in at.info)

def test_ui_mock_mode_rejection(mock_env):
    """Test the rejection path in the UI."""
    at = AppTest.from_file("../ui/streamlit_app.py").run()
    
    # Click generate
    at.button[0].click().run()
    
    # Click reject
    reject_button = at.button[2] # "Reject Plan"
    reject_button.click().run()
    
    # Verify final rejection state
    assert any("Workflow finished" in str(success.value) for success in at.success)
    assert any("rejected. No staffing changes were committed" in str(info.value) for info in at.info)
