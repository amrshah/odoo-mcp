"""
Focused Benchmark for Core Architecture Models:
- Gemma 3 (1B-it-qat) -> Fast Classifier / Worker
- Qwen 3.5 (4B) -> Primary ClinicFlow Engine
- Qwen 2.5 (7B) -> High-Complexity Reasoning Tier
- BitNet 1.58b (2.7B) -> Remote Ternary Baseline
"""

import asyncio
import sys
import time
import json
import logging
import httpx
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO)


class SOAPStructure(BaseModel):
    subjective: str
    objective: str
    assessment: str
    plan: str


class PrescriptionStructure(BaseModel):
    medication_name: str
    dosage: str
    route: str
    frequency: str
    duration: str
    instructions: Optional[str] = None


TEST_CASES = {
    "TC1_SOAP_EXTRACTION": {
        "name": "W04 Ambient Scribe SOAP Extraction",
        "system_prompt": (
            "You are an expert veterinary medical scribe. Extract a structured SOAP note from the consultation dialogue.\n"
            "Respond ONLY with valid JSON conforming to: {\"subjective\": \"...\", \"objective\": \"...\", \"assessment\": \"...\", \"plan\": \"...\"}"
        ),
        "user_prompt": (
            "Doctor: Good morning! How is Max doing today?\n"
            "Owner: He has had reduced appetite and vomited twice over the last 24 hours. He seems lethargic.\n"
            "Doctor: Let's do an exam. Mucous membranes are pink and moist. Capillary refill time is 1.5 seconds. Heart rate 115 bpm, regular rhythm. Femoral pulses strong. Temperature is 102.1 F. Abdominal palpation reveals mild cranial epigastric discomfort, but no palpable foreign body or organomegaly.\n"
            "Doctor: Based on the exam, this looks like acute dietary indiscretion or mild gastroenteritis. I recommend Maropitant 16mg injection today, a bland diet for 3 days, and oral Metronidazole 250mg BID for 5 days."
        ),
        "target_schema": SOAPStructure,
    },
    "TC2_PRESCRIPTION_EXTRACTION": {
        "name": "W09 Clinical Prescription Extraction",
        "system_prompt": (
            "You are a clinical pharmacology assistant. Extract the prescription proposal from the doctor directive.\n"
            "Respond ONLY with valid JSON: {\"medication_name\": \"...\", \"dosage\": \"...\", \"route\": \"...\", \"frequency\": \"...\", \"duration\": \"...\", \"instructions\": \"...\"}"
        ),
        "user_prompt": (
            "Please prescribe Amoxicillin-Clavulanate 250mg oral tablets for Max, 1 tablet twice daily with food for 7 days."
        ),
        "target_schema": PrescriptionStructure,
    },
    "TC3_CONTRADICTION_DETECTION": {
        "name": "Safety Contradiction Detection",
        "system_prompt": (
            "You are a clinical safety validator. Check the following prescription order for contradictions or dangerous errors.\n"
            "Identify if there is a contradiction between frequency and dosage instructions.\n"
            "Respond ONLY with JSON: {\"is_contradictory\": true/false, \"error_type\": \"...\", \"explanation\": \"...\"}"
        ),
        "user_prompt": (
            "Order: Carprofen 75mg 1 tablet BID (once daily in the evening) for 14 days."
        ),
        "expected_contradiction": True,
    },
    "TC4_DIFFERENTIAL_REASONING": {
        "name": "Complex Clinical Differential Reasoning",
        "system_prompt": (
            "You are a senior veterinary clinician. Provide top 3 differential diagnoses with justification based on clinical signs.\n"
            "Respond in structured format."
        ),
        "user_prompt": (
            "Patient: 8-year-old neutered male Golden Retriever presenting with acute abdominal distension, unproductive retching, restlessness, tachycardia (160 bpm), and weak femoral pulses."
        ),
    },
}


class ModelCandidate(BaseModel):
    name: str
    endpoint_type: str
    base_url: str
    model_id: str
    api_key: Optional[str] = None


async def query_model(candidate: ModelCandidate, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    t0 = time.time()
    headers = {"Content-Type": "application/json"}
    
    if candidate.endpoint_type == "alamia":
        headers["Authorization"] = f"Bearer {candidate.api_key}"
        headers["bitnet-api-key"] = candidate.api_key
        url = f"{candidate.base_url}/v1/chat/completions"
        payload = {
            "model": candidate.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 512,
        }
    else:  # Ollama native API
        url = f"{candidate.base_url}/api/chat"
        payload = {
            "model": candidate.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1024},
        }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            elapsed_ms = (time.time() - t0) * 1000.0
            
            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                    "elapsed_ms": elapsed_ms,
                    "content": "",
                }
            
            data = resp.json()
            if candidate.endpoint_type == "alamia":
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("completion_tokens", len(content.split()))
            else:
                msg_obj = data.get("message", {})
                content = msg_obj.get("content", "")
                tokens = data.get("eval_count", len(content.split()))

            tok_per_sec = (tokens / (elapsed_ms / 1000.0)) if elapsed_ms > 0 else 0.0

            return {
                "success": True,
                "content": content,
                "elapsed_ms": round(elapsed_ms, 1),
                "tokens": tokens,
                "tokens_per_sec": round(tok_per_sec, 1),
                "error": None,
            }
    except Exception as e:
        elapsed_ms = (time.time() - t0) * 1000.0
        return {
            "success": False,
            "error": str(e),
            "elapsed_ms": round(elapsed_ms, 1),
            "content": "",
        }


def extract_json(content: str) -> Optional[Dict[str, Any]]:
    if not content:
        return None
    cleaned = content.strip()
    if "```json" in cleaned:
        start_idx = cleaned.find("```json") + 7
        end_idx = cleaned.find("```", start_idx)
        cleaned = cleaned[start_idx:end_idx].strip() if end_idx != -1 else cleaned[start_idx:].strip()
    elif "```" in cleaned:
        start_idx = cleaned.find("```") + 3
        end_idx = cleaned.find("```", start_idx)
        cleaned = cleaned[start_idx:end_idx].strip() if end_idx != -1 else cleaned[start_idx:].strip()

    try:
        return json.loads(cleaned)
    except Exception:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start:end+1])
            except Exception:
                pass
    return None


async def main():
    candidates = [
        ModelCandidate(
            name="Gemma-3-1B-it (Local Ollama)",
            endpoint_type="ollama",
            base_url="http://localhost:11434",
            model_id="gemma3:1b-it-qat",
        ),
        ModelCandidate(
            name="Qwen-3.5-4B (Local Ollama)",
            endpoint_type="ollama",
            base_url="http://localhost:11434",
            model_id="qwen3.5:4b",
        ),
        ModelCandidate(
            name="Qwen-2.5-7B (Local Ollama)",
            endpoint_type="ollama",
            base_url="http://localhost:11434",
            model_id="qwen2.5:7b",
        ),
    ]

    print("=" * 80)
    print("🏥 CORE CLINICAL MODEL BENCHMARK (Gemma 1B vs Qwen 3.5 4B vs Qwen 2.5 7B)")
    print("=" * 80 + "\n")

    results = {}

    for cand in candidates:
        print(f"▶️ Benchmarking: {cand.name} ...")
        results[cand.name] = {}
        for tc_key, tc in TEST_CASES.items():
            res = await query_model(cand, tc["system_prompt"], tc["user_prompt"])
            schema_valid = False
            parsed = None
            if res["success"]:
                parsed = extract_json(res["content"])
                if "target_schema" in tc and parsed:
                    try:
                        tc["target_schema"].model_validate(parsed)
                        schema_valid = True
                    except Exception:
                        schema_valid = False
                elif "expected_contradiction" in tc and parsed:
                    schema_valid = (parsed.get("is_contradictory") is True)
                elif tc_key == "TC4_DIFFERENTIAL_REASONING":
                    schema_valid = any(w in res["content"].lower() for w in ["gdv", "gastric dilatation", "volvulus", "torsion"])

            results[cand.name][tc_key] = {
                "success": res["success"],
                "elapsed_ms": res["elapsed_ms"],
                "tok_per_sec": res.get("tokens_per_sec", 0),
                "schema_valid": schema_valid,
                "parsed": parsed,
                "content_preview": res["content"][:200],
            }
            status = "✅ PASS" if (res["success"] and schema_valid) else "❌ FAIL"
            print(f"   [{status}] {tc['name']}: {res['elapsed_ms']}ms ({res.get('tokens_per_sec', 0)} tok/s)")
        print()

    with open("core_benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("=" * 80)
    print("📊 FINAL ARCHITECTURE BENCHMARK MATRIX")
    print("=" * 80)
    print(f"{'Model Candidate':<30} | {'TC1 SOAP':<10} | {'TC2 Rx':<10} | {'TC3 Safety':<12} | {'TC4 Reason':<12} | {'Avg Latency':<12}")
    print("-" * 95)
    for cname, tcs in results.items():
        s1 = "✅ PASS" if tcs["TC1_SOAP_EXTRACTION"]["schema_valid"] else "❌ FAIL"
        s2 = "✅ PASS" if tcs["TC2_PRESCRIPTION_EXTRACTION"]["schema_valid"] else "❌ FAIL"
        s3 = "✅ PASS" if tcs["TC3_CONTRADICTION_DETECTION"]["schema_valid"] else "❌ FAIL"
        s4 = "✅ PASS" if tcs["TC4_DIFFERENTIAL_REASONING"]["schema_valid"] else "❌ FAIL"
        lats = [t["elapsed_ms"] for t in tcs.values() if t["success"]]
        avg_l = f"{sum(lats)/len(lats):.0f} ms" if lats else "ERR"
        print(f"{cname:<30} | {s1:<10} | {s2:<10} | {s3:<12} | {s4:<12} | {avg_l:<12}")


if __name__ == "__main__":
    asyncio.run(main())
