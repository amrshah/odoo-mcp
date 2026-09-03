# Coding & Architecture Standards

## 1. Odoo 19 Module Standards
1. **Manifest Definitions:** Every custom module must provide a comprehensive `__manifest__.py` explicitly declaring `name`, `version` (`19.0.x.x.x`), `license` (`LGPL-3` or `OPL-1`), `depends`, `data`, and `application` flags.
2. **Model Naming Conventions:**
   - Technical model identifiers must use dot notation prefixed with domain: e.g. `vet.patient`, `vet.appointment`, `vet.treatment.plan`.
   - Python model classes should use PascalCase: e.g. `VetPatient`, `VetAppointment`.
3. **ORM Constraints & Invariants:**
   - Use Python `@api.constrains` for complex business validation (e.g. uniqueness of microchip numbers, valid date ranges).
   - Use SQL constraints for simple unique keys where possible.
4. **Security & Access Rights:**
   - Every model must have entries in `security/ir.model.access.csv`.
   - Business security groups must inherit from standard Odoo user groups (`base.group_user`).

---

## 2. FastMCP & Tool Standards
1. **Tool Signatures & Types:**
   - Every MCP tool function in `mcp-server/server.py` must have complete type annotations and descriptive docstrings explaining the model format, parameter types, and expected return structure.
2. **Error Handling & Sanitization:**
   - Tools must catch exceptions from the XML-RPC layer and return clean, structured JSON dictionaries with error descriptions instead of raw unhandled stack traces.
3. **Transport Independence:**
   - Code written for MCP tools must remain completely transport-agnostic, supporting both `stdio` and `SSE` without code changes.

---

## 3. Environment & Configuration Standards
1. **Never Hardcode Secrets:**
   - Database credentials, Odoo master secrets, and API keys must always be loaded via `.env` and `os.getenv()`.
2. **Port Allocation:**
   - Main Odoo HTTP: `8069`
   - Longpolling: `8072`
   - FastMCP Server: `8008` (avoids common collisions on port 8000).
