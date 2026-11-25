"""Small deterministic local-model smoke benchmark; no paid API."""
import argparse
import asyncio
import json
import time
from app.model import stream_model

CASES = [("What is 17 multiplied by 19? Reply with only the number.", "323"), ("Return only the capital of France.", "paris"), ("Reverse the string ABCD. Return only the result.", "dcba"), ("What is the next integer after 99? Return only the number.", "100")]

async def run(model):
    rows = []
    for prompt, expected in CASES:
        start = time.monotonic()
        try:
            parts = [token async for token in stream_model([{"role": "user", "content": prompt}], model)]
            answer = "".join(parts).strip()
            rows.append({"prompt": prompt, "answer": answer, "expected": expected, "passed": answer.casefold() == expected, "seconds": round(time.monotonic()-start, 2)})
        except Exception as exc:
            rows.append({"prompt": prompt, "passed": False, "error": type(exc).__name__})
    print(json.dumps({"model": model, "passed": sum(r["passed"] for r in rows), "total": len(rows), "cases": rows}, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    asyncio.run(run(parser.parse_args().model))
