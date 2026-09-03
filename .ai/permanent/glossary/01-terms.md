# Project Glossary

| Term | Definition |
|---|---|
| **MCP (Model Context Protocol)** | An open protocol developed by Anthropic allowing AI assistants to interact securely with external tools and data sources. |
| **FastMCP** | High-level Python framework for building MCP servers with automatic schema generation for LLMs. |
| **Odoo.sh** | Odoo's managed cloud hosting platform integrated with GitHub repositories for continuous integration and branch-based staging/production environments. |
| **VetCairn** | Complete veterinary practice management suite for Odoo covering clinical, diagnostic, appointment, pharmacy, and hospital operations. |
| **Clinical Encounter** | A medical consultation session (`vet.encounter`) capturing chief complaints, physical exam findings, diagnoses, and SOAP notes. |
| **Provider** | A veterinary clinician or doctor (`res.users` / `res.partner`) responsible for clinical appointments and medical procedures. |
| **Domain Filter** | Odoo's Polish notation criteria list for filtering ORM recordsets (e.g., `[("state", "=", "confirmed"), ("clinic_id", "=", 3)]`). |
| **XML-RPC** | Standard external API protocol supported by Odoo core across all versions (`/xmlrpc/2/common` and `/xmlrpc/2/object`). |
| **SSE (Server-Sent Events)** | HTTP transport mode for MCP enabling streaming bidirectional-capable tool interactions over network ports. |
