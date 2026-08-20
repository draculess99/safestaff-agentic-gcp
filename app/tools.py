import datetime
import os
import json
from google.cloud import firestore

def generate_forecast(historical_data: dict) -> dict:
    """Mock XGBoost forecaster."""
    # To be replaced with actual XGBoost prediction from legacy code
    return {"predicted_demand": 42, "confidence": 0.85}

def apply_healthcare_rules(demand: int) -> list:
    """Mock healthcare domain rules."""
    # To be replaced with actual rule engine logic from legacy code
    return [
        f"Require at least {demand // 4} RNs on shift.",
        f"Maintain 1:{demand // 8} supervisor ratio."
    ]

def _write_mock_audit(audit_data: dict) -> None:
    mock_file = "mock_audit.json"
    data = []
    if os.path.exists(mock_file):
        with open(mock_file, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                pass
    data.append(audit_data)
    with open(mock_file, "w") as f:
        json.dump(data, f, indent=2)

def commit_plan(
    workflow_id: str,
    input_scenario: str,
    forecast: dict,
    recommendation: dict,
    approval_status: str,
    human_decision: str,
    staffing_plan: dict
) -> str:
    """
    Writes the final approved recommendation and audit record to Firestore.
    Acts as the authoritative persistent record for the workflow.
    """
    audit_data = {
        "workflow_id": workflow_id,
        "input_scenario": input_scenario,
        "forecast": forecast,
        "recommendation": recommendation,
        "approval_status": approval_status,
        "human_decision": human_decision,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "staffing_plan": staffing_plan
    }
    
    if os.getenv("MOCK_MODE", "").lower() == "true":
        _write_mock_audit(audit_data)
        return f"Successfully committed plan to Mock JSON (ID: {workflow_id})."

    try:
        db = firestore.Client()
        doc_ref = db.collection("staffing_audits").document(workflow_id)
        doc_ref.set(audit_data)
        return f"Successfully committed plan to Firestore (ID: {workflow_id})."
    except Exception as e:
        return f"Failed to commit to Firestore: {str(e)}"

def record_audit(
    workflow_id: str,
    input_scenario: str,
    forecast: dict,
    recommendation: dict,
    approval_status: str,
    human_decision: str,
    staffing_plan: dict
) -> str:
    """
    Writes an audit record without committing any changes.
    Used for rejected workflows.
    """
    audit_data = {
        "workflow_id": workflow_id,
        "input_scenario": input_scenario,
        "forecast": forecast,
        "recommendation": recommendation,
        "approval_status": approval_status,
        "human_decision": human_decision,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "staffing_plan": staffing_plan
    }
    
    if os.getenv("MOCK_MODE", "").lower() == "true":
        _write_mock_audit(audit_data)
        return f"Successfully recorded audit to Mock JSON (ID: {workflow_id})."

    try:
        db = firestore.Client()
        doc_ref = db.collection("staffing_audits").document(workflow_id)
        doc_ref.set(audit_data)
        return f"Successfully recorded audit to Firestore (ID: {workflow_id})."
    except Exception as e:
        return f"Failed to record audit to Firestore: {str(e)}"
