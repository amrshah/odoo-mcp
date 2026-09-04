"""AI layer — pluggable providers, one contract.

Every method here returns plain data. Nothing in this file writes to a patient record on its own:
the consult, the handoff and the admission decide what to do with the proposals.

Providers
---------
* anthropic  — Claude Messages API (https://api.anthropic.com/v1/messages)
* openai     — Chat Completions API (https://api.openai.com/v1/chat/completions)
* none       — offline mode: proposals come from hospital memory, learned rules and the protocol table.

The offline mode is not a toy: it is the same three sources the LLM is given, so a hospital can run
the whole workflow without any external API and switch a key on later.
"""
import json
import logging
import re

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .drug import ROUTES, FREQUENCIES

_logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the clinical assistant inside a hospital information system in Pakistan.
You help a licensed doctor by drafting — you never decide. Every suggestion must be reviewable and
carry its reasoning. Be conservative: do not propose antibiotics for presentations that are usually
viral; respect allergies absolutely; prefer medicines from the FORMULARY list (return their drug_id);
use adult or paediatric dosing according to age and weight; flag red flags. When HOSPITAL MEMORY and
the GUIDELINE disagree, say so in the reasoning so the doctor sees the divergence.
Answer ONLY with a single JSON object matching the schema. No prose before or after."""

ANALYSE_SCHEMA = """{
  "hpi": "string — history of presenting illness written from the transcript (2-4 sentences)",
  "past_history": "string", "medication_history": "string", "family_history": "string", "social_history": "string",
  "review_of_systems": "string",
  "red_flags": ["string"],
  "diagnoses": [{"name": "string", "icd10": "string code or empty", "reasoning": "string", "source": "ai|memory|protocol"}],
  "medicines": [{"drug_id": int or null, "drug": "string", "dose": "string", "route": "po|iv|im|sc|sl|top|inh|pr|neb|eye|ear",
                 "frequency": "stat|od|bd|tds|qid|hs|prn|q4h|q6h|q8h|q12h|weekly", "duration_days": int, "reason": "string", "source": "ai|memory|protocol"}],
  "investigations": [{"test_id": int or null, "test": "string", "urgency": "routine|urgent|stat", "reason": "string"}],
  "referral": {"department": "string or empty", "urgency": "routine|urgent|immediate", "reason": "string"},
  "safety_notes": ["string"]
}"""


class HmsAiService(models.AbstractModel):
    _name = "hms.ai.service"
    _description = "AI Service (pluggable)"

    # ------------------------------------------------------------------ config
    @api.model
    def _cfg(self, key, default=""):
        return self.env["ir.config_parameter"].sudo().get_param(f"stratos_hms.{key}", default)

    @api.model
    def provider(self):
        p = self._cfg("ai_provider", "none")
        if p == "anthropic" and not self._cfg("anthropic_api_key"):
            return "none"
        if p == "openai" and not self._cfg("openai_api_key"):
            return "none"
        return p

    # ------------------------------------------------------------------ transport
    @api.model
    def _call_llm(self, system, user, max_tokens=2500, json_mode=True):
        provider = self.provider()
        timeout = int(self._cfg("ai_timeout", "60") or 60)
        if provider == "anthropic":
            model = self._cfg("anthropic_model", "claude-sonnet-4-5")
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": self._cfg("anthropic_api_key"), "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": model, "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": user}]},
                timeout=timeout,
            )
            if resp.status_code >= 400:
                raise UserError(_("Anthropic API error %s: %s") % (resp.status_code, resp.text[:300]))
            data = resp.json()
            return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        if provider == "openai":
            model = self._cfg("openai_model", "gpt-4o")
            body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "max_tokens": max_tokens}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._cfg('openai_api_key')}", "content-type": "application/json"},
                json=body, timeout=timeout,
            )
            if resp.status_code >= 400:
                raise UserError(_("OpenAI API error %s: %s") % (resp.status_code, resp.text[:300]))
            return resp.json()["choices"][0]["message"]["content"]
        return None

    @staticmethod
    def _parse_json(text):
        if not text:
            return {}
        text = text.strip()
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
        try:
            return json.loads(text)
        except ValueError:
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except ValueError:
                    pass
        _logger.warning("AI returned non-JSON: %s", text[:200])
        return {}

    # ------------------------------------------------------------------ context builders
    @api.model
    def _formulary_snippet(self, extra_drugs=None, limit=80):
        Drug = self.env["hms.drug"]
        drugs = Drug.browse()
        if extra_drugs:
            drugs |= extra_drugs
        drugs |= Drug.search([], limit=limit)
        return "\n".join(f"- drug_id={d.id}: {d.name} [{d.generic_name}] class={d.drug_class or ''} dose={d.default_dose or ''} {d.default_route} {d.default_frequency}"
                         + (f" paeds={d.paediatric_dose_text}" if d.paediatric_dose_text else "") + (f" MAX={d.max_daily_dose_text}" if d.max_daily_dose_text else "")
                         + (f" ALLERGEN={d.allergen_class}" if d.allergen_class else "") for d in drugs)

    @api.model
    def _tests_snippet(self):
        return "\n".join(f"- test_id={t.id}: {t.name} ({t.code}, {t.category})" for t in self.env["hms.test"].search([], limit=120))

    @api.model
    def _protocols_snippet(self, protocols):
        out = []
        for p in protocols[:3]:
            meds = "; ".join(f"{l.drug_id.name} {l.dose} {l.route} {l.frequency} ×{l.duration_days}d ({l.reason or ''})" for l in p.line_ids)
            out.append(f"GUIDELINE '{p.name}' [{p.source or 'local'}]: {p.reasoning or ''} Medicines: {meds}. Investigations: {', '.join(p.investigation_ids.mapped('name'))}. Red flags: {p.red_flags or ''}")
        return "\n".join(out)

    # ------------------------------------------------------------------ public API
    @api.model
    def summarize_visit(self, visit):
        """Five bullets: the story so far, from every department, up to this exact moment."""
        ctx = visit.patient_id.get_chart_context()
        consults = visit.consult_ids.filtered(lambda c: c.state == "signed")
        facts = {
            "patient": ctx, "visit": visit.name, "type": visit.visit_type, "department": visit.department_id.name,
            "doctor": visit.doctor_id.display_name, "complaint": visit.complaint, "stage": visit.stage,
            "ews": visit.ews_score, "held": visit.hold_reason or "", "billing": visit.billing_state,
            "amount_due": visit.amount_due, "approved_discount": visit.approved_discount,
            "orders": [{"test": o.test_id.name, "state": o.state, "urgency": o.urgency, "result": o.result_value or "", "flag": o.flag or ""} for o in visit.order_ids],
            "consults_this_visit": [{"doctor": c.doctor_id.display_name, "diagnosis": c.working_diagnosis, "plan": (c.plan or "")[:300]} for c in consults],
            "referred_by": visit.referred_by or "",
        }
        if self.provider() != "none":
            try:
                text = self._call_llm(
                    "You write a concise clinical hand-over summary for a doctor about to see the patient. Five short bullets, plain text, "
                    "start with who the patient is and why they are here, then vitals/EWS, then allergies IN CAPITALS, then what has already been done "
                    "(orders, results, medicines, money status), then what is outstanding. No JSON.",
                    json.dumps(facts, ensure_ascii=False, default=str), max_tokens=600, json_mode=False)
                if text:
                    return text.strip()
            except Exception as e:  # noqa: BLE001
                _logger.warning("AI summary failed, using template: %s", e)
        return self._template_summary(visit, facts)

    @api.model
    def _template_summary(self, visit, facts):
        p = visit.patient_id
        allergy = ("ALLERGY: " + visit.allergy_summary.upper()) if visit.allergy_summary else "No known allergies recorded."
        vit = visit.latest_vitals_id
        lines = [
            f"• {p.name}, {p.age_display}, {p.occupation or ''} — {visit.visit_type.upper()} to {visit.department_id.name}: {visit.complaint}." + (f" Referred: {visit.referred_by}." if visit.referred_by else ""),
            f"• {vit.as_text() if vit else 'No vitals yet.'}" + (f" Flagged: {vit.flags}." if vit and vit.flags else ""),
            f"• {allergy}" + (f" Chronic: {p.chronic_conditions}." if p.chronic_conditions else "") + (f" Current medicines: {p.current_medicines}." if p.current_medicines else ""),
            "• " + (("Orders: " + "; ".join(f"{o['test']} [{o['state']}{', ' + o['result'] + ' ' + o['flag'] if o['result'] else ''}]" for o in facts["orders"])) if facts["orders"] else "No investigations ordered yet.")
            + (" Prior consults: " + "; ".join(f"{c['doctor']}: {c['diagnosis']}" for c in facts["consults_this_visit"]) if facts["consults_this_visit"] else ""),
            f"• Journey: {dict(visit._fields['stage'].selection)[visit.stage]}. Money: {visit.billing_state}" + (f", due PKR {visit.amount_due:,.0f}" if visit.amount_due else "") + (f", {visit.approved_discount:g}% discount approved" if visit.approved_discount else "") + (f". HELD — {visit.hold_reason}" if visit.held else "") + ".",
        ]
        return "\n".join(lines)

    @api.model
    def analyse_consult(self, consult):
        """The three sources — hospital memory, learned rules, guideline — plus the LLM if configured."""
        patient = consult.patient_id
        Memory = self.env["hms.case.memory"]
        cases = Memory.similar(consult)
        agg = Memory.aggregate(cases)
        memory_text = Memory.memory_text(agg)
        rules = self.env["hms.ai.rule"].match(consult)
        protocols = self.env["hms.protocol"].match_text(" ".join(filter(None, [consult.complaint, consult.transcript, consult.hpi])), age=patient.age)
        result = None
        provider = self.provider()
        if provider != "none":
            extra = self.env["hms.drug"].browse([m["drug_id"] for m in agg["medicines"]]) | rules.mapped("drug_id") if rules else self.env["hms.drug"].browse([m["drug_id"] for m in agg["medicines"]])
            for p in protocols[:3]:
                extra |= p.line_ids.mapped("drug_id")
            user = "\n\n".join(filter(None, [
                "PATIENT: " + json.dumps(patient.get_chart_context(), ensure_ascii=False, default=str),
                f"DEPARTMENT: {consult.department_id.name}. SPECIALTY PACK: {consult.department_id.specialty_pack or 'none'}",
                f"PRESENTING COMPLAINT: {consult.complaint}",
                f"VITALS: {consult.latest_vitals_text} (EWS {consult.ews_score})",
                f"TRANSCRIPT OF CONSULTATION (doctor and patient, may be Urdu/English):\n{consult.transcript or '(none)'}",
                f"DOCTOR'S TYPED HPI: {consult.hpi}" if consult.hpi else "",
                f"HOSPITAL MEMORY (what this hospital's doctors did for similar presentations):\n{memory_text}" if memory_text else "HOSPITAL MEMORY: no similar cases yet.",
                ("LEARNED RULES from this doctor/department (offer these FIRST when they apply, source='memory'):\n" + "\n".join(f"- when '{r.trigger_keywords}': drug_id={r.drug_id.id} {r.drug_id.name} {r.dose} {r.route} {r.frequency} ×{r.duration_days}d ({r.reason or ''})" for r in rules)) if rules else "",
                self._protocols_snippet(protocols),
                "FORMULARY (use drug_id):\n" + self._formulary_snippet(extra),
                "TEST CATALOGUE (use test_id):\n" + self._tests_snippet(),
                "Return JSON with this schema:\n" + ANALYSE_SCHEMA,
            ]))
            try:
                result = self._parse_json(self._call_llm(SYSTEM_PROMPT, user))
                if result:
                    result["_provider"] = provider
            except UserError:
                raise
            except Exception as e:  # noqa: BLE001
                _logger.exception("AI analyse failed: %s", e)
                result = None
        if not result:
            result = self._offline_analyse(consult, agg, rules, protocols)
            result["_provider"] = "offline (memory + rules + protocols)"
        # learned rules always ride along, marked
        seen = {(m.get("drug_id"), (m.get("dose") or "").lower()) for m in result.get("medicines", [])}
        for r in rules:
            if (r.drug_id.id, r.dose.lower()) not in seen:
                result.setdefault("medicines", []).insert(0, {"drug_id": r.drug_id.id, "drug": r.drug_id.name, "dose": r.dose, "route": r.route, "frequency": r.frequency,
                                                             "duration_days": r.duration_days, "reason": f"Learned rule ({r.doctor_id.display_name}): {r.reason or r.trigger_keywords}", "source": "memory", "learned": True})
            r.times_offered += 1
        result["_memory_text"] = memory_text
        return result

    @api.model
    def _offline_analyse(self, consult, agg, rules, protocols):
        """No API key: memory first, guideline second, and the differences are visible."""
        out = {"diagnoses": [], "medicines": [], "investigations": [], "referral": {}, "safety_notes": [], "red_flags": []}
        for d, n in agg["diagnoses"]:
            out["diagnoses"].append({"name": d, "reasoning": f"Hospital memory: {n} similar case(s) were diagnosed as this.", "source": "memory"})
        for m in agg["medicines"][:4]:
            out["medicines"].append({"drug_id": m["drug_id"], "drug": m["drug"], "dose": m.get("dose"), "route": m.get("route"), "frequency": m.get("frequency"),
                                     "duration_days": m.get("duration_days"), "reason": f"Hospital memory: prescribed {m['count']}× for similar cases by {', '.join(m.get('doctors', []))}", "source": "memory"})
        for p in protocols[:2]:
            if p.name not in [d["name"] for d in out["diagnoses"]]:
                out["diagnoses"].append({"name": p.icd10_id.name if p.icd10_id else p.name, "icd10": p.icd10_id.code if p.icd10_id else "", "reasoning": f"Guideline ({p.source or 'local protocol'}): {p.reasoning or ''}", "source": "protocol"})
            mem_ids = {m["drug_id"] for m in out["medicines"]}
            for l in p.line_ids:
                if l.drug_id.id not in mem_ids:
                    out["medicines"].append({"drug_id": l.drug_id.id, "drug": l.drug_id.name, "dose": l.dose, "route": l.route, "frequency": l.frequency, "duration_days": l.duration_days,
                                             "reason": f"Guideline ({p.source or 'protocol'}): {l.reason or ''}", "source": "protocol"})
            for t in p.investigation_ids:
                out["investigations"].append({"test_id": t.id, "test": t.name, "urgency": "urgent" if consult.ews_score >= 5 else "routine", "reason": f"Guideline: {p.name}"})
            if p.refer_department_id and not out["referral"]:
                out["referral"] = {"department": p.refer_department_id.name, "urgency": "urgent" if consult.ews_score >= 5 else "routine", "reason": p.name}
            if p.red_flags:
                out["red_flags"].append(p.red_flags)
        if agg["n"] and protocols:
            out["safety_notes"].append("Hospital memory and guideline shown side by side — check where they diverge before approving.")
        if not out["diagnoses"] and consult.complaint:
            out["diagnoses"].append({"name": consult.complaint, "reasoning": "No matching memory or protocol; recorded the presenting complaint as a working diagnosis for the doctor to replace.", "source": "ai"})
        return out

    @api.model
    def draft_sbar(self, admission):
        """SBAR from the chart itself: medicines given this shift, flagged results, escalation thresholds."""
        vit = admission.vitals_ids.sorted("create_date", reverse=True)[:1] or admission.visit_id.latest_vitals_id
        given = admission.mar_ids.filtered(lambda m: m.state == "given" and m.given_at and (fields.Datetime.now() - m.given_at).total_seconds() < 12 * 3600)
        due = admission.mar_ids.filtered(lambda m: m.state == "due").sorted("scheduled_at")[:5]
        flagged = admission.visit_id.order_ids.filtered(lambda o: o.flag in ("critical", "high", "low", "abnormal"))
        pending = admission.visit_id.order_ids.filtered(lambda o: o.state in ("ordered", "collected", "resulted"))
        facts = {
            "patient": f"{admission.patient_id.name}, {admission.patient_id.age_display}, MRN {admission.patient_id.mrn}, bed {admission.bed_id.display_name}",
            "admitted": f"{admission.admitted_at:%d %b %H:%M} under {admission.doctor_id.display_name} with {admission.diagnosis}",
            "allergies": admission.allergy_summary or "none recorded",
            "latest_vitals": vit.as_text() if vit else "none",
            "active_orders": [o.display_name for o in admission.ward_order_ids.filtered(lambda o: o.state == "active")],
            "given_this_shift": [f"{m.drug_id.name} {m.dose or ''} at {m.given_at:%H:%M}" for m in given],
            "due_next": [f"{m.drug_id.name} at {m.scheduled_at:%H:%M}" for m in due],
            "flagged_results": [f"{o.test_id.name} {o.result_value} {o.flag}" for o in flagged],
            "pending_results": [o.test_id.name for o in pending],
            "progress_notes": [f"{n.doctor_id.display_name}: {n.note[:200]}" for n in admission.progress_note_ids[:2]],
            "escalation": admission.escalation_note,
        }
        if self.provider() != "none":
            try:
                data = self._parse_json(self._call_llm(
                    "You are a senior nurse writing a shift handover in SBAR format. Return JSON {situation, background, assessment, recommendation}. "
                    "Recommendation must list what to do, what to watch, and the escalation thresholds. Plain concise sentences.",
                    json.dumps(facts, ensure_ascii=False, default=str), max_tokens=900))
                if data.get("situation"):
                    return data
            except Exception as e:  # noqa: BLE001
                _logger.warning("SBAR AI failed: %s", e)
        return {
            "situation": f"{facts['patient']}. Admitted {facts['admitted']}. Allergies: {facts['allergies']}.",
            "background": "Active orders: " + ("; ".join(facts["active_orders"]) or "none") + ". " + (("Notes: " + " | ".join(facts["progress_notes"])) if facts["progress_notes"] else ""),
            "assessment": f"Latest vitals {facts['latest_vitals']}. " + ("Flagged results: " + "; ".join(facts["flagged_results"]) + ". " if facts["flagged_results"] else "No flagged results. ") + ("Pending: " + ", ".join(facts["pending_results"]) + "." if facts["pending_results"] else ""),
            "recommendation": ("Given this shift: " + ("; ".join(facts["given_this_shift"]) or "nothing") + ". Due next: " + ("; ".join(facts["due_next"]) or "nothing scheduled") + ". " + facts["escalation"]),
        }

    @api.model
    def draft_discharge_summary(self, admission):
        v = admission.visit_id
        consults = v.consult_ids.filtered(lambda c: c.state == "signed")
        results = v.order_ids.filtered(lambda o: o.state in ("verified", "acknowledged"))
        meds = admission.ward_order_ids.filtered(lambda o: o.drug_id)
        html = [f"<h3>Discharge Summary — {admission.name}</h3>",
                f"<p><b>{admission.patient_id.name}</b> · {admission.patient_id.age_display} · MRN {admission.patient_id.mrn}</p>",
                f"<p><b>Admitted:</b> {admission.admitted_at:%d %b %Y} · <b>Discharged:</b> {fields.Datetime.now():%d %b %Y} · <b>LOS:</b> {admission.length_of_stay} day(s) · <b>Under:</b> {admission.doctor_id.display_name}</p>",
                f"<p><b>Diagnosis:</b> {admission.diagnosis}</p>"]
        if admission.allergy_summary:
            html.append(f"<p style='color:#b91c1c'><b>ALLERGY:</b> {admission.allergy_summary}</p>")
        if consults:
            html.append("<p><b>Consultations:</b></p><ul>" + "".join(f"<li>{c.doctor_id.display_name}: {c.working_diagnosis} — {(c.plan or '')[:200]}</li>" for c in consults) + "</ul>")
        if results:
            html.append("<p><b>Investigations:</b></p><ul>" + "".join(f"<li>{o.test_id.name}: {o.result_value or 'see report'} {o.test_id.unit or ''} ({o.flag or ''})</li>" for o in results) + "</ul>")
        if meds:
            html.append("<p><b>Medicines during stay:</b> " + "; ".join(meds.mapped("display_name")) + "</p>")
        if admission.surgery_ids:
            html.append("<p><b>Procedures:</b> " + "; ".join(admission.surgery_ids.mapped("procedure")) + "</p>")
        html.append(f"<p><b>Escalation advice given:</b> {admission.escalation_note}</p>")
        html.append(f"<p><i>Generated by Stratos HMS on {fields.Datetime.now():%d %b %Y %H:%M}; to be reviewed and signed by the discharging doctor.</i></p>")
        return "".join(html)

    @api.model
    def test_connection(self):
        provider = self.provider()
        if provider == "none":
            raise UserError(_("No AI provider configured (or key missing). The system will use offline mode: hospital memory + learned rules + protocols."))
        text = self._call_llm("Reply with the single word OK.", "ping", max_tokens=10, json_mode=False)
        return f"{provider}: {text.strip()[:50]}"
