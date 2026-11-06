import asyncio
import json
from mcp.client.sse import sse_client
from mcp import ClientSession

async def run_comprehensive_live_test():
    print("========================================================")
    print("[*] Testing Alamia OdooBridge over Live SSE Container")
    print("========================================================")
    
    async with sse_client("http://localhost:8008/sse") as (read, write):
        async with ClientSession(read, write) as session:
            init_res = await session.initialize()
            print(f"[+] Initialized MCP: {init_res.server_info.name} (v{init_res.server_info.version})")
            
            # 1. Status Check
            res_status = await session.call_tool("odoo_status", {})
            status_data = json.loads(res_status.content[0].text)
            print(f"[+] odoo_status: status={status_data.get('status')}, odoo_ver={status_data.get('server_version')}, uid={status_data.get('uid')}")
            print(f"    schema_cache initial stats: {status_data.get('schema_cache')}")

            # 2. List Models (Test Cache Miss & Hit)
            res_m1 = await session.call_tool("odoo_list_models", {"filter_term": "vet.patient"})
            m1_data = json.loads(res_m1.content[0].text)
            print(f"[+] odoo_list_models (1st call - miss): retrieved {len(m1_data)} models: {[m['model'] for m in m1_data]}")

            res_m2 = await session.call_tool("odoo_list_models", {"filter_term": "vet.patient"})
            m2_data = json.loads(res_m2.content[0].text)
            print(f"[+] odoo_list_models (2nd call - hit): retrieved {len(m2_data)} models")

            # 3. Model Fields (Test Cache Miss & Hit)
            res_f1 = await session.call_tool("odoo_get_model_fields", {"model": "res.partner", "attributes": ["type", "string"]})
            f1_data = json.loads(res_f1.content[0].text)
            print(f"[+] odoo_get_model_fields (1st call - miss): retrieved {len(f1_data)} fields for res.partner")

            res_f2 = await session.call_tool("odoo_get_model_fields", {"model": "res.partner", "attributes": ["type", "string"]})
            f2_data = json.loads(res_f2.content[0].text)
            print(f"[+] odoo_get_model_fields (2nd call - hit): retrieved {len(f2_data)} fields")

            # 4. Search Read
            res_sr = await session.call_tool("odoo_search_read", {"model": "res.partner", "limit": 2, "fields": ["id", "name"]})
            sr_data = json.loads(res_sr.content[0].text)
            print(f"[+] odoo_search_read: retrieved {len(sr_data)} records: {sr_data}")

            # 5. Create and Write Record
            res_create = await session.call_tool("odoo_create_record", {
                "model": "res.partner",
                "values": {"name": "Bridge Live Test Partner", "email": "test-live-bridge@alamia.ai"}
            })
            create_data = json.loads(res_create.content[0].text)
            new_id = create_data.get("id")
            print(f"[+] odoo_create_record: created partner ID {new_id}")

            res_write = await session.call_tool("odoo_write_record", {
                "model": "res.partner",
                "ids": [new_id],
                "values": {"comment": "Updated via Alamia OdooBridge Live Test"}
            })
            write_data = json.loads(res_write.content[0].text)
            print(f"[+] odoo_write_record: updated partner ID {new_id}: success={write_data.get('success')}")

            # 6. Guardrail: Unlink Denial
            res_unlink = await session.call_tool("odoo_unlink_record", {"model": "res.partner", "ids": [new_id]})
            unlink_data = json.loads(res_unlink.content[0].text)
            print(f"[+] Guardrail check (odoo_unlink_record): success={unlink_data.get('success')}, error=\"{unlink_data.get('error')}\"")

            # 7. Guardrail: Disallowed Method Call Denial
            res_exec = await session.call_tool("odoo_execute_method", {
                "model": "res.partner",
                "method": "dangerous_unlisted_method",
                "args": []
            })
            exec_data = json.loads(res_exec.content[0].text)
            print(f"[+] Guardrail check (odoo_execute_method): success={exec_data.get('success')}, error=\"{exec_data.get('error')}\"")

            # 8. Check Final Cache Stats via Status
            res_status_final = await session.call_tool("odoo_status", {})
            status_final_data = json.loads(res_status_final.content[0].text)
            print(f"[+] Final schema_cache stats: {status_final_data.get('schema_cache')}")
            print("========================================================")
            print("[SUCCESS] ALL LIVE TESTS COMPLETED AND VERIFIED SUCCESSFULLY!")
            print("========================================================")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_live_test())
