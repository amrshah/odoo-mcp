# AI Workspace Instructions (AGENTS.md)

This file contains the foundational rules for all AI agents working in this repository. It is automatically injected into the context of every new conversation.

## 1. The AI Bootstrap Sequence
If you are entering a fresh conversation and do not have full context of this project, you **MUST NOT** immediately inspect the source code or reverse engineer the repository. 

Instead, you must strictly follow this read order:
1. Read .ai/README.md (Master Index)
2. Read .ai/transient/sprint/00-current-state.md
3. Read .ai/permanent/architecture/01-system-architecture.md
4. Read .ai/indexes/repository.md to map concepts to code.
5. Only then may you inspect the source code.

## 2. Documentation Ownership (Knowledge Manager)
- The documentation in .ai/ is strictly maintained by the **Knowledge Manager** agent. 
- If you (the Developer agent) modify the architecture, database models, workflows, or APIs, you must either update the docs yourself, or delegate to the Knowledge Manager.
- Never summarize source code in documentation. Document *intent, invariants, tradeoffs, and failure modes*.

## 3. Strict Zero-Touch VPS Deployment (Zero SSH / Terminal)
- **NEVER** instruct, suggest, or execute SSH, bash, or manual terminal commands on the production VPS.
- All container updates, module installations (`-i`), upgrades (`-u`), and database initializations MUST be completely automated via `docker-entrypoint.sh`, Dockerfiles, self-healing scripts (`setup_odoo_mcp_orm.py`), and Portainer stack redeployments.

## 4. Alamia White-Label Branding Invariant
- All user-facing views, OWL 2 components, Odoo settings (`res.config.settings`), cards, and alerts MUST use the **Alamia** brand name (e.g., *"Alamia AI Gateway & Edge Workers"*, *"Alamia AI Model"*).
- NEVER expose third-party vendor names (such as "Cloudflare", "OpenAI", etc.) in clinician or user interfaces. Use "CF" only when unavoidable in internal code identifiers or field technical names.

## 5. Zero-Configuration Environment Auto-Provisioning
- Credentials and configurations supplied via Portainer / Docker compose environment variables MUST automatically activate and provision the underlying Odoo models and `ir.config_parameter` on container startup without requiring manual entry in Odoo settings.
- Model clients MUST include direct `os.getenv()` fallback chains for high availability.

## 6. Free-Tier Edge Inference Constraint
- All edge gateway integrations must operate strictly within the zero-cost free tier (e.g. Cloudflare Workers AI 10,000 daily neurons).
- Always use active model tags (e.g., `@cf/meta/llama-3.1-8b-instruct-fp8`) and strip internal `<think>` reasoning tags from model outputs before presenting to clinical workflows.
