I inspected the actual source at e19c640 in the standalone repository and checked the corresponding monorepo files at de9e197. I did not rely solely on the agent's report.
Remediation substantially complete
Not production-ready

1. Previous findings: verification results
Previous finding	Result	My assessment
Incorrect JSON-2 UID	Addressed	No longer invents UID 1 or returns an arbitrary user
Viewer wildcard permissions	Addressed	Explicit read/write model allowlists
Human identity vs Odoo service identity	Addressed	Documentation correctly distinguishes them
Missing API key fail-open	Addressed	Middleware now rejects missing configuration
Ordinary key comparison	Addressed	Uses hmac.compare_digest()
Streamable HTTP lifecycle	Addressed	Actual SDK integration tests added
Default execution policy	Addressed	READ_ONLY is now the configuration default
Version fallback	Addressed	No longer invents Odoo 19+
Maximum token TTL	Addressed	24-hour maximum
nbf validation	Addressed	Implemented

The changes are also present in the monorepo package. I verified the corresponding policy, adapter and live-test files rather than assuming synchronization succeeded.

Relevant commits:
- Standalone: e19c640
- Monorepo: de9e197
The reported 61 passing tests are encouraging, but I have not independently executed them. The GitHub commit status response also did not provide independent CI check results.
2. New findings from the actual source
There are still four things I would not ignore.
A. Critical: a live Odoo API key is hardcoded in the repository
Immediate action required
In tests/test_json2_live.py:
LIVE_ODOO_API_KEY = "c4f6ce9cbf49849cc832a377fbd96c6c8d4cd39c"



This is present in both repositories.

The same credential was also exposed in the previous hardening report. If it is a real Odoo API key, treat it as compromised.

Required actions:
1. Revoke the exposed API key in Odoo immediately.
2. Generate a replacement.
3. Load the key from an environment variable or secret store.
4. Make live tests skip unless explicit test credentials are provided.
5. Review Git history and remove the exposed credential from historical commits where practical.
Do not assume deleting the line in a new commit makes the old credential safe.
B. odoo_list_models() bypasses the new role matrix
In mcp/server.py, the tool still does this:
raw_models = adapter.list_models(filter_term=filter_term)filtered_models = [    m for m in raw_models    if m.get("model") not in cfg.disallowed_models]



There is no call to policy.check_read() and no filtering against the current principal's allowed_read_models.

Consequently:
- A viewer can discover models outside their permitted model list.
- A service identity with no read scope can still invoke model discovery.
- The returned model list is cached without a role-specific cache key.
This does not directly grant access to records, but it undermines the stated authorization boundary and leaks internal model metadata.

Fix: filter discovery results using the current principal's actual model permissions and service scopes. Include the authorization context in the cache key, or cache raw metadata internally and filter it separately for each caller.
C. Company context can be overridden
In json2.py:
if principal and principal.company_id and "context" not in body:    body["context"] = {        "allowed_company_ids": [principal.company_id]    }



This only injects the verified company when the payload does not already contain context.

But execute_method() accepts arbitrary named kwargs. A caller can potentially supply its own context, including a different allowed_company_ids value.

That undermines the intended company boundary.

Fix: enforce the principal's company restrictions rather than merely supplying a default. Reject or sanitize caller-provided allowed_company_ids so they cannot expand the verified company's scope.
D. Authentication semantics need one final clarification
The new JSON-2 authenticate() returns None after calling:
/json/2/res.partner/check_access_rights



This is better than manufacturing a UID. However, it couples credential verification to having read-access rights on res.partner.

A valid Odoo API key belonging to a restricted account could fail this check even though the credentials themselves are valid.

Separate these concepts:
- Is the API credential valid?
- Can this identity access the required Odoo model?
- What is the authenticated Odoo execution identity?
Also update the odoo_status() documentation, which still describes returning an authenticated user ID. The JSON-2 adapter now deliberately returns no numeric UID.
3. One additional security test I want
The policy tests now cover role boundaries, but I would add an end-to-end test proving that a caller cannot escape their company context.

For example:
- Signed principal has company_id=1.
- Caller attempts to execute an allowlisted method with context.allowed_company_ids=[2].
- Bridge rejects the request or safely constrains it to company 1.
- The Odoo request must never execute with company 2.
This is more meaningful than another isolated unit test because it validates the complete path from signed identity through JSON-2 request construction.

4. What I recommend now
Don't restart the hardening process. Most of the previous findings have been addressed.
Remaining corrective work
1. Revoke and remove the exposed API key.
2. Fix role-aware model discovery and caching.
3. Enforce company context against caller overrides.
4. Clarify JSON-2 authentication and status semantics.
5. Add the cross-company isolation integration test.

Then proceed to the ZelixVet pilot.

My strategic recommendation remains unchanged: Alamia OdooBridge should become the canonical Odoo connectivity layer for ZelixVet, TravelOS and Stratos HMS.

At this point, the biggest risk is no longer the basic bridge architecture. It is whether the security policy remains consistent across every exposed tool and every transport.

Do not spend another week adding features. Close these remaining gaps, then start integrating it into ZelixVet alongside the existing adapter.