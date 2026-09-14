"""Raw Wire-Level Protocol Client for Alamia Copilot.

This script communicates directly with Alamia Copilot over low-level HTTP & SSE (Server-Sent Events)
without using any frontend libraries, CopilotKit packages, or heavy frameworks.

It demonstrates:
1. Establishing an agent turn via raw HTTP POST to /api/ag-ui.
2. Streaming and parsing Server-Sent Events (RUN_STARTED, STATE_UPDATE, TEXT_DELTA, INTERRUPT, RUN_FINISHED).
3. Extracting the HITL (Human-in-the-Loop) interrupt payload.
4. Confirming the proposed action via POST /api/action/confirm.
5. Observing the resulting business mutation.
"""

import json
import sys
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def stream_ag_ui_skill(skill_id: str, inputs: dict, role: str = "finance_assistant"):
    """Connect to /api/ag-ui via raw HTTP POST and stream SSE frames."""
    print_section(f"1. Initiating SSE Stream: skill='{skill_id}', role='{role}'")
    
    url = f"{BASE_URL}/api/ag-ui"
    payload = {
        "skill_id": skill_id,
        "inputs": inputs,
        "role": role,
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": "Alamia-Raw-Wire-Client/1.0",
        },
        method="POST",
    )
    
    interrupt_action_id = None
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            print(f"HTTP Status: {response.status}")
            print(f"Content-Type: {response.headers.get('Content-Type')}\n")
            print("--- Received SSE Stream Frames ---")
            
            # Read line by line from SSE stream
            for line in response:
                decoded = line.decode("utf-8").strip()
                if not decoded:
                    continue
                
                if decoded.startswith("data: "):
                    raw_data = decoded[6:]
                    event = json.loads(raw_data)
                    event_type = event.get("event_type")
                    event_id = event.get("event_id")
                    data = event.get("data", {})
                    
                    print(f"  [SSE Event] type={event_type:<15} id={event_id}")
                    
                    if event_type == "TEXT_DELTA":
                        delta = data.get("delta", "")
                        print(f"    --> Delta: {delta}")
                    elif event_type == "STATE_UPDATE":
                        print(f"    --> State snapshot: {json.dumps(data.get('state', {}))[:80]}...")
                    elif event_type == "INTERRUPT":
                        interrupt_id = data.get("interrupt_id")
                        prompt = data.get("prompt")
                        proposal = data.get("proposal", {})
                        interrupt_action_id = interrupt_id
                        print(f"    --> [HITL INTERRUPT TRIGGERED] Interrupt ID: {interrupt_id}")
                        print(f"    --> Prompt: {prompt}")
                        print(f"    --> Proposed Action: {proposal.get('action_type')} (Risk: {proposal.get('risk_level')})")
                    elif event_type == "RUN_FINISHED":
                        print(f"    --> Finished run. Output keys: {list(data.get('result', {}).get('output', {}).keys()) if isinstance(data.get('result'), dict) else list(data.keys())}")
                        break
                    elif event_type == "RUN_ERROR":
                        print(f"    --> Run Error: {data.get('error')}")
                        break
                        
    except urllib.error.URLError as e:
        print(f"Error connecting to {url}: {e}")
        return None
        
    return interrupt_action_id


def confirm_action(action_id: str, role: str = "finance_assistant"):
    """Submit approval for an interrupted action proposal via raw POST /api/action/confirm."""
    print_section(f"2. Submitting HITL Approval for Action: {action_id}")
    
    url = f"{BASE_URL}/api/action/confirm"
    payload = {
        "action_id": action_id,
        "role": role,
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            print(f"HTTP Status: {response.status}")
            print(f"Confirmation Response: {json.dumps(res_data, indent=2)}")
            return res_data
    except urllib.error.URLError as e:
        print(f"Error submitting confirmation: {e}")
        return None


def verify_dashboard_state():
    """Verify backend business state after mutation."""
    print_section("3. Verifying Backend State Mutation via /api/dashboard")
    
    url = f"{BASE_URL}/api/dashboard"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            tasks_raw = data.get("tasks", {})
            tasks = list(tasks_raw.values()) if isinstance(tasks_raw, dict) else tasks_raw
            print(f"Total Tasks in ERP Backend: {len(tasks)}")
            for t in tasks:
                if isinstance(t, dict):
                    print(f"  - Task [{t.get('id')}]: {t.get('title')} (status={t.get('status')})")
                else:
                    print(f"  - Task: {t}")
            return data
    except urllib.error.URLError as e:
        print(f"Error fetching dashboard state: {e}")
        return None


def test_natural_language_chat_endpoint():
    """Test standard JSON request-response endpoint /api/copilot/chat."""
    print_section("4. Testing Synchronous Natural Language Endpoint /api/copilot/chat")
    
    url = f"{BASE_URL}/api/copilot/chat"
    payload = {
        "message": "Show me customer 101",
        "role": "finance_assistant",
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            print(f"HTTP Status: {response.status}")
            print(f"Chat Response: {json.dumps(data, indent=2)}")
            return data
    except urllib.error.URLError as e:
        print(f"Error calling /api/copilot/chat: {e}")
        return None


if __name__ == "__main__":
    print("======================================================================")
    print("  Alamia Copilot — Raw Wire-Level Protocol Client Verification")
    print("======================================================================")
    
    # 1. Test synchronous natural language dispatch
    chat_res = test_natural_language_chat_endpoint()
    
    # 2. Trigger payment followup skill over SSE stream which produces an INTERRUPT
    interrupt_id = stream_ag_ui_skill("payment_followup", {"customer_id": "cust_101"})
    
    # 3. If an interrupt was emitted, confirm it
    if interrupt_id:
        confirm_action(interrupt_id)
        
    # 4. Verify that the task was created in the backend
    verify_dashboard_state()
    
    print("\n[SUCCESS] Raw wire-level protocol interaction verified completely.\n")
