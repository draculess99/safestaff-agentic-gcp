# GCP Agentic Deployment Runbook

## Purpose and Reuse Guidance
This runbook serves as a reusable, interview-ready guide for deploying human-governed AI agent projects to Google Cloud Platform (GCP). It was originally developed alongside the SafeStaff Agentic GCP prototype. It documents the critical boundary between safe local testing (mocking and controlled live execution) and secure public deployment (mock-only). You can adapt these patterns to reliably scale any future agentic workflows built on Google ADK, Vertex AI, and Streamlit.

## Prerequisites and Google Cloud APIs

```mermaid
flowchart LR
    Dev[Local Developer] -->|gcloud run deploy| CR(Cloud Run)
    CR -->|MOCK_MODE=true| Mock[Local Mock Audit]
    CR -.->|MOCK_MODE=false| VAI(Vertex AI)
    CR -.->|MOCK_MODE=false| FS[(Firestore)]
    
    style CR fill:#f9f,stroke:#333,stroke-width:2px
    style VAI fill:#d4edda,stroke:#333
    style FS fill:#cce5ff,stroke:#333
    style Mock fill:#fff3cd,stroke:#333
```

Before starting deployment or live testing, ensure the following are configured in your GCP project:
- A valid Google Cloud Project with billing enabled.
- **Cloud Run API** (`run.googleapis.com`) enabled.
- **Vertex AI API** (`aiplatform.googleapis.com`) enabled (required only for controlled live testing).
- **Cloud Build API** (`cloudbuild.googleapis.com`) enabled (required for source-based deployment).
- Google Cloud CLI (`gcloud`) installed and authenticated locally.

## Local Virtual Environment and Dependencies
Isolate your environment before running tests or deployments:
```bash
python -m venv .venv
# On Windows: .\.venv\Scripts\activate
# On Linux/Mac: source .venv/bin/activate
pip install --no-cache-dir -r requirements.txt
```

## Environment Variables Configuration
Configure a local `.env` file. **Never commit secrets to version control.**
Standard required variables include:
- `MOCK_MODE`: Controls whether the agent calls external APIs (`true` or `false`).
- `RUN_LIVE_TESTS`: Flag to enable specific integration tests (`true` or `false`).
- `GEMINI_MODEL`: Specifies the Vertex AI model version.
- `GOOGLE_CLOUD_PROJECT`: Target project ID.
- `GOOGLE_CLOUD_LOCATION`: Region for the deployment and Vertex AI calls.
- `GOOGLE_GENAI_USE_VERTEXAI`: Enable Google GenAI SDK Vertex usage.

*Note: Use placeholders in `.env.example` to track structure.*

## Testing Methodologies

```mermaid
flowchart TD
    Start[Run Test/App] --> Mode{MOCK_MODE?}
    Mode -- true --> Mock[Mock Mode]
    Mock --> U[Local UI Testing]
    Mock --> T1[pytest tests/]
    Mock --> M[Deterministic Mock Output]
    
    Mode -- false --> Live[Controlled Live Mode]
    Live --> V[Vertex AI API]
    Live --> T2[pytest tests/test_live.py -s]
    Live --> O[Real Gemini Output]
```

### Mock-Mode Local Testing
Ensures core workflow orchestration and UI functions perfectly without hitting live endpoints.
```bash
# Set MOCK_MODE=true in .env
streamlit run ui/streamlit_app.py
python -m pytest tests/
```

### Controlled Live Vertex Testing
Proves integration with live Vertex AI endpoints before deployment. This controlled test was successfully proven locally for the SafeStaff prototype.
```bash
# Set MOCK_MODE=false and RUN_LIVE_TESTS=true in .env
python -m pytest tests/test_live.py -s
```

## Dockerfile Lessons Learned

```mermaid
flowchart LR
    Container[Docker Container]
    Container -->|1. Set PATH| WP[WORKDIR /app\nENV PYTHONPATH=/app]
    Container -->|2. Entrypoint| CMD[CMD streamlit run ui/streamlit_app.py]
    WP --> Python[Python finds app/agent.py]
    CMD --> UI[UI Loads Successfully]
```

When containerizing Streamlit with Google ADK, two critical configuration elements are required to prevent startup failures:
1. **Streamlit Entry Point**: The `CMD` instruction must accurately point to the nested Streamlit file. Use `"ui/streamlit_app.py"`, not the generic `"ui/app.py"`.
2. **Python Path Integration**: Streamlit often fails to resolve sibling package modules (e.g., `app/agent.py`) inside the container. You must explicitly declare the root path immediately following the `WORKDIR` directive:
   ```dockerfile
   WORKDIR /app
   ENV PYTHONPATH=/app
   ```

## Cloud Run Deployment and Safety Configuration
For public demonstrations, the deployment must strictly execute in mock mode to prevent unauthorized inference costs or database mutations.

Deploy directly from source, enforcing safety rules:
```bash
gcloud run deploy safestaff-agentic-demo \
  --source . \
  --port 8501 \
  --allow-unauthenticated \
  --set-env-vars="MOCK_MODE=true" \
  --min-instances=0 \
  --max-instances=1 \
  --region=us-central1
```

## Post-Deployment Checks
After a successful deployment:
1. Navigate to the provided `https://*.run.app` URL.
2. Verify the application loads without a "Please wait" hanging state.
3. Confirm the "SAFE MOCK MODE" indicator is visible in the UI.
4. Execute the workflow to confirm mock outputs render seamlessly.

## Cost and Safety Controls
- **Scale-to-Zero Configuration**: Setting `--min-instances 0` prevents idle billing.
- **Max Instance Limiting**: Setting `--max-instances 1` guarantees costs cannot surge during an accidental or malicious spike in traffic.
- **Public Mock Mode Limit**: Passing `--set-env-vars="MOCK_MODE=true"` at the deployment level guarantees that no public user can invoke the live Vertex AI endpoint.

## Common Failures and Fixes
- **`ModuleNotFoundError: No module named 'app'`**: Caused by missing Python path resolution in the Docker container. *Fix: Add `ENV PYTHONPATH=/app` to the `Dockerfile`.*
- **Streamlit "File not found" or 404 Errors**: Caused by an invalid file reference in the Docker `CMD`. *Fix: Update `CMD` to point precisely to `"ui/streamlit_app.py"`.*
- **Cloud Run Startup Timeouts or Port Errors**: Caused by Streamlit binding to localhost instead of all interfaces. *Fix: Ensure the Docker `CMD` includes `--server.address=0.0.0.0` and `--server.port=8501`, and the deployment uses `--port 8501`.*

## Reproducibility Checklist
- [ ] Dependencies documented precisely in `requirements.txt`.
- [ ] Environment variable template maintained in `.env.example`.
- [ ] `Dockerfile` entry points and `PYTHONPATH` explicitly configured.
- [ ] Deterministic unit tests passed natively.
- [ ] Controlled Live Vertex integration confirmed locally.
- [ ] Public Cloud Run deployment executed with bounded scaling limits and mock isolation.

## Adapting this Runbook to Another Agent Project
To reuse this runbook for a new Google ADK agent:
1. Update the `CMD` file reference if your UI entry point differs from `ui/streamlit_app.py`.
2. Adapt the environment variable schema and ensure custom `MOCK_MODE` implementations exist in your new node functions.
3. Replace `safestaff-agentic-demo` in the `gcloud run deploy` command with your new project slug.
4. If your new agent necessitates live public access, transition from `--allow-unauthenticated` to an explicit Identity-Aware Proxy (IAP) or IAM authenticated invocation model.
