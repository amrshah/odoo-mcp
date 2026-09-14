Do one final production-readiness pass on the Zelix integration guide. Do NOT change Alamia Core architecture.

Fix these issues:

1. Clearly distinguish the two deployment models:
   A) Starter embedded/installed inside Odoo's Python environment, using Odoo ORM/session.
   B) Separate ZelixAI service, using Odoo API/MCP/XML-RPC as an adapter.
   Do not mix ORM examples with XML-RPC/REST claims. Recommend the appropriate model for ZelixVet.

2. Replace dynamic `f"vet.{entity_type}"` model resolution with an explicit allowlisted Odoo MODEL_MAP.

3. Do not expose generic create/update/delete as AI capabilities. Show explicit domain mutation tools such as `create_soap_draft`, `confirm_soap_note`, etc.

4. Remove fabricated SOAP clinical facts from examples. Show transcript → AI structured SOAP draft → veterinarian review → ActionProposal → explicit confirmation → Odoo persistence → audit.

5. Document that AI-generated clinical content is ALWAYS a draft until explicitly confirmed by an authorized veterinarian. No autonomous clinical-record mutation, diagnosis, prescribing, or treatment changes.

6. Add the voice integration contract: Audio → pluggable SpeechToTextProvider → transcript → ZelixAI skill. STT provider must remain replaceable.

7. Make authentication/security explicit: user identity, tenant/clinic, role and permissions MUST be derived server-side from the authenticated Odoo context. Never trust role/tenant/user values supplied by the client.

8. Add Odoo record-level access/security considerations: Alamia policy checks do not replace Odoo ACLs/record rules; final Odoo operation must execute under the correct authenticated user/security context.

9. Change claims such as "100% ready" to "integration contract ready / Starter ready for external application implementation." Tests prove Starter behavior, not successful integration with an arbitrary Odoo deployment.

10. Add a concrete Zelix acceptance test using the existing ZelixVet Odoo deployment: authenticate as veterinarian → open/select patient → ask Patient 360 → retrieve real Odoo data → provide voice/audio → generate structured SOAP draft → edit/review → confirm → persist → verify audit. Also verify a non-veterinarian/read-only user cannot perform the clinical mutation.

11. Keep the guide platform-independent: veterinary/Odoo specifics belong in the ZelixAI integration layer, not Alamia Core.

At the end, produce a concise "What Zelix developers implement vs what Alamia Starter provides" table and a final handoff checklist.
