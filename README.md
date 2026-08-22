# SafeStaff Agentic GCP

A modern, Google-native AI agent for healthcare staffing forecasting, built for the All Things Agentic Hackathon.

## Architecture

* **Orchestration**: Google ADK 2.0 (Workflow API)
* **Model**: Gemini 3.5 Flash via Vertex AI
* **State & Audit**: Firestore
* **Frontend**: Streamlit
* **Deployment**: Cloud Run

## Getting Started

1. Copy `.env.example` to `.env` and fill in your GCP project details.
2. Install dependencies: `pip install -r requirements.txt`
3. Run the Streamlit interface: `streamlit run ui/app.py`

## Features

- **Deterministic Workflow**: Data Intake -> AI Forecasting -> Human-in-the-Loop Review -> Commit to Firestore.
- **XGBoost Integration**: (Coming soon) Reuses forecasting components from the legacy SafeStaff codebase.
- **Healthcare Domain Rules**: (Coming soon) Applied during the recommendation generation phase.
