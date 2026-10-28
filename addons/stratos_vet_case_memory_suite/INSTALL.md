# Vet Clinical Suggestions – Installation Guide (Odoo 19 Community)

Stratos Hub · www.stratos-hub.com

## 1. What is in this package

| # | Module | Install | Purpose |
|---|---|---|---|
| 1 | `stratos_vet_case_memory` | Yes | Core app: clinical cases, suggestion engine, approvals, learning, voice dictation, reports. |
| 2 | `stratos_vet_case_memory_soap` | Automatic | Connects to the SOAP exam module `stratos_vet_exam`. Installs itself when both are present. |
| 3 | `stratos_vet_case_memory_vetcairn` | Automatic | Maps VetCairn roles and menus; fills breed, sex, neuter status and age from the VetCairn patient. Installs itself when `stratos_vet_exam_vetcairn` is present. |

**Requires:** `stratos_vet_exam` (and optionally `stratos_vet_exam_vetcairn`) from the Vet Exam suite.

## 2. Install steps

1. Copy the three folders into the server's custom addons folder (the same folder as `stratos_vet_exam`).
2. Restart the Odoo service.
3. Apps → Update Apps List.
4. Search **Vet Clinical Suggestions** → Install. The two connectors install automatically.
5. Settings → Users: give each user a role under **Vet Clinical Suggestions**.
   - With VetCairn, roles follow VetCairn automatically: Technician → Nurse, Veterinarian → Veterinarian, Manager → Senior Vet.

## 3. Demo data (for videos and presentations)

| Database type | How demo data loads |
|---|---|
| New database created **with demo data** | Loads automatically on install. |
| Any other database | Vet Suggestions → Configuration → Settings → **Load demo cases**. |

The demo adds:

1. **50 finalised cases**: 20 dogs, 12 cats, 12 cattle, 6 goats.
   - Each one was run through the real engine and decided by a demo vet, so the knowledge base and reports hold real history.
2. **6 open cases ready for a live demo:**

| Case | What it shows |
|---|---|
| Bruno (Labrador puppy) | A voice note waiting to be applied, then a parvo suggestion. |
| Mano (Persian cat) | Respiratory infection suggestion. Try adding Paracetamol to see the species block. |
| Cow #A-112 (Sahiwal) | Mastitis suggestion with milk and meat withdrawal days. |
| Buffalo #B-07 | No buffalo history yet, so it falls back to a protocol ("Low evidence"). |
| Rocky (Rough Collie) | Mange suggestion with an Ivermectin breed caution and a zoonotic alert. |
| Goat #G-31 (Beetal) | PPR vs pneumonia shown as competing diagnoses. |

3. **Demo logins** (password = login + `123`):

| Login | Role |
|---|---|
| `dr.ayesha` | Senior Vet |
| `dr.hamza` | Veterinarian |
| `nurse.sana` | Nurse |

## 4. Voice dictation

- Works in **Google Chrome** or **Microsoft Edge**. The browser asks for microphone permission once.
- The site must be served over **HTTPS**; browsers block the microphone on plain http, except on localhost.
- Dictation languages: English and Urdu. The default is set in Settings.

## 5. Optional AI layer

| Mode | How to set it |
|---|---|
| Demo mode (default) | Works offline. Use it for demos and training. |
| Live AI | Settings → AI provider → Anthropic or OpenAI → paste the API key. |

## 6. Important

- Dosing values in the demo drug list are for training only. Review **Configuration → Drugs & Dosing Rules** against your clinic's formulary before live use.
- Suggestions are decision support. Nothing is ordered until a veterinarian approves it.
