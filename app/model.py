import json
import os
import httpx

SYSTEM_PROMPT = "You are Neuravale, a capable, accurate and helpful AI assistant. Be direct, reason carefully, and acknowledge uncertainty. Do not claim to perform actions you have not performed."


def model_name():
    return os.getenv("NEURAVALE_MODEL", "qwen2.5:3b")


def ollama_url():
    return os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")


async def stream_model(history):
    payload = {"model": model_name(), "stream": True, "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + [{"role": m["role"], "content": m["content"]} for m in history]}
    async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=5)) as client:
        async with client.stream("POST", ollama_url() + "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                item = json.loads(line)
                if item.get("error"):
                    raise RuntimeError(str(item["error"]))
                token = item.get("message", {}).get("content", "")
                if token:
                    yield token
                if item.get("done"):
                    break
