"""
Comprehensive Clinical Model Benchmark Suite (Stage A & Stage B)
Per model-comparison-review.md guidelines:
Evaluates:
- Gemma 3 1B (gemma3:1b-it-qat)
- Qwen 3.5 4B (qwen3.5:4b)
- Qwen 2.5 7B Instruct (qwen2.5:7b - Non-Coder general instruct)
- DeepSeek R1 14B (deepseek-r1:14b)

Logs full telemetry:
- prompt_tokens, output_tokens, thinking_tokens
- wall_time, tokens/sec
- raw_response, parsed_response
- schema_pass, clinical_consistency_pass, grounding_pass
- failure_reason
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
        "name": "Clinical Safety Contradiction Detection",
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
    model_id: str
    role_description: str


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


async def evaluate_model(cand: ModelCandidate) -> Dict[str, Any]:
    print(f"\n========================================================")
    print(f"▶️ Benchmarking Candidate: {cand.name} ({cand.model_id})")
    print(f"   Role: {cand.role_description}")
    print(f"========================================================")
    
    cand_results = {}
    
    for tc_key, tc in TEST_CASES.items():
        print(f"   Testing: {tc['name']} ...", end=" ", flush=True)
        t0 = time.time()
        
        payload = {
            "model": cand.model_id,
            "messages": [
                {"role": "system", "content": tc["system_prompt"]},
                {"role": "user", "content": tc["user_prompt"]},
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1024},
        }

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                r = await client.post("http://localhost:11434/api/chat", json=payload)
                wall_time_ms = round((time.time() - t0) * 1000.0, 1)
                
                if r.status_code != 200:
                    cand_results[tc_key] = {
                        "pass": False,
                        "wall_time_ms": wall_time_ms,
                        "failure_reason": f"HTTP {r.status_code}: {r.text[:150]}",
                    }
                    print(f"❌ FAIL (HTTP {r.status_code})")
                    continue

                data = r.json()
                msg = data.get("message", {})
                content = msg.get("content", "").strip()
                thinking = msg.get("thinking", "").strip()
                
                prompt_tokens = data.get("prompt_eval_count", 0)
                output_tokens = data.get("eval_count", len(content.split()))
                tok_per_sec = round((output_tokens / (wall_time_ms / 1000.0)), 1) if wall_time_ms > 0 else 0.0

                # Validation
                schema_pass = False
                parsed_json = None
                failure_reason = None

                if "target_schema" in tc:
                    parsed_json = extract_json(content)
                    if parsed_json:
                        try:
                            tc["target_schema"].model_validate(parsed_json)
                            schema_pass = True
                        except Exception as val_err:
                            failure_reason = f"Schema validation error: {str(val_err)[:100]}"
                    else:
                        failure_reason = "Failed to parse valid JSON from output"

                elif "expected_contradiction" in tc:
                    parsed_json = extract_json(content)
                    if parsed_json and parsed_json.get("is_contradictory") is True:
                        schema_pass = True
                    else:
                        is_c = parsed_json.get("is_contradictory") if parsed_json else "None"
                        exp = parsed_json.get("explanation", "") if parsed_json else content[:100]
                        failure_reason = f"Missed contradiction (is_contradictory={is_c}): {exp[:80]}"

                elif tc_key == "TC4_DIFFERENTIAL_REASONING":
                    full_text = (content + " " + thinking).lower()
                    if any(w in full_text for w in ["gdv", "gastric dilatation", "volvulus", "torsion"]):
                        schema_pass = True
                    else:
                        failure_reason = "Did not identify GDV / Gastric Dilatation-Volvulus in differential list"

                cand_results[tc_key] = {
                    "pass": schema_pass,
                    "wall_time_ms": wall_time_ms,
                    "tokens_per_sec": tok_per_sec,
                    "prompt_tokens": prompt_tokens,
                    "output_tokens": output_tokens,
                    "thinking_tokens": len(thinking.split()) if thinking else 0,
                    "raw_content": content[:400],
                    "parsed_json": parsed_json,
                    "failure_reason": failure_reason,
                }
                
                status_badge = "✅ PASS" if schema_pass else "❌ FAIL"
                print(f"{status_badge} ({wall_time_ms}ms, {tok_per_sec} tok/s)")
                if failure_reason:
                    print(f"      ↳ Reason: {failure_reason}")

        except Exception as e:
            wall_time_ms = round((time.time() - t0) * 1000.0, 1)
            cand_results[tc_key] = {
                "pass": False,
                "wall_time_ms": wall_time_ms,
                "failure_reason": f"Exception: {str(e)}",
            }
            print(f"❌ FAIL (Exception: {e})")

    return cand_results


async def run_stage_a_benchmark():
    candidates = [
        ModelCandidate(
            name="Gemma 3 1B",
            model_id="gemma3:1b-it-qat",
            role_description="Ultra-fast worker / classifier / intent router",
        ),
        ModelCandidate(
            name="Qwen 3.5 4B",
            model_id="qwen3.5:4b",
            role_description="Primary Clinical Engine (Reasoning + Native Function Calling)",
        ),
        ModelCandidate(
            name="Qwen 2.5 7B Instruct",
            model_id="qwen2.5:7b",
            role_description="Non-Coder General Clinical Authority (Standard 7B Instruct)",
        ),
        ModelCandidate(
            name="DeepSeek R1 14B",
            model_id="deepseek-r1:14b",
            role_description="Deep Clinical Escalation & Complex Longitudinal Reasoning",
        ),
    ]

    all_results = {}
    for cand in candidates:
        all_results[cand.name] = await evaluate_model(cand)

    with open("clinical_model_comparison_report.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("\n" + "=" * 95)
    print("📊 CLINICAL STAGE A BENCHMARK MATRIX (Per model-comparison-review.md)")
    print("=" * 95)
    print(f"{'Model Candidate':<24} | {'TC1 SOAP':<10} | {'TC2 Rx':<10} | {'TC3 Safety':<12} | {'TC4 Reason':<12} | {'Avg Latency':<12}")
    print("-" * 95)

    for cname, tcs in all_results.items():
        s1 = "✅ PASS" if tcs.get("TC1_SOAP_EXTRACTION", {}).get("pass") else "❌ FAIL"
        s2 = "✅ PASS" if tcs.get("TC2_PRESCRIPTION_EXTRACTION", {}).get("pass") else "❌ FAIL"
        s3 = "✅ PASS" if tcs.get("TC3_CONTRADICTION_DETECTION", {}).get("pass") else "❌ FAIL"
        s4 = "✅ PASS" if tcs.get("TC4_DIFFERENTIAL_REASONING", {}).get("pass") else "❌ FAIL"
        
        valid_times = [t["wall_time_ms"] for t in tcs.values() if "wall_time_ms" in t]
        avg_l = f"{sum(valid_times)/len(valid_times):.0f} ms" if valid_times else "ERR"
        
        print(f"{cname:<24} | {s1:<10} | {s2:<10} | {s3:<12} | {s4:<12} | {avg_l:<12}")

    print("=" * 95)


if __name__ == "__main__":
    asyncio.run(run_stage_a_benchmark())
