Implement the next architecture-proof milestone: prove that Alamia Copilot is genuinely client/framework independent.

Create a SMALL STANDALONE SPA in a separate directory/process from the existing CopilotKit dashboard. It must consume the SAME Alamia Copilot runtime endpoint and must not import, reuse, or depend on the existing dashboard frontend.

OBJECTIVE:
Prove the protocol boundary, not just build another UI.

The standalone client must demonstrate:

1. Establish a Copilot session.
2. Send natural-language messages.
3. Receive and render streamed assistant events.
4. Invoke an Alamia Skill.
5. Receive tool/state updates.
6. Trigger an ActionProposal requiring HITL.
7. Receive the interrupt.
8. Submit approve/reject.
9. Observe the resulting state/mutation.
10. Work independently of the CopilotKit dashboard.

Also add a minimal RAW protocol test/client that demonstrates the actual wire contract independently of CopilotKit. Do not claim SSE = JSON-RPC automatically. Inspect the implementation and document the exact protocol, transport, request/response/event formats, session mechanism, and interrupt/approval flow actually used.

Then create comprehensive integration documentation explaining how an external application can integrate Alamia Copilot UI/runtime, including:

* CopilotKit/React
* Vue
* Angular
* Flutter
* Native/mobile
* WhatsApp/channel adapter

For each, clearly distinguish:
A) direct AG-UI/SSE client integration,
B) application/channel adapter integration,
C) anything requiring an additional bridge.

IMPORTANT:

* Do not weaken or modify core platform-independence.
* core/ must remain completely unaware of CopilotKit, React, Vue, Angular, Flutter, etc.
* Do not introduce CopilotKit Intelligence/cloud dependency.
* Reuse the existing AG-UI/runtime contracts rather than creating a parallel protocol.
* Do not make unsupported claims. Verify every protocol claim against the actual implementation.
* If a requested client type cannot directly consume the protocol, explicitly state that and document the required adapter/bridge.

Acceptance criteria:

1. Existing CopilotKit dashboard continues working.
2. Standalone SPA runs separately and independently.
3. Standalone SPA successfully performs chat + skill + streaming + HITL end-to-end.
4. Raw protocol client proves the wire-level contract without CopilotKit.
5. Documentation contains concrete setup/configuration steps, endpoint examples, message/event examples, authentication/session requirements, and architecture diagrams.
6. Documentation explicitly answers:
   "Can an external application integrate Alamia Copilot without using CopilotKit?"
   "Can CopilotKit consume Alamia without Alamia depending on CopilotKit?"
   "What exactly is reusable across React/Vue/Angular/Flutter/mobile?"
   "How does WhatsApp integrate, and is it direct or via an adapter?"
7. Add automated/integration tests for the protocol boundary where practical.

Finish with a concise VERIFICATION REPORT listing each claim as PASS / PARTIAL / FAIL and evidence for each. Do not declare success merely because the SPA renders; prove the end-to-end protocol interaction.
