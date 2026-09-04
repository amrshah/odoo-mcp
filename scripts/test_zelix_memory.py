"""
Verification script for Zelix AI Learned Rules, Case Memory, and Settings
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp-server"))
from odoo_client import OdooClient


def test_zelix_features():
    client = OdooClient()
    uid = client.authenticate()
    print(f"[+] Authenticated as admin (UID: {uid})")

    # 1. Test creating a Learned Prescribing Rule
    meds = client.search_read("vet.medication", [], ["id", "name"], limit=1)
    if not meds:
        print("[!] No vet.medication found.")
        return

    med_id = meds[0]["id"]
    med_name = meds[0]["name"]
    print(f"[*] Found medication: {med_name} (ID: {med_id})")

    rule_id = client.create("zelix.ai.rule", {
        "trigger_keywords": "vomiting, gastroenteritis, nausea",
        "min_matches": 1,
        "scope": "doctor",
        "medication_id": med_id,
        "dosage": "16 mg",
        "frequency": "sid",
        "duration": "3 days",
        "reason": "First-line antiemetic protocol for acute dietary indiscretion",
    })
    print(f"[+] Successfully created Learned Rule ID: {rule_id}")

    # Read back rule
    rule = client.read("zelix.ai.rule", [rule_id], ["name", "scope", "trigger_keywords", "dosage", "frequency"])
    print(f"[+] Read-back rule: {rule[0].get('name')}")

    # 2. Test zelix.ai.rule.match_rules method
    matched_rules = client.execute_kw("zelix.ai.rule", "match_rules", ["Patient presented with acute vomiting and nausea"])
    print(f"[+] Rule matching test returned {len(matched_rules)} matched rule(s)")

    # 3. Create a Case Memory Record
    print("[*] Testing zelix.case.memory creation...")
    case_id = client.create("zelix.case.memory", {
        "age_band": "adult",
        "weight_kg": 28.4,
        "chief_complaint": "Acute vomiting x3 after table scraps",
        "keywords": "vomiting gastroenteritis nausea dietary indiscretion",
        "assessment": "Acute dietary gastroenteritis",
        "prescription_summary": '[{"medication": "Cerenia", "dosage": "16 mg", "frequency": "SID"}]',
    })
    print(f"[+] Successfully created Case Memory ID: {case_id}")

    # 4. Read back Case Memory Record
    case = client.read("zelix.case.memory", [case_id], ["chief_complaint", "assessment", "keywords"])
    print(f"[+] Read-back case memory: {case[0].get('chief_complaint')}")

    # 5. Test zelix.case.memory.find_similar_cases method
    similar = client.execute_kw("zelix.case.memory", "find_similar_cases", ["vomiting after eating scraps"])
    print(f"[+] Case memory similarity search returned {len(similar)} case(s)")
    print("[SUCCESS] All Zelix AI memory and prescribing rule models verified in Odoo 19!")


if __name__ == "__main__":
    test_zelix_features()
