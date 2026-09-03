import asyncio
import sys
import json
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def test_qwen():
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "model": "qwen3.5:4b",
            "messages": [
                {"role": "system", "content": "Extract structured JSON: {\"subjective\": \"...\", \"objective\": \"...\", \"assessment\": \"...\", \"plan\": \"...\"}"},
                {"role": "user", "content": "Max vomited twice today. Mucous membranes pink, HR 115, temp 102.1. Diagnosis gastroenteritis. Plan maropitant."}
            ],
            "stream": False
        }
        r = await client.post("http://localhost:11434/api/chat", json=payload)
        data = r.json()
        print("Raw Message Keys:", list(data.get("message", {}).keys()))
        print("Message Content:\n", data.get("message", {}).get("content"))
        if "thinking" in data.get("message", {}):
            print("Thinking Field Present:\n", data.get("message", {}).get("thinking")[:150])

if __name__ == "__main__":
    asyncio.run(test_qwen())
