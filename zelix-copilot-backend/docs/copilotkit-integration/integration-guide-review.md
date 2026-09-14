Review docs/integration/client-integration-guide.md and correct the guide before considering it final.

The architecture is good, but several claims currently blur REST, AG-UI, SSE, and JSON-RPC. Make the documentation technically precise.

Required corrections:

1. REMOVE "JSON-RPC" unless the implementation actually implements JSON-RPC. Do not call SSE payloads JSON-RPC. Clearly distinguish:

   * Alamia REST/HTTP JSON API
   * AG-UI event stream
   * SSE transport
   * JSON-RPC only if genuinely implemented.

2. Correct `/api/ag-ui` documentation to explicitly state HTTP request method, request Content-Type, response Content-Type, streaming behavior, and actual event format based on the implementation.

3. Verify that the emitted events are actually compliant with the AG-UI protocol/schema rather than merely Alamia-defined events with similar names. Document the exact AG-UI version/subset implemented. Do not claim full protocol compatibility if only a subset is implemented.

4. Split the integration guide into two clear paths:
   A. Simple REST integration: POST /api/copilot/chat → JSON response.
   B. Streaming AG-UI integration: client → AG-UI endpoint → SSE event stream.
   Explain when each should be used.

5. Verify the CopilotKit example against the actual installed CopilotKit version and confirm that the shown runtimeUrl and protocol are genuinely compatible.

6. SECURITY CRITICAL:
   Remove examples where the client declares its authoritative role using:
   {"role":"finance_assistant"}.
   Client-provided role/user/tenant/permission data must NEVER be trusted for authorization.
   Document an authenticated integration context (token/session/etc.) from which Alamia derives user_id, tenant_id, role and permissions server-side.
   The backend PolicyEngine remains the sole authorization authority.

7. Explicitly document tenant isolation and EmployeeContext derivation.

8. Replace absolute security claims:

   * "zero duplicate transactions" → explain idempotency/deduplication guarantees actually implemented.
   * "tamper-proof audit records" → use "append-only/immutable audit records" unless cryptographic tamper evidence is actually implemented.

9. For WhatsApp/Slack/Telegram, explicitly classify them as channel adapters/bridges, not direct AG-UI clients. Show identity mapping from the channel identity to authenticated Alamia user/tenant context.

10. Add a protocol compatibility table:
    Client | Direct REST | Direct AG-UI | Requires Adapter | Notes

11. Add a "Verified vs Planned" section. Every capability claimed in the guide must be either demonstrated by the standalone integration test or clearly marked as planned/not yet implemented.

12. Add concrete curl examples for:

    * authenticated REST request
    * authenticated AG-UI request
    * HITL approval/rejection
      using the actual API contract.

Do not redesign Alamia Core. This is a documentation and contract-accuracy pass.

FINAL REQUIREMENT:
Do not declare "Any client can connect" as a blanket statement. State the precise, verified claim: any client capable of implementing the documented HTTP/JSON + AG-UI/SSE contract can integrate without a proprietary SDK, while channel platforms such as WhatsApp require an adapter.
