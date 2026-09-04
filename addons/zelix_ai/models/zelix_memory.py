# -*- coding: utf-8 -*-
"""
Zelix Institutional Intelligence: Learned Rules & Veterinary Case Memory
Enables closed-loop learning from past clinician decisions and verified encounter history.
"""

import json
import re
from collections import Counter, defaultdict
from odoo import api, fields, models, _

STOP_WORDS = {
    "the", "and", "with", "for", "was", "has", "have", "had", "since", "days", "day", "patient", "ago",
    "from", "that", "this", "also", "not", "but", "his", "her", "she", "him", "doctor", "there", "then",
    "than", "been", "being", "some", "very", "just", "much", "more", "about", "yesterday", "today",
    "morning", "night", "week", "weeks", "hours", "hour", "taking", "take", "took", "feel", "feels",
    "feeling", "little", "canine", "feline", "dog", "cat", "pet", "animal", "clinic",
}


def extract_tokens(text):
    if not text:
        return set()
    return {t for t in re.findall(r"[a-zA-Z]{3,}", text.lower()) if t not in STOP_WORDS}


class ZelixAiRule(models.Model):
    """
    Learned Prescribing Rule: "Teach once, it practises your way".
    Allows veterinarians to capture decision heuristics (trigger keywords -> drug & dosage).
    """
    _name = "zelix.ai.rule"
    _description = "Zelix Learned Prescribing Rule"
    _order = "create_date desc"

    name = fields.Char(string="Rule Summary", compute="_compute_name", store=True)
    user_id = fields.Many2one("res.users", string="Veterinarian", required=True, default=lambda self: self.env.user)
    clinic_id = fields.Many2one("vet.clinic", string="Clinic Branch")
    scope = fields.Selection(
        [
            ("doctor", "This Veterinarian Only"),
            ("clinic", "Clinic Branch"),
            ("global", "Entire Practice (Global)"),
        ],
        string="Application Scope",
        default="doctor",
        required=True,
    )
    species_id = fields.Many2one("vet.species", string="Species Restriction", help="Leave empty for all species")
    trigger_keywords = fields.Char(
        string="Trigger Keywords",
        required=True,
        help="Comma-separated keywords in complaint/notes, e.g. 'vomiting, lethargy, gastritis'",
    )
    min_matches = fields.Integer(string="Min Keyword Matches", default=1)
    
    medication_id = fields.Many2one("vet.medication", string="Recommended Medication", required=True)
    dosage = fields.Char(string="Dosage", required=True)
    frequency = fields.Selection(
        [
            ("sid", "Once daily (SID)"),
            ("bid", "Twice daily (BID)"),
            ("tid", "Three times daily (TID)"),
            ("qid", "Four times daily (QID)"),
            ("prn", "As needed (PRN)"),
            ("stat", "Immediately (STAT)"),
        ],
        string="Frequency",
        default="sid",
        required=True,
    )
    duration = fields.Char(string="Duration", default="3 days")
    instructions = fields.Text(string="Administration Instructions")
    reason = fields.Char(string="Clinical Rationale")
    
    times_offered = fields.Integer(string="Times Offered", readonly=True, default=0)
    times_accepted = fields.Integer(string="Times Accepted", readonly=True, default=0)
    active = fields.Boolean(string="Active", default=True)

    @api.depends("trigger_keywords", "medication_id", "dosage")
    def _compute_name(self):
        for rec in self:
            med_name = rec.medication_id.name if rec.medication_id else "Medication"
            rec.name = f"{rec.trigger_keywords} → {med_name} ({rec.dosage or ''})"

    def keyword_list(self):
        self.ensure_one()
        return [k.strip().lower() for k in (self.trigger_keywords or "").split(",") if k.strip()]

    @api.model
    def match_rules(self, text, species_id=None, user_id=None, clinic_id=None):
        """Find active learned rules matching the clinical text."""
        if not text:
            return []
        text_lower = text.lower()
        
        domain = [("active", "=", True)]
        rules = self.search(domain)
        matched = []

        for rule in rules:
            # Check scope
            if rule.scope == "doctor" and user_id and rule.user_id.id != user_id:
                continue
            if rule.scope == "clinic" and clinic_id and rule.clinic_id and rule.clinic_id.id != clinic_id:
                continue
            if rule.species_id and species_id and rule.species_id.id != species_id:
                continue

            hits = sum(1 for k in rule.keyword_list() if k in text_lower)
            if hits >= max(1, rule.min_matches):
                matched.append((hits, rule))

        matched.sort(key=lambda t: -t[0])
        res = []
        for _, r in matched:
            res.append({
                "id": r.id,
                "name": r.name,
                "scope": r.scope,
                "trigger_keywords": r.trigger_keywords,
                "medication": r.medication_id.name if r.medication_id else "",
                "dosage": r.dosage,
                "frequency": r.frequency,
                "duration": r.duration,
                "reason": r.reason or "",
                "instructions": r.instructions or "",
            })
        return res


class ZelixCaseMemory(models.Model):
    """
    Veterinary Institutional Memory: De-identified bank of past confirmed encounters.
    Allows similarity search: "In this clinic, for this presentation, veterinarians usually prescribed..."
    """
    _name = "zelix.case.memory"
    _description = "Veterinary Case Memory"
    _order = "create_date desc"

    encounter_id = fields.Many2one("vet.encounter", string="Source Encounter", ondelete="set null")
    clinic_id = fields.Many2one("vet.clinic", string="Clinic Branch", index=True)
    veterinarian_id = fields.Many2one("res.users", string="Veterinarian", index=True)
    
    species_id = fields.Many2one("vet.species", string="Species", index=True)
    breed_id = fields.Many2one("vet.breed", string="Breed")
    weight_kg = fields.Float(string="Weight (kg)")
    age_band = fields.Selection(
        [
            ("juvenile", "Puppy / Kitten (< 1y)"),
            ("adult", "Adult (1-7y)"),
            ("senior", "Senior (7y+)"),
        ],
        string="Age Band",
        index=True,
    )
    
    chief_complaint = fields.Char(string="Chief Complaint")
    keywords = fields.Char(string="Indexed Tokens", index=True)
    assessment = fields.Text(string="Assessment / Diagnosis")
    prescription_summary = fields.Text(string="Prescriptions (JSON)")
    diagnostic_summary = fields.Char(string="Diagnostics Ordered")

    @api.model
    def record_from_encounter(self, encounter):
        """Ingest a confirmed clinical encounter into institutional memory."""
        if not encounter.patient_id:
            return None

        patient = encounter.patient_id
        age_years = (fields.Date.today() - patient.dob).days / 365.25 if patient.dob else 3.0
        age_band = "juvenile" if age_years < 1.0 else "senior" if age_years >= 7.0 else "adult"

        text_to_index = f"{encounter.chief_complaint or ''} {encounter.assessment or ''} {encounter.plan or ''}"
        tokens = extract_tokens(text_to_index)

        # Extract prescriptions
        prescriptions = self.env["vet.prescription"].search([("patient_id", "=", patient.id)])
        rx_list = []
        for rx in prescriptions[:5]:
            rx_list.append({
                "medication_id": rx.medication_id.id if rx.medication_id else None,
                "medication": rx.medication_id.name if rx.medication_id else "Medication",
                "dosage": rx.dosage,
                "frequency": rx.frequency,
                "duration": rx.duration,
            })

        return self.create({
            "encounter_id": encounter.id,
            "clinic_id": encounter.clinic_id.id if encounter.clinic_id else None,
            "veterinarian_id": encounter.provider_id.id if encounter.provider_id else self.env.uid,
            "species_id": patient.species_id.id if patient.species_id else None,
            "breed_id": patient.breed_id.id if patient.breed_id else None,
            "weight_kg": patient.weight if hasattr(patient, "weight") else 0.0,
            "age_band": age_band,
            "chief_complaint": encounter.chief_complaint,
            "keywords": " ".join(sorted(tokens)),
            "assessment": encounter.assessment,
            "prescription_summary": json.dumps(rx_list),
        })

    @api.model
    def find_similar_cases(self, query_text, species_id=None, limit=10):
        """Find past cases with greatest TF-IDF keyword overlap."""
        tokens = extract_tokens(query_text)
        if not tokens:
            return []

        search_terms = sorted(tokens, key=len, reverse=True)[:6]
        domain = []
        if species_id:
            domain.append(("species_id", "=", species_id))
        
        if search_terms:
            kw_domain = ["|"] * (len(search_terms) - 1) + [("keywords", "ilike", t) for t in search_terms]
            domain.extend(kw_domain)

        candidates = self.search(domain, limit=100)
        if not candidates:
            return []

        scored = []
        for c in candidates:
            c_tokens = set((c.keywords or "").split())
            overlap = tokens & c_tokens
            if overlap:
                score = len(overlap) / float(len(tokens) + len(c_tokens) - len(overlap))
                scored.append((score, c))

        scored.sort(key=lambda t: -t[0])
        res = []
        for score, c in scored[:limit]:
            res.append({
                "id": c.id,
                "score": round(score, 3),
                "species": c.species_id.name if c.species_id else "",
                "breed": c.breed_id.name if c.breed_id else "",
                "weight_kg": c.weight_kg,
                "age_band": c.age_band,
                "chief_complaint": c.chief_complaint,
                "assessment": c.assessment,
                "prescription_summary": c.prescription_summary,
                "diagnostic_summary": c.diagnostic_summary or "",
            })
        return res
