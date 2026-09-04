import json
import re
from collections import Counter, defaultdict

from odoo import api, fields, models, _

from .drug import ROUTES, FREQUENCIES

STOP = {
    # english
    "the", "and", "with", "for", "was", "has", "have", "had", "since", "days", "day", "patient", "ago", "from", "that", "this", "also", "not",
    "but", "his", "her", "she", "him", "doctor", "there", "then", "than", "been", "being", "some", "very", "just", "much", "more", "about",
    "yesterday", "today", "morning", "night", "week", "weeks", "hours", "hour", "taking", "take", "took", "feel", "feels", "feeling", "little",
    # roman urdu function words
    "hai", "hain", "hoon", "aur", "say", "mein", "main", "mujhe", "mera", "meri", "mere", "ki", "ka", "ke", "ko", "se", "hy", "kya", "bhi",
    "raha", "rahi", "rahe", "hua", "hui", "hue", "tha", "thi", "the", "din", "teen", "char", "paanch", "lekin", "kar", "karta", "karti",
    "nahi", "nahin", "kal", "aaj", "saath", "sath", "ye", "yeh", "wo", "woh", "jab", "tab", "phir", "bohat", "bahut", "kuch", "zyada",
    "kam", "thora", "thori", "sahab", "sahib", "bata", "batao", "dafa", "baar", "jaisa", "jaisi", "pee", "kha", "abhi", "kabhi", "liye",
}


def tokens(text):
    return {t for t in re.findall(r"[a-zA-Z؀-ۿ]{3,}", (text or "").lower()) if t not in STOP}


class HmsAiRule(models.Model):
    """Teach once and it practises your way. A doctor records a rule — situation, his answer —
    saved as a rule, not a note. Next time it is offered first, wearing a 'learned' badge.
    Juniors inherit the seniors' judgment."""
    _name = "hms.ai.rule"
    _description = "Learned Prescribing Rule"
    _order = "create_date desc"

    doctor_id = fields.Many2one("hms.practitioner", required=True, default=lambda self: self.env["hms.practitioner"].get_current())
    department_id = fields.Many2one("hms.department")
    scope = fields.Selection([("doctor", "This doctor only"), ("department", "Whole department"), ("hospital", "Whole hospital")], default="doctor", required=True)
    trigger_keywords = fields.Char(required=True, help="When the complaint / transcript mentions… (comma-separated), e.g. 'sternal wound, itching, night'")
    min_matches = fields.Integer(default=1, help="How many of the keywords must appear.")
    drug_id = fields.Many2one("hms.drug", required=True)
    dose = fields.Char(required=True)
    route = fields.Selection(ROUTES, default="po", required=True)
    frequency = fields.Selection(FREQUENCIES, default="od", required=True)
    duration_days = fields.Integer(default=5)
    reason = fields.Char(string="Reason (shown with the proposal)")
    times_offered = fields.Integer(readonly=True)
    times_accepted = fields.Integer(readonly=True)
    active = fields.Boolean(default=True)

    def keyword_list(self):
        self.ensure_one()
        return [k.strip().lower() for k in (self.trigger_keywords or "").split(",") if k.strip()]

    @api.model
    def match(self, consult):
        """Rules that apply to this consult (doctor / department / hospital scope), best first."""
        text = " ".join(filter(None, [consult.complaint, consult.transcript, consult.hpi, consult.working_diagnosis])).lower()
        out = []
        for rule in self.search([]):
            if rule.scope == "doctor" and rule.doctor_id != consult.doctor_id:
                continue
            if rule.scope == "department" and rule.department_id and rule.department_id != consult.department_id:
                continue
            hits = sum(1 for k in rule.keyword_list() if k in text)
            if hits >= max(1, rule.min_matches):
                out.append((hits, rule))
        out.sort(key=lambda t: -t[0])
        return [r for _, r in out]

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.trigger_keywords} → {rec.drug_id.name} {rec.dose}"


class HmsCaseMemory(models.Model):
    """Hospital memory. Every signed consult becomes a de-identified case: presentation → decision.
    A new patient with a similar presentation gets 'in this hospital, for this, Dr X usually gives…'
    next to the guideline — and the doctor still decides."""
    _name = "hms.case.memory"
    _description = "Hospital Case Memory"
    _order = "create_date desc"

    consult_id = fields.Many2one("hms.consult", ondelete="set null")
    doctor_id = fields.Many2one("hms.practitioner", index=True)
    department_id = fields.Many2one("hms.department", index=True)
    age_band = fields.Selection([("infant", "<2"), ("child", "2-13"), ("adult", "14-59"), ("elderly", "60+")], index=True)
    sex = fields.Selection([("m", "Male"), ("f", "Female"), ("o", "Other")])
    complaint = fields.Char()
    keywords = fields.Char(index=True, help="Normalised tokens from complaint + HPI + diagnosis.")
    diagnosis = fields.Char(index=True)
    icd10_code = fields.Char()
    prescription_json = fields.Text()
    investigations = fields.Char()
    ews_score = fields.Integer()
    outcome = fields.Selection([("unknown", "Unknown"), ("improved", "Improved"), ("admitted", "Admitted"), ("referred", "Referred"), ("returned", "Returned within 7 days")], default="unknown")

    @api.model
    def _age_band(self, age):
        if age is None:
            return "adult"
        return "infant" if age < 2 else "child" if age < 14 else "adult" if age < 60 else "elderly"

    @api.model
    def record_from_consult(self, consult):
        dx = consult.diagnosis_ids.filtered("confirmed")
        rx = consult.prescription_ids.filtered(lambda l: l.state == "approved")
        text = " ".join(filter(None, [consult.complaint, consult.hpi, consult.transcript, ", ".join(dx.mapped("name"))]))
        return self.create({
            "consult_id": consult.id,
            "doctor_id": consult.doctor_id.id,
            "department_id": consult.department_id.id,
            "age_band": self._age_band(consult.patient_id.age),
            "sex": consult.patient_id.sex,
            "complaint": consult.complaint,
            "keywords": " ".join(sorted(tokens(text))),
            "diagnosis": ", ".join(dx.mapped("name")),
            "icd10_code": ", ".join(dx.mapped("icd10_id.code")),
            "prescription_json": json.dumps([{
                "drug_id": l.drug_id.id, "drug": l.drug_id.name, "dose": l.dose, "route": l.route,
                "frequency": l.frequency, "duration_days": l.duration_days,
            } for l in rx]),
            "investigations": ", ".join(consult.order_ids.filtered(lambda o: o.state not in ("proposed", "cancelled")).mapped("test_id.name")),
            "ews_score": consult.ews_score,
            "outcome": "referred" if consult.refer_department_id else "admitted" if consult.admit else "unknown",
        })

    @api.model
    def similar(self, consult, limit=40):
        """Cases with the most keyword overlap, same age band preferred."""
        q = tokens(" ".join(filter(None, [consult.complaint, consult.hpi, consult.transcript])))
        if not q:
            return []
        band = self._age_band(consult.patient_id.age)
        terms = sorted(q, key=len, reverse=True)[:8]
        domain = ["|"] * (len(terms) - 1) + [("keywords", "ilike", t) for t in terms]
        cands = self.search(domain, limit=500)
        if not cands:
            return []
        # IDF-style weights: a word every case contains ("fever") says less than a rare one ("wheeze")
        n = len(cands)
        df = {t: sum(1 for c in cands if t in set((c.keywords or "").split())) for t in q}
        weight = {t: 1.0 / (1.0 + df[t]) if df[t] else 0.0 for t in q}
        total = sum(weight.values()) or 1.0
        scored = []
        for c in cands:
            ck = set((c.keywords or "").split())
            hit = q & ck
            if not hit:
                continue
            rel = sum(weight[t] for t in hit) / total
            if len(hit) < 2 and len(q) > 3:
                continue
            if rel < 0.2:
                continue
            score = rel + (0.15 if c.age_band == band else 0.0) + (0.1 if c.department_id == consult.department_id else 0.0)
            scored.append((score, c))
        scored.sort(key=lambda t: -t[0])
        return [c for _, c in scored[:limit]]

    @api.model
    def aggregate(self, cases):
        """Turn similar cases into 'what this hospital usually does': top diagnoses and top medicine patterns."""
        dx_counter = Counter()
        rx_counter = Counter()
        rx_detail = {}
        doctors = defaultdict(set)
        for c in cases:
            for d in (c.diagnosis or "").split(", "):
                if d:
                    dx_counter[d] += 1
            try:
                lines = json.loads(c.prescription_json or "[]")
            except ValueError:
                lines = []
            for l in lines:
                key = l.get("drug_id")
                if key:
                    rx_counter[key] += 1
                    rx_detail.setdefault(key, l)
                    if c.doctor_id:
                        doctors[key].add(c.doctor_id.display_name)
        return {
            "n": len(cases),
            "diagnoses": dx_counter.most_common(3),
            "medicines": [dict(rx_detail[k], count=n, doctors=sorted(doctors[k])[:3]) for k, n in rx_counter.most_common(6)],
        }

    @api.model
    def memory_text(self, agg):
        if not agg or not agg["n"]:
            return ""
        lines = [f"{agg['n']} similar past case(s) in this hospital."]
        if agg["diagnoses"]:
            lines.append("Diagnosed as: " + "; ".join(f"{d} ({n})" for d, n in agg["diagnoses"]))
        for m in agg["medicines"]:
            fr = dict(FREQUENCIES).get(m.get("frequency"), m.get("frequency"))
            lines.append(f"• {m['drug']} {m.get('dose','')} {fr} × {m.get('duration_days','')}d — {m['count']}× (" + ", ".join(m.get("doctors", [])) + ")")
        return "\n".join(lines)
