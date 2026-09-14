# How to Kickstart Your Vertical AI Copilot from Alamia Copilot Starter

This guide explains how external development teams (such as the **ZelixVet** team building **ZelixAI** or the **TravelOS** team building **TravelOS AI**) fork the **Alamia AI Copilot Starter** template repository and build their vertical domain Copilot on top of it.

---

## 1. The Template Forking Paradigm

The Starter is designed to be **cloned / forked**, giving each product team complete code ownership, rapid development velocity, and total flexibility to add custom domain entities, workflows, and integrations without polluting the generic upstream foundation.

```text
               ALAMIA COPILOT STARTER
                  (Template Base)
                         │
               clone / fork / copy
                         │
           ┌─────────────┴─────────────┐
           ▼                           ▼
       ZelixAI                     TravelOS AI
       Copilot                       Copilot
    (Veterinary / Odoo)         (Travel / Operations)
```

### Clean Core vs. Product Extension Layer
When you fork the Starter for your project (e.g. `ZelixAI-Copilot/`):

```text
ZelixAI-Copilot/
├── core/                       # Inherited generic foundation (KEEP PLATFORM-NEUTRAL)
│   ├── runtime/                # CopilotEngine turn lifecycle & session management
│   ├── skills/                 # BaseSkill, SkillRegistry
│   ├── tools/                  # BaseTool, ToolRegistry
│   ├── policies/               # Deterministic PolicyEngine (RBAC & Risk)
│   ├── actions/                # ActionProposal & HITL StateMachine
│   ├── audit/                  # Append-only structured audit logger
│   └── ai/                     # AI provider & router abstraction
│
├── adapters/
│   └── odoo/                   # YOUR Odoo 19 XML-RPC / ORM adapter
│
├── skills/
│   └── veterinary/             # YOUR Veterinary Skills (patient_360, voice_to_soap)
│
├── tools/
│   └── veterinary/             # YOUR Veterinary Tools (get_patient, get_vaccinations)
│
├── policies/
│   └── clinical/               # YOUR Clinical Policies (medical mutation review gates)
│
├── voice/                      # YOUR Pluggable Voice / STT Providers (Whisper, Deepgram)
│
└── frontend/                   # YOUR UI Components (Odoo OWL widget / CopilotKit panel)
```

> **The Golden Rule**: Extend around the core. Modify `core/` only when introducing a capability that is genuinely domain-agnostic (e.g., enhanced memory types or streaming event schemas) and should be contributed back upstream to the Starter template.

---

## 2. 10-Step Kickoff Contract for Developers

```text
1. Clone / Fork Starter ──► 2. Configure Environment ──► 3. Implement ApplicationAdapter
                                                                   │
8. Wire Auth Context   ◄── 7. Pluggable Voice / STT  ◄── 6. Domain Skills & Tools
        │
        ▼
9. Connect UI (AG-UI)  ──► 10. Run Test Suite
```

---

### Step 1: Clone / Fork the Starter
```bash
git clone https://github.com/Alamia/AlamiaAICopilot-Starter.git ZelixAI-Copilot
cd ZelixAI-Copilot
```

---

### Step 2: Configure Environment
```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

---

### Step 3: Implement `ZelixOdooAdapter` with Explicit Allowlist
Create your database/API connector under `adapters/odoo/` by subclassing [`ApplicationAdapter`](file:///e:/Alamia/AlamiaAICopilot-Starter/adapters/application/base/adapter.py). **Never use dynamic string interpolation for model names.** Use an explicit allowlist:

```python
"""adapters/odoo/zelix_odoo_adapter.py"""
import xmlrpc.client
from typing import Any, Dict, List, Optional
from adapters.application.base.adapter import ApplicationAdapter

class ZelixOdooAdapter(ApplicationAdapter):
    """Bridges Copilot Engine to Odoo 19 via XML-RPC / API."""

    MODEL_MAP = {
        "patient": "vet.patient",
        "vaccination": "vet.vaccination",
        "encounter": "vet.encounter",
        "appointment": "vet.appointment",
    }

    def __init__(self, url: str, db: str, user_id: int, api_key: str) -> None:
        self.url = url
        self.db = db
        self.user_id = user_id
        self.api_key = api_key
        self.models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def _get_model(self, entity_type: str) -> str:
        model = self.MODEL_MAP.get(entity_type.lower())
        if not model:
            raise ValueError(f"Entity type '{entity_type}' is not allowlisted.")
        return model

    def get(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        model = self._get_model(entity_type)
        try:
            records = self.models.execute_kw(
                self.db, self.user_id, self.api_key,
                model, "read", [[int(entity_id)]]
            )
            return records[0] if records else None
        except Exception:
            return None

    def search(self, entity_type: str, query: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[Dict[str, Any]]:
        model = self._get_model(entity_type)
        domain = [[k, "=", v] for k, v in (query or {}).items()]
        return self.models.execute_kw(
            self.db, self.user_id, self.api_key,
            model, "search_read", [domain], {"limit": limit}
        )

    def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        model = self._get_model(entity_type)
        rec_id = self.models.execute_kw(
            self.db, self.user_id, self.api_key,
            model, "create", [data]
        )
        return {"id": rec_id, "status": "created"}

    def relationships(self, entity_type: str, entity_id: str, relationship_name: str) -> List[Dict[str, Any]]:
        if entity_type == "patient" and relationship_name == "vaccinations":
            return self.search("vaccination", {"patient_id": int(entity_id)})
        return []
```

---

### Step 4: Implement Domain Tools (No Generic Raw CRUD)
Create deterministic domain tools under `tools/veterinary/` by extending [`BaseTool`](file:///e:/Alamia/AlamiaAICopilot-Starter/core/tools/base.py):

```python
"""tools/veterinary/patient_tools.py"""
from typing import Any, Dict, List, Optional
from core.tools.base import BaseTool
from core.tools.definition import ToolDefinition
from core.sessions.context import EmployeeContext
from adapters.odoo.zelix_odoo_adapter import ZelixOdooAdapter

class GetPatientRecordTool(BaseTool):
    def __init__(self, adapter: ZelixOdooAdapter) -> None:
        self.adapter = adapter

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_patient_record",
            description="Fetches medical record, species, breed, and alerts for a patient.",
            parameters={"patient_id": {"type": "string"}},
            required_permissions=["patients.read"],
            risk_level="LOW",
        )

    def execute(self, context: EmployeeContext, **kwargs: Any) -> Optional[Dict[str, Any]]:
        return self.adapter.get("patient", kwargs.get("patient_id"))

class GetVaccinationHistoryTool(BaseTool):
    def __init__(self, adapter: ZelixOdooAdapter) -> None:
        self.adapter = adapter

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_vaccination_history",
            description="Retrieves administered vaccinations, batch numbers, and booster due dates.",
            parameters={"patient_id": {"type": "string"}},
            required_permissions=["medical_records.read"],
            risk_level="LOW",
        )

    def execute(self, context: EmployeeContext, **kwargs: Any) -> List[Dict[str, Any]]:
        return self.adapter.relationships("patient", kwargs.get("patient_id"), "vaccinations")
```

---

### Step 5: Implement Domain Skills & SOAP Workflow
Create vertical skills under `skills/veterinary/` by extending [`BaseSkill`](file:///e:/Alamia/AlamiaAICopilot-Starter/core/skills/base.py):

```python
"""skills/veterinary/soap_skill.py"""
import json
from typing import Any, Dict, Optional
from core.skills.base import BaseSkill, SkillResult
from core.skills.definition import SkillDefinition
from core.sessions.context import EmployeeContext
from core.actions.proposal import ActionProposal, RiskLevel

class VoiceToSoapSkill(BaseSkill):
    """Converts clinical dictation into a structured SOAP draft requiring vet confirmation."""

    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            id="voice_to_soap",
            name="Voice-to-SOAP Clinical Note Draft",
            description="Transcribes clinical audio and structures findings into a SOAP draft.",
            required_tools=["get_patient_record"],
            risk_level="HIGH",
            allowed_roles=["veterinarian"],
        )

    def execute(
        self,
        context: EmployeeContext,
        tools: Dict[str, Any],
        ai_provider: Optional[Any] = None,
        **kwargs: Any
    ) -> SkillResult:
        patient_id = str(kwargs.get("patient_id"))
        transcript = kwargs.get("transcript", "")

        patient = tools["get_patient_record"].execute(context, patient_id=patient_id)
        if not patient:
            return SkillResult(success=False, skill_id=self.definition.id, error=f"Patient '{patient_id}' not found.")

        # Structured findings (AI synthesis)
        structured_soap = {
            "subjective": "Alert, active, no vomiting or diarrhea reported.",
            "objective": "Weight: 14.2kg, Temp: 38.5C, HR: 110 bpm, Mucous membranes pink.",
            "assessment": "Healthy adult canine, routine preventative exam.",
            "plan": "Administer DHPP booster, dispense 6-month flea/tick preventative.",
        }

        # Human-in-the-Loop Confirmation Proposal
        proposal = ActionProposal(
            action_id=f"act_soap_patient_{patient_id}",
            action_type="create_soap_encounter",
            idempotency_key=f"soap_draft_{patient_id}_run_{context.conversation_id or 'default'}",
            target={"type": "patient", "id": patient_id},
            reason=f"Add clinical SOAP note for patient {patient.get('name', patient_id)}.",
            proposed_changes={
                "patient_id": int(patient_id),
                "summary": "Annual Wellness Exam",
                "notes": json.dumps(structured_soap),
            },
            risk_level=RiskLevel.HIGH,
            required_permission="medical_records.write",
            requires_confirmation=True,
            created_by=context.user_id,
        )

        return SkillResult(
            success=True,
            skill_id=self.definition.id,
            output={
                "status": "draft_awaiting_review",
                "patient_name": patient.get("name"),
                "soap_draft": structured_soap,
            },
            proposed_actions=[proposal.model_dump()],
        )
```

---

### Step 6: Configure Clinical Policies & Bootloader
Assemble your Copilot in `main.py`:

```python
"""main.py — ZelixAI Bootloader."""
from core.runtime.engine import CopilotEngine
from core.skills.registry import SkillRegistry
from core.tools.registry import ToolRegistry
from core.roles.registry import RoleRegistry
from core.roles.manifest import RoleManifest
from adapters.odoo.zelix_odoo_adapter import ZelixOdooAdapter
from tools.veterinary.patient_tools import GetPatientRecordTool, GetVaccinationHistoryTool
from skills.veterinary.soap_skill import VoiceToSoapSkill

adapter = ZelixOdooAdapter(url="https://zelix.alamiaconnect.com", db="zelix_prod", user_id=2, api_key="env_api_key")

tools = ToolRegistry()
tools.register(GetPatientRecordTool(adapter))
tools.register(GetVaccinationHistoryTool(adapter))

skills = SkillRegistry()
skills.register(VoiceToSoapSkill())

roles = RoleRegistry()
roles.register(RoleManifest(
    id="veterinarian",
    name="Licensed Veterinarian",
    skills=["voice_to_soap"],
    permissions=["patients.read", "medical_records.read", "medical_records.write"],
))

engine = CopilotEngine(
    skill_registry=skills,
    tool_registry=tools,
    role_registry=roles,
    application_adapter=adapter,
)

# Mandatory HITL confirmation gate on clinical encounter creation
engine.policies.confirmation_policy.always_require_confirmation_actions.add("create_soap_encounter")
```

---

### Step 7: Pluggable Voice / Speech-to-Text (STT) Contract
Decouple audio transcription via a swappable STT provider under `voice/`:

```python
"""voice/stt_provider.py"""
from abc import ABC, abstractmethod

class BaseSpeechToTextProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        """Transcribe audio bytes to text."""
        pass

class WhisperSTTProvider(BaseSpeechToTextProvider):
    def __init__(self, client: Any = None) -> None:
        self.client = client

    def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        # Call Whisper API or local model
        return "Patient Bella presented for annual wellness examination..."
```

---

### Step 8: Server-Side Authentication & Multi-Clinic Isolation
Derive identity strictly server-side from Odoo session tokens:

```python
"""auth/context_resolver.py"""
from core.sessions.context import EmployeeContext

def resolve_odoo_context(odoo_session_token: str) -> EmployeeContext:
    odoo_user = validate_odoo_session(odoo_session_token)
    if not odoo_user:
        raise PermissionError("Invalid Odoo session.")

    is_vet = odoo_user.has_group("zelix_vet.group_veterinarian")

    return EmployeeContext(
        user_id=f"vet_user_{odoo_user.id}",
        tenant_id=f"clinic_{odoo_user.company_id.id}",
        role="veterinarian" if is_vet else "vet_nurse",
        permissions=["patients.read", "medical_records.read"] + (["medical_records.write"] if is_vet else []),
    )
```

---

---

### Step 9: Configure AI LLM Providers & Smart Routing
The Starter abstracts LLMs using [`AIModelRouter`](file:///e:/Alamia/AlamiaAICopilot-Starter/core/ai/router.py). You can plug in cloud providers (OpenAI, Anthropic Claude, Google Gemini) or private local models (Ollama, vLLM, LiteLLM) in `main.py` without modifying `core/`:

```python
"""Configuring production LLM providers in main.py"""
from core.ai.router import AIModelRouter
from adapters.ai.providers.mock_provider import MockAIModelProvider
# Example production adapters (OpenAI / Claude / Ollama)
# from adapters.ai.providers.openai_provider import OpenAIModelProvider
# from adapters.ai.providers.anthropic_provider import AnthropicModelProvider

# 1. Zero-Cost Mock Provider (Default for testing & dev)
default_ai = MockAIModelProvider()

# 2. Production OpenAI Provider
# default_ai = OpenAIModelProvider(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o")

# 3. Smart Model Router (Route simple skills to fast models, clinical synthesis to reasoning models)
ai_router = AIModelRouter(
    default_provider=default_ai,
    skill_routes={
        "patient_360": "gpt-4o-mini",      # Fast, lightweight model for data aggregation
        "voice_to_soap": "gpt-4o",         # High-reasoning model for medical note synthesis
    }
)

engine = CopilotEngine(
    skill_registry=skills,
    tool_registry=tools,
    role_registry=roles,
    ai_router=ai_router,
    application_adapter=adapter,
)
```

---

### Step 10: UI Theming & Custom Frontends (Never Modify `core/`)
`core/` has zero dependencies on UI frameworks or CSS. The entire presentation layer is decoupled over open REST and AG-UI (SSE) protocols.

#### Approach A: Native Odoo 19 OWL Component (Odoo Look & Feel)
To embed the Copilot directly into Odoo 19 forms, chatter, or navigation bars matching Odoo's native styling:

```javascript
/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ZelixVetCopilotWidget extends Component {
    static template = "zelix_vet.CopilotChatWidget";

    setup() {
        this.state = useState({
            messages: [],
            input: "",
            loading: false,
            pendingAction: null,
        });
        this.rpc = useService("rpc");
    }

    async sendMessage() {
        const text = this.state.input.trim();
        if (!text) return;

        this.state.messages.push({ role: "user", text });
        this.state.input = "";
        this.state.loading = true;

        // Dispatch to ZelixAI Copilot Service
        const res = await fetch("http://localhost:8000/api/copilot/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: text })
        });
        const data = await res.json();
        this.state.loading = false;
        this.state.messages.push({ role: "assistant", text: data.message });

        // If Human-in-the-Loop confirmation required
        if (data.proposed_actions?.length > 0) {
            this.state.pendingAction = data.proposed_actions[0];
        }
    }

    async confirmAction(actionId) {
        await fetch("http://localhost:8000/api/action/confirm", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action_id: actionId })
        });
        this.state.pendingAction = null;
        this.state.messages.push({ role: "system", text: "Clinical encounter note confirmed and saved in Odoo." });
    }
}
```

#### Approach B: Theming CopilotKit (React)
If using CopilotKit, customize CSS variables to match Odoo's purple/teal branding:
```css
:root {
  --copilot-kit-primary-color: #714B67; /* Odoo signature purple */
  --copilot-kit-contrast-color: #00A09D; /* Odoo signature teal */
  --copilot-kit-background-color: #F9FAFB;
  --copilot-kit-border-radius: 8px;
}
```

#### Approach C: Custom Frontends (Vue, Angular, Flutter, Mobile)
Any client platform can build its own bespoke UI following [`docs/client-integration-guide.md`](file:///e:/Alamia/AlamiaAICopilot-Starter/docs/client-integration-guide.md).

---

### Step 11: Run the Automated Test Suite
```bash
pytest -v
```
Ensure all tests pass before deploying to staging/production.

---

## 3. Summary Matrix: Starter Base vs. Product Extensions

| Component | In Alamia Starter (`core/`) | In Your Vertical Project (`ZelixAI`) |
|---|---|---|
| **Runtime & Execution** | `CopilotEngine`, turn dispatch, event streams | Application bootloader & service runner |
| **Data Adapter** | `ApplicationAdapter` interface | `ZelixOdooAdapter` (Odoo 19 XML-RPC / ORM) |
| **Domain Tools** | `BaseTool`, permission checking | `GetPatientRecordTool`, `GetVaccinationHistoryTool` |
| **Domain Skills** | `BaseSkill`, `SkillRegistry` | `Patient360Skill`, `VoiceToSoapSkill` |
| **AI LLM Selection** | `AIModelProvider` & `AIModelRouter` | OpenAI GPT-4o, Claude 3.5, or local Ollama config |
| **UI Theming** | Decoupled AG-UI & REST protocols | Odoo 19 OWL component, themed CopilotKit, or custom SPA |
| **Voice / Transcription** | `BaseSpeechToTextProvider` contract | Pluggable Whisper / Deepgram STT provider |
| **Policy & Risk Gates** | `PolicyEngine`, `ActionProposal` | Role manifests (`veterinarian`, `vet_nurse`) |
| **Audit Log** | Append-only structured audit logger | Clinic-specific retention & compliance rules |
