Drive Lens
=======================

Backend assignment implementation for a conversational Google Drive search agent.

Setup
-----

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root:

```env
FOLDER_ID=your_google_drive_folder_id
SERVICE_ACCOUNT_FILE=./credentials/service-account.json
BACKEND_URL=http://localhost:8000

# Choose one LLM provider: gemini, groq, openrouter, or openai.
LLM_PROVIDER=gemini
MODEL_NAME=gemini-2.5-flash-lite
GOOGLE_API_KEY=your_gemini_api_key
```

4. Place the Google service account JSON at `credentials/service-account.json`.

LLM provider examples
---------------------

Gemini:

```env
LLM_PROVIDER=gemini
MODEL_NAME=gemini-2.5-flash-lite
GOOGLE_API_KEY=your_gemini_api_key
```

Groq:

```env
LLM_PROVIDER=groq
MODEL_NAME=openai/gpt-oss-20b
GROQ_API_KEY=your_groq_api_key
```

OpenRouter:

```env
LLM_PROVIDER=openrouter
MODEL_NAME=openai/gpt-oss-120b:free
OPENROUTER_API_KEY=your_openrouter_api_key
```

OpenAI:

```env
LLM_PROVIDER=openai
MODEL_NAME=gpt-4.1-mini
OPENAI_API_KEY=your_openai_api_key
```

If `MODEL_NAME` is omitted, the app uses a sensible default for the selected
provider. All providers use the same LangGraph tool-calling flow.

Run
---

Start the backend:

```bash
uvicorn backend.main:app --reload
```

Start the Streamlit frontend in a second terminal:

```bash
streamlit run frontend/app.py
```

Health check:

```bash
curl http://localhost:8000/health
```

Persistence
-----------

Session metadata is stored in `backend/data/sessions.db`. LangGraph conversation
checkpoints are stored in `backend/data/checkpoints.db` through `AsyncSqliteSaver`,
so chat history can survive backend restarts.
