# Neuravale

Independent, locally deployable artificial intelligence. Phase 1 includes a FastAPI backend, a polished chat UI, streaming responses, local SQLite conversation history, and an Ollama model adapter. No commercial API keys are required.

## Requirements
- Python 3.11+
- Ollama installed and running locally
- A model pulled locally: `ollama pull qwen2.5:3b`

## Start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. The interface streams real responses from Ollama, shows connection errors instead of fabricating responses, and stores conversations in a local SQLite file. Set `NEURAVALE_MODEL` in .env to switch downloaded models. Do not expose this development server to the public internet: this phase has no user authentication or public rate limits.

## API
- `GET /api/health` — application and Ollama connectivity
- `GET /api/conversations` — local session history
- `GET /api/conversations/{id}` — complete message history
- `POST /api/chat` — streaming NDJSON tokens; JSON body `{ "message": "...", "conversation_id": "optional" }`

## Tests
```bash
pip install -r requirements-dev.txt
pytest -q
```

## Architecture
- `app/main.py`: validated FastAPI endpoints and streaming orchestration
- `app/store.py`: SQLite persistence
- `app/model.py`: Ollama streaming API adapter
- `static/`: responsive, no-build web frontend

## Limitations
Neuravale Phase 1 hosts open-weight models rather than training a new foundation model. Quality depends on the downloaded model and available RAM/GPU. Its data remains on the computer running it, except for any outbound traffic caused by your local environment. No production auth, multi-tenancy, billing, tools, agent execution or cloud deployment is implemented yet. Respect each model's license.

## Phase 2 foundation (0.2)
Select any installed Ollama model in the chat header. Delete local conversations from the composer. The backend checks model availability before writing a new message and rejects incomplete inference streams. Context is limited to the most recent 40 messages; this is not semantic long-term memory. Run the small exact-answer evaluation suite with `python -m research.evaluate --model qwen2.5:3b`. Results are local diagnostics, not frontier benchmark claims.


## Neuravale N series (0.5 preview)
The website brands the Qwen2.5 0.5B, 1.5B and 3B inference profiles as N1 Mini, N1 Compact and N1 respectively. These are runtime profiles, not independently trained or owned model weights. Runtime IDs and original model provenance remain visible in the selector, model catalog, and exported evaluation results. R1, C1, V1, A1 and E1 are research targets only. Website publishing source: main/docs.


## Browser CPU compatibility (0.6)
Chat and Research expose CPU/WebAssembly profiles even without WebGPU. N1 Lite uses SmolLM2 135M Instruct ONNX, N1 Mini CPU uses Qwen2.5 0.5B Instruct ONNX. CPU runs in a worker via Transformers.js 3.8.1, single-threaded, q4; GPU options are discovered separately. CPU responses appear after generation, not token by token. Actual performance depends on browser and memory. No hosted inference or paid API is involved.


## Original model research: N0 Chat 003
See [research/n0_chat](research/n0_chat) for the from-scratch dialogue model training source, local demo and measured run summary. The exact original checkpoint is not yet uploaded. The public chat still uses third-party models; N0 Chat 003 is a narrow research prototype.
