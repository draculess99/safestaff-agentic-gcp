# SafeStaff Agentic GCP

A modern, Google-native AI agent for healthcare staffing forecasting, built for the All Things Agentic Hackathon.

## Architecture

* **Orchestration**: Google ADK 2.0 (Workflow API)
* **Model**: Gemini 3.5 Flash via Vertex AI
* **State & Audit**: Firestore
* **Frontend**: Streamlit
* **Deployment**: Cloud Run

## Verified workflow evidence

- [x] One successful controlled Vertex AI execution

The live Vertex/Gemini test passed and produced a schema-valid StaffingPlan. Our deterministic safety validation successfully enforced 42 direct-care staff, 9 supervisors, at least 10 RNs, and 51 total staff.

![A generated staffing plan pauses for explicit human approval before Firestore](docs/screenshots/01-human-approval-pending.png.jpg)
![An approved plan completes and is committed to Firestore with an audit ID](docs/screenshots/02-human-decision-audit.png.jpg)

## Getting Started

1. Copy `.env.example` to `.env` and fill in your GCP project details.
2. Install dependencies: `pip install -r requirements.txt`
3. Run the Streamlit interface: `streamlit run ui/app.py`

## Features

- **Deterministic Workflow**: Data Intake -> AI Forecasting -> Human-in-the-Loop Review -> Commit to Firestore.
- **XGBoost Integration**: (Coming soon) Reuses forecasting components from the legacy SafeStaff codebase.
- **Healthcare Domain Rules**: (Coming soon) Applied during the recommendation generation phase.
