import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

load_dotenv()
from app import store  # noqa: E402
from app.model import model_name, ollama_url, stream_model, installed_models  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("neuravale")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.initialize()
    yield


app = FastAPI(title="Neuravale", version="0.2.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=16000)
    conversation_id: uuid.UUID | None = None
    model: str | None = Field(default=None, max_length=200)


@app.get("/")
async def home():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/style.css")
async def style():
    return FileResponse(ROOT / "static" / "style.css", media_type="text/css")


@app.get("/app.js")
async def script():
    return FileResponse(ROOT / "static" / "app.js", media_type="text/javascript")


@app.get("/api/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(ollama_url() + "/api/tags")
            response.raise_for_status()
            installed = [m.get("name") for m in response.json().get("models", [])]
        return {"status": "ok", "ollama": "connected", "model": model_name(), "installed_models": installed}
    except (httpx.HTTPError, ValueError) as exc:
        return {"status": "degraded", "ollama": "unavailable", "model": model_name(), "reason": type(exc).__name__}


@app.get("/api/conversations")
async def conversations():
    return store.list_conversations()


@app.get("/api/conversations/{conversation_id}")
async def conversation(conversation_id: uuid.UUID):
    key = str(conversation_id)
    if not store.conversation_exists(key):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"id": key, "messages": store.messages(key)}


def event(data):
    return (json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8")


@app.post("/api/chat")
async def chat(body: ChatRequest):
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message is empty")
    if body.conversation_id and not store.conversation_exists(str(body.conversation_id)):
        raise HTTPException(status_code=404, detail="Conversation not found")
    selected = body.model or model_name()
    try:
        available = await installed_models()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="Ollama is unavailable")
    if selected not in available:
        raise HTTPException(status_code=422, detail="Selected model is not installed")
    key = str(body.conversation_id) if body.conversation_id else store.create_conversation(message)
    if not store.conversation_exists(key):
        raise HTTPException(status_code=404, detail="Conversation not found")
    history = store.messages(key)
    store.append_message(key, "user", message)
    history.append({"role": "user", "content": message})

    async def generate():
        yield event({"type": "conversation", "id": key})
        content = ""
        try:
            async for token in stream_model(history[-40:], selected):
                content += token
                yield event({"type": "token", "text": token})
            if content:
                store.append_message(key, "assistant", content)
            yield event({"type": "done"})
        except (httpx.HTTPError, RuntimeError, ValueError, asyncio.TimeoutError) as exc:
            log.warning("Inference failed: %s", type(exc).__name__)
            yield event({"type": "error", "message": "Inference unavailable. Check that Ollama is running and the model is downloaded."})

    return StreamingResponse(generate(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.get("/api/models")
async def models():
    try:
        return {"models": await installed_models(), "default": model_name()}
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="Ollama is unavailable")


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: uuid.UUID):
    if not store.delete_conversation(str(conversation_id)):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True}
