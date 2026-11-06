# Alamia OdooBridge — review of the latest hardening report

This is a substantial improvement over the previous `350f113` version. The agent has addressed the main issues I raised: JSON-2 payload contracts, service-account scopes, declarative role policies, SSE identity propagation, and adapter auto-selection.

My verdict: move to a controlled integration pilot, but do not call this production-ready yet.

The strongest evidence in this report is the live Odoo 19 CRUD test and the real MCP SDK SSE tests. Those are materially better than mocked unit tests. However, there are still important security and verification questions.

## What is genuinely improved

| Area                     | Assessment                                                                                |
| ------------------------ | ----------------------------------------------------------------------------------------- |
| JSON-2 payloads          | Corrected to named parameters for create, write, unlink, fields_get and search operations |
| JSON-2 live tests        | Good evidence: actual Odoo 19 CRUD lifecycle, not just mocked responses                   |
| Service scopes           | Meaningful improvement; default service identity is read-only                             |
| Role/action/model policy | Better structure than the previous hardcoded role exclusions                              |
| SSE middleware           | Pure ASGI is a sensible fix for streaming compatibility                                   |
| Replay protection        | Session-aware handling is better than one-time token rejection                            |
| Adapter selection        | AUTO now probes JSON-2 and falls back to XML-RPC                                          |

The report records 54 passing tests in both repositories, 4 live JSON-2 tests, and 5 MCP SDK SSE tests. Those are agent-reported results; I have not independently executed the test suites or reproduced the live Odoo environment.&#x20;

Pasted text(20261106-094959).txt



## Issues I found in the actual committed code

I inspected the files at commit `4e7d58d`, not just the report. These are the remaining problems I would address.

### 1. `authenticate()` does not reliably return the authenticated user's UID

Correctness issue

In `json2.py`, authentication calls:

```
/json/2/res.users/search_read
```

with an empty domain and `limit: 1`, then returns the ID of the first user record returned.

That is not necessarily the UID of the user authenticated by the API key. It is a query against user records, not a reliable current-user identity endpoint. The fallback `return 1` makes the situation worse because it can report a successful-looking UID when no record was returned.

Required fix: use a verified current-user identity mechanism. If JSON-2 does not expose one directly, do not pretend to know the UID. Return an authenticated status with an explicitly unknown UID instead.

### 2. The viewer role is much broader than its description

Authorization issue

The code defines:

```
"viewer": {    "allowed_actions": ["read"],    "allowed_models": ["*"],    "denied_models": [        "account.*",        "res.users",    ],}
```

This does not mean "business models only." It means almost every model is readable except the two denied patterns and the global exact-name denylist.

For example, `res.company` is not denied for viewers by this role or by the current global `disallowed_models` list.

The report's security matrix describes a narrower permission set than the implementation actually enforces.

Required fix: define an explicit business-model allowlist for viewer access. Apply the same principle to every role: access should be granted by explicit permission, not by an increasingly large collection of exclusions.

### 3. Company context is not human-level authorization

Important boundary

The JSON-2 adapter propagates:

```
{"allowed_company_ids": [principal.company_id]}
```

This is useful context propagation, but it does not impersonate the human user or establish that the human is entitled to access those records.

Odoo still evaluates access under the Odoo API-key account. If that account has broad permissions, the bridge's role policy and company handling must provide the additional isolation.

The report correctly says Odoo ACLs and record rules remain authoritative. However, those rules apply to the Odoo execution identity, not automatically to the signed human principal.

Required fix: document this distinction clearly and test cross-company access using the actual service account and representative records. Never describe `user_id` propagation as Odoo user impersonation.

### 4. API-key middleware still has a fail-open configuration

In `auth.py`:

```
if self.enforce_api_key and self.api_key:
```

If enforcement is enabled but the API key is missing, the middleware skips the check.

The CLI may prevent this particular configuration, but the middleware itself should not depend on the CLI to remain secure.

Required fix: when `enforce_api_key=True`, reject startup or requests if no API key is configured. Also use constant-time comparison for the supplied key.

### 5. Streamable HTTP replay handling remains unproven

The report demonstrates real SSE compatibility, which is good. But the token logic explicitly recognizes an SSE handshake.

For Streamable HTTP, an initial POST without a session ID can be treated as a non-session request. Reusing the same token on subsequent requests can then trigger replay rejection.

The report does not establish Streamable HTTP compatibility.

Required fix: test the actual Streamable HTTP lifecycle with the official MCP SDK, including initialization, repeated tool calls, session headers, concurrent sessions, and token expiry. Do not assume SSE test results prove Streamable HTTP works.

### 6. Default execution policy contradicts the report

The report says remote deployments default to read-only unless write access is deliberately configured.

But `config.py` currently says:

```
execution_policy: ExecutionPolicy = Field(    default=ExecutionPolicy.CONTROLLED_WRITES,    alias="BRIDGE_EXECUTION_POLICY")
```

Service-only identities are protected by the default read scope, but signed human identities can still perform permitted writes under the default policy.

That is not the same as a read-only default.

Required fix: make the documented deployment default and actual configuration agree. I would use `READ_ONLY` for a fresh remote deployment.

### 7. Other details worth correcting

- `get_version()` falls back to a hardcoded `"19.0+"` when it cannot obtain version information. It should report an unknown version rather than potentially misrepresenting the server.
- `PrincipalVerifier` has no maximum token lifetime. A trusted issuer can create unnecessarily long-lived tokens. Add a maximum TTL.
- The verifier does not validate a `nbf` claim. Either implement it or remove any implication that it is checked.
- The role matrix's `"admin"` role is effectively unrestricted across all models and methods at the bridge policy level. Ensure only a tightly controlled identity issuer can grant it.
- The `doctor` role has write access to `mail.*`, `product.*`, and `calendar.*`. Review whether those broad permissions are genuinely needed for ZelixVet.

## My revised assessment

Overall implementation

# 8/10

| Area                  | Assessment |
| --------------------- | ---------- |
| Architecture          | 9/10       |
| JSON-2 implementation | 8.5/10     |
| Authentication        | 8/10       |
| Authorization         | 6.5/10     |
| MCP compatibility     | 7.5/10     |
| Production readiness  | Not yet    |

The score reflects the code and report available at this commit, not an independent security certification.

## What I would do next

Do not start another large development phase. The bridge is now mature enough to test against a real product integration, but first close the specific issues above.

My recommended sequence:

1. Small corrective pass: fix UID identification, viewer permissions, fail-closed API-key enforcement, default execution policy, and token validation.
2. Streamable HTTP verification: test the actual transport, not just SSE.
3. ZelixVet controlled pilot: integrate the bridge alongside the existing direct Odoo adapter.
4. Side-by-side comparison: run the same read, create, update, business-method and authorization scenarios through both implementations.
5. Switch connectivity only after parity: retain the old adapter until the new bridge passes the regression suite.

The architectural boundary remains important: Alamia OdooBridge should own Odoo connectivity, authentication, policy enforcement, execution and auditing. ZelixVet should own veterinary workflows and business rules. Don't turn the bridge into another agent framework.

My recommendation: keep `4e7d58d` as the current development baseline. Do not merge it into the ZelixVet production path yet, but stop expanding its feature set. Close the security and identity gaps, then begin the controlled pilot.