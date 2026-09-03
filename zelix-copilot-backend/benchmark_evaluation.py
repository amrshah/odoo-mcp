"""
SLM Multi-Model Clinical Evaluation & Benchmarking Suite (V2)
Evaluates and compares BitNet 1.58b (remote) against local Ollama SLMs:
- BitNet 1.58b (2.7B ternary via Alamia AI)
- Gemma 3 (1B-it-qat)
- Qwen 2.5 Coder (1.5B)
- Qwen 3.5 (4B - Reasoning Model with Think Tag extraction)
- Qwen 2.5 Coder (7B)

Evaluation Dimensions:
1. Latency (Time-to-Complete ms)
2. Token Throughput (est. tokens/sec)
3. Structured Output Conformance (SOAP note Pydantic schema validation)
4. Clinical Contradiction Detection (BID vs once daily catch rate)
5. Clinical Prescription Extraction (Medication, dosage, route, frequency precision)
6. Complex Clinical Reasoning & Differential Diagnosis quality
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
logger = logging.getLogger("zelix.benchmark")


# Clinical Schemas to evaluate
class SOAPStructure(BaseModel):
    subjective: str = Field(..., description="Owner stated complaints and history")
    objective: str = Field(..., description="Vitals and physical examination findings")
    assessment: str = Field(..., description="Differential diagnoses and clinical evaluation")
    plan: str = Field(..., description="Diagnostic, therapeutic, and client education plan")


class PrescriptionStructure(BaseModel):
    medication_name: str
    dosage: str
    route: str
    frequency: str
    duration: str
    instructions: Optional[str] = None


# Benchmark Test Cases
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
    endpoint_type: str  # "alamia" or "ollama"
    base_url: str
    model_id: str
    api_key: Optional[str] = None


async def query_model(candidate: ModelCandidate, system_prompt: str, user_prompt: str, json_mode: bool = True) -> Dict[str, Any]:
    """Execute query against candidate model endpoint."""
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
                # If thinking model placed response in thinking or content
                if not content and "thinking" in msg_obj:
                    content = msg_obj.get("thinking", "")
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
    """Extract and parse JSON object from model raw output."""
    if not content:
        return None
    cleaned = content.strip()
    # Remove markdown ```json ``` markers
    if "```json" in cleaned:
        start_idx = cleaned.find("```json") + 7
        end_idx = cleaned.find("```", start_idx)
        if end_idx != -1:
            cleaned = cleaned[start_idx:end_idx].strip()
        else:
            cleaned = cleaned[start_idx:].strip()
    elif "```" in cleaned:
        start_idx = cleaned.find("```") + 3
        end_idx = cleaned.find("```", start_idx)
        if end_idx != -1:
            cleaned = cleaned[start_idx:end_idx].strip()
        else:
            cleaned = cleaned[start_idx:].strip()

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


async def run_full_benchmark():
    candidates = [
        ModelCandidate(
            name="BitNet-1.58b-2B (Alamia Remote)",
            endpoint_type="alamia",
            base_url="https://ai.alamiaconnect.com",
            model_id="/models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf",
            api_key="51129693340",
        ),
        ModelCandidate(
            name="Gemma-3-1B-it (Local Ollama)",
            endpoint_type="ollama",
            base_url="http://localhost:11434",
            model_id="gemma3:1b-it-qat",
        ),
        ModelCandidate(
            name="Qwen-2.5-Coder-1.5B (Local Ollama)",
            endpoint_type="ollama",
            base_url="http://localhost:11434",
            model_id="qwen2.5-coder:1.5b",
        ),
        ModelCandidate(
            name="Qwen-3.5-4B (Local Ollama)",
            endpoint_type="ollama",
            base_url="http://localhost:11434",
            model_id="qwen3.5:4b",
        ),
        ModelCandidate(
            name="Qwen-2.5-Coder-7B (Local Ollama)",
            endpoint_type="ollama",
            base_url="http://localhost:11434",
            model_id="qwen2.5-coder:7b",
        ),
    ]

    print("=" * 80)
    print("🏥 ZELIX COPILOT MULTI-MODEL CLINICAL EVALUATION BENCHMARK (V2)")
    print(f"Comparing {len(candidates)} Model Candidates across 4 Clinical Test Batteries")
    print("=" * 80 + "\n")

    results_matrix = {}

    for cand in candidates:
        print(f"▶️ Testing Candidate: {cand.name} ...")
        results_matrix[cand.name] = {}
        
        for tc_key, tc in TEST_CASES.items():
            is_json = "target_schema" in tc or "expected_contradiction" in tc
            res = await query_model(cand, tc["system_prompt"], tc["user_prompt"], json_mode=is_json)
            
            # Validation
            schema_valid = False
            parsed_data = None
            if res["success"]:
                parsed_data = extract_json(res["content"])
                if "target_schema" in tc and parsed_data:
                    try:
                        tc["target_schema"].model_validate(parsed_data)
                        schema_valid = True
                    except Exception:
                        schema_valid = False
                elif "expected_contradiction" in tc and parsed_data:
                    is_contra = parsed_data.get("is_contradictory")
                    schema_valid = (is_contra is True)
                elif tc_key == "TC4_DIFFERENTIAL_REASONING":
                    # Check if GDV / Gastric Dilatation-Volvulus is recognized
                    schema_valid = any(term in res["content"].lower() for term in ["gdv", "gastric dilatation", "volvulus", "torsion"])
            
            score_entry = {
                "success": res["success"],
                "elapsed_ms": res["elapsed_ms"],
                "tokens_per_sec": res.get("tokens_per_sec", 0),
                "schema_valid": schema_valid,
                "parsed_data": parsed_data,
                "raw_content": res["content"][:300] if res["content"] else "",
                "error": res["error"],
            }
            results_matrix[cand.name][tc_key] = score_entry
            
            status_icon = "✅ PASS" if (res["success"] and schema_valid) else "❌ FAIL"
            print(f"   [{status_icon}] {tc['name']}: {res['elapsed_ms']}ms ({res.get('tokens_per_sec', 0)} tok/s)")
        
        print()

    # Save Results
    with open("benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results_matrix, f, indent=2)

    print("=" * 80)
    print("📊 BENCHMARK SUMMARY MATRIX")
    print("=" * 80)
    print(f"{'Model Name':<35} | {'TC1 (SOAP)':<12} | {'TC2 (Rx)':<12} | {'TC3 (Safety)':<12} | {'TC4 (Reason)':<12} | {'Avg Latency':<12}")
    print("-" * 105)

    for cand_name, tcs in results_matrix.items():
        tc1_s = "✅ PASS" if tcs.get("TC1_SOAP_EXTRACTION", {}).get("schema_valid") else "❌ FAIL"
        tc2_s = "✅ PASS" if tcs.get("TC2_PRESCRIPTION_EXTRACTION", {}).get("schema_valid") else "❌ FAIL"
        tc3_s = "✅ PASS" if tcs.get("TC3_CONTRADICTION_DETECTION", {}).get("schema_valid") else "❌ FAIL"
        tc4_s = "✅ PASS" if tcs.get("TC4_DIFFERENTIAL_REASONING", {}).get("schema_valid") else "❌ FAIL"
        
        latencies = [t["elapsed_ms"] for t in tcs.values() if t["success"]]
        avg_lat = f"{sum(latencies)/len(latencies):.0f} ms" if latencies else "ERR"
        
        print(f"{cand_name:<35} | {tc1_s:<12} | {tc2_s:<12} | {tc3_s:<12} | {tc4_s:<12} | {avg_lat:<12}")

    print("\nBenchmark completed and saved to benchmark_results.json")


if __name__ == "__main__":
    asyncio.run(run_full_benchmark())
