The current reference dashboard is useful as the host application and should remain intact. However, the current implementation demonstrates Alamia Core/AG-UI capabilities rather than CopilotKit itself.

Now implement the actual CopilotKit integration as the next step.

GOAL:
Add a real CopilotKit-powered Copilot interface to the existing reference application so we can evaluate CopilotKit as the default Alamia Copilot UI/AG-UI adapter.

Requirements:

1. Add a visible CopilotKit chat interface/widget to the dashboard (preferably floating or right-side panel) that allows natural-language interaction with the reference application.

2. Connect CopilotKit to the existing Alamia runtime/AG-UI endpoint. Do NOT move Alamia business logic into CopilotKit.

3. The Copilot must be able to demonstrate at least:

   * "Show me customer 1001"
   * "What invoices are overdue?"
   * "Give me my daily operational briefing"
   * "Follow up on overdue payments"
   * "Switch/verify behavior based on my current role"

4. Tool/skill execution must continue through Alamia Core:
   CopilotKit → AG-UI → Alamia Runtime → Skills → Tools/Policies → result/action.

5. Demonstrate a mutation requiring HITL:
   Ask the Copilot to perform a payment follow-up or other confirmation-required action and show the approval/rejection interaction through the Copilot UI.

6. Keep the existing direct Skill Trigger buttons and AG-UI event inspector. They are useful for comparing:

   * direct skill invocation
   * natural-language Copilot invocation
   * underlying AG-UI events

7. Do NOT make CopilotKit a dependency of core/.
   CopilotKit must live under the appropriate frontend/adapter/reference-app boundary.

8. Do NOT introduce CopilotKit Intelligence/cloud dependency unless absolutely required. The spike must work with the locally running Alamia runtime.

9. Document the resulting architecture and explicitly identify:

   * what CopilotKit provides
   * what AG-UI provides
   * what Alamia Core provides
   * what remains custom Alamia functionality

10. Add a short feasibility verdict after implementation:

* Can CopilotKit be the default Alamia Copilot UI?
* Can Alamia Core remain completely CopilotKit-independent?
* Can another frontend consume the same AG-UI/runtime endpoint?
* What CopilotKit functionality would we still need to implement ourselves?

Acceptance criterion:
Opening http://localhost:8000 must show the existing reference dashboard PLUS an obvious working CopilotKit chat experience. A user should be able to accomplish the demonstrated skills through natural-language conversation rather than only clicking Skill Trigger buttons.
