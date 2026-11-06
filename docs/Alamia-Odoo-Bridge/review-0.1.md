Good progress. Proceed with Phase 0 and Phase 1 on `alamia-odoobridge`, keeping all changes isolated from the existing implementation.

A few additional engineering requirements:

1. **Expand the security scrub:** Review the entire repository for hardcoded credentials, secrets, insecure defaults and exposed configuration, not just `mcp-server/`. Rotate potentially exposed credentials and inspect Git history. Do not rewrite shared branch history without approval.

2. **Preserve functionality:** Extract the existing ten MCP tools without silently changing their names, argument schemas or response contracts. Maintain backward compatibility during migration.

3. **Security architecture:** Do not trust user_id, role or company_id supplied through arbitrary headers. Require authenticated service-to-service communication and verifiable principal claims. Enforce model, operation and record-level authorization.

4. **Destructive operations:** Disable generic unlink by default. Restrict arbitrary execute_method to an explicit method policy. Require appropriate authorization and confirmation for sensitive business operations.

5. **Transport:** Support stdio and Streamable HTTP as primary transports, retaining legacy SSE compatibility for existing integrations.

6. **Odoo connectivity:** Keep the adapter interface transport-independent. Plan for JSON-2 and legacy RPC, but do not assume arbitrary execute_kw calls can be automatically translated into JSON-2 requests.

7. **Testing:** Create dedicated unit, security and integration tests for the extracted package. Include negative authorization tests, concurrency tests, transport tests and a clean-install test.

8. **Avoid duplicated implementations:** The new package must become the canonical source of Odoo connectivity. Do not leave multiple independently maintained copies of OdooClient behind.

9. **Scope control:** Do not implement commercial licensing, multi-tenant dashboards, marketplaces, or advanced toolpacks during these phases.

Before completing Phase 1, provide:
- Final package tree.
- Files moved, changed and removed.
- Security findings and remediation evidence.
- Test results.
- Existing versus new MCP tool contract comparison.
- Remaining technical debt and blockers.

Do not merge into main. Keep the branch independently deployable until we verify ZelixVet integration and approve the migration.