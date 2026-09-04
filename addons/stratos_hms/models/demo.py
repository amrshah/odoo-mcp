"""Demo scenario generator — runs from demo/demo_visits.xml via <function>.

Builds a believable morning at a Lahore hospital so every workspace has something on it:
queues, a held file with a discount request, a STEMI in the doctor's queue, memory cases,
a critical troponin awaiting a phone call, an inpatient with a MAR and a handoff.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HmsDemo(models.AbstractModel):
    _name = "hms.demo"
    _description = "HMS demo scenario"

    @api.model
    def _ref(self, xid):
        return self.env.ref(f"stratos_hms.{xid}")

    @api.model
    def _signed_consult(self, patient, dept, doctor, complaint, transcript, dx_name, icd_xid, meds, tests=(), days_ago=0, vitals=None):
        """Create a full signed consult in the past (for hospital memory) and close the visit."""
        Visit = self.env["hms.visit"]
        arrival = fields.Datetime.now() - timedelta(days=days_ago, hours=3)
        visit = Visit.create({"patient_id": patient.id, "department_id": dept.id, "doctor_id": doctor.id, "complaint": complaint, "arrival_time": arrival})
        visit.consent_ids.write({"state": "signed", "signed_at": arrival, "signed_by_name": patient.name, "taken_by_id": self._ref("staff_nasreen").id})
        self.env["hms.vitals"].create(dict({"visit_id": visit.id, "nurse_id": self._ref("staff_hina").id, "taken_at": arrival}, **(vitals or {"bp_sys": 120, "bp_dia": 78, "heart_rate": 82, "resp_rate": 16, "temperature": 37.0, "spo2": 98})))
        consult = self.env["hms.consult"].create({"visit_id": visit.id, "doctor_id": doctor.id, "transcript": transcript, "hpi": transcript[:200]})
        self.env["hms.consult.diagnosis"].create({"consult_id": consult.id, "name": dx_name, "icd10_id": self._ref(icd_xid).id, "confirmed": True, "source": "doctor"})
        for drug_xid, dose, route, freq, days, reason in meds:
            self.env["hms.prescription.line"].create({"consult_id": consult.id, "drug_id": self._ref(drug_xid).id, "dose": dose, "route": route, "frequency": freq, "duration_days": days, "reason": reason, "state": "approved"})
        for t in tests:
            self.env["hms.order"].create({"visit_id": visit.id, "consult_id": consult.id, "test_id": self._ref(t).id, "ordered_by_id": doctor.id, "state": "ordered"})
        consult.action_sign()
        for o in visit.order_ids:
            o.write({"scanned_band": patient.mrn, "scanned_specimen": o.specimen_barcode})
            o.action_collect()
            o.write({"result_value": "Normal" if not o.test_id.numeric else str((o.test_id.ref_low + o.test_id.ref_high) / 2)})
            o.action_enter_result()
            o.action_verify_release()
            o.action_acknowledge()
        # pharmacy dispensed
        for d in self.env["hms.dispense"].search([("visit_id", "=", visit.id)]):
            d.action_verify()
            d.action_dispense()
        # bill & pay
        self.env["hms.charge"].create_invoice_for_visit(visit)
        inv = visit.invoice_ids.filtered(lambda m: m.state == "posted")
        if inv:
            try:
                self.env["account.payment.register"].with_context(active_model="account.move", active_ids=inv.ids).create({}).action_create_payments()
            except Exception as ex:  # noqa: BLE001
                _logger.warning("Demo payment skipped: %s", ex)
        visit.write({"stage": "discharged", "state": "closed"})
        return consult

    @api.model
    def generate(self):
        env = self.env
        P = lambda x: self._ref(f"patient_{x}")  # noqa: E731
        S = lambda x: self._ref(f"staff_{x}")  # noqa: E731
        D = lambda x: self._ref(f"dept_{x}")  # noqa: E731
        med, card, paeds, pulmo = D("medicine"), D("cardiology"), D("paeds"), D("pulmo")
        ayesha, bilal, farhan, sana, hina = S("ayesha"), S("bilal"), S("farhan"), S("sana"), S("hina")

        # ---- hospital memory: past signed consults (diarrhoea pattern, typhoid, URTI, dengue) ----
        self._signed_consult(P("amina"), med, ayesha, "Loose motions for two days", "Doctor, I have loose motions since two days, five six times a day, watery, no blood. Some vomiting yesterday. No fever. I am drinking water.",
                             "Acute watery diarrhoea", "icd_a09", [("drug_ors", "200 ml after each loose stool", "po", "prn", 3, "Rehydration"), ("drug_zinc_20", "1 tab", "po", "od", 14, "Shortens the episode"), ("drug_ondansetron_8", "1 tab", "po", "bd", 2, "For vomiting")], days_ago=21)
        self._signed_consult(P("hassan"), med, ayesha, "Diarrhoea and abdominal cramps", "Loose stools since yesterday, cramping pain, went to a wedding, ate outside. No blood, mild fever.",
                             "Acute gastroenteritis", "icd_a09", [("drug_ors", "200 ml after each loose stool", "po", "prn", 3, "Rehydration"), ("drug_zinc_20", "1 tab", "po", "od", 10, "Reduces duration"), ("drug_hyoscine_10", "1 tab", "po", "tds", 2, "Cramps")], days_ago=14)
        self._signed_consult(P("iqbal"), med, sana, "Loose motions, weakness", "Dast lag gaye hain teen din se, kamzori hai, pani jaisa. Bukhar nahi.",
                             "Acute watery diarrhoea", "icd_a09", [("drug_ors", "200 ml after each loose stool", "po", "prn", 3, "Rehydration"), ("drug_zinc_20", "1 tab", "po", "od", 14, "WHO recommendation")], days_ago=9)
        self._signed_consult(P("zainab"), paeds, farhan, "Diarrhoea in a child", "Bachi ko do din se dast hain, din mein aath dus dafa, thora bukhar. Pee rahi hai. Aankhein thori dhansi hui.",
                             "Acute diarrhoea with some dehydration", "icd_a09", [("drug_ors", "75 ml/kg over 4 hours then after each stool", "po", "prn", 3, "Plan B rehydration"), ("drug_zinc_20", "20 mg", "po", "od", 14, "IMCI")], days_ago=6,
                             vitals={"bp_sys": 96, "bp_dia": 60, "heart_rate": 118, "resp_rate": 24, "temperature": 38.1, "spo2": 98, "weight": 22})
        self._signed_consult(P("saima"), med, ayesha, "Fever for six days", "Continuous fever for six days, headache, abdominal discomfort, constipation, no rash. Took paracetamol only.",
                             "Enteric (typhoid) fever", "icd_a01_0", [("drug_azithromycin_500", "1 tab", "po", "od", 7, "XDR typhoid first-line"), ("drug_paracetamol_500", "1 tab", "po", "tds", 5, "Antipyretic")], tests=("test_cbc", "test_typhidot"), days_ago=12)
        self._signed_consult(P("fatima"), med, ayesha, "Sore throat and cold", "Sore throat, runny nose and sneezing for three days, mild cough, no fever.",
                             "Acute upper respiratory infection", "icd_j06_9", [("drug_paracetamol_500", "1 tab", "po", "tds", 3, "Symptomatic"), ("drug_cetirizine_10", "1 tab", "po", "hs", 5, "Rhinorrhoea")], days_ago=4)
        self._signed_consult(P("karim"), card, bilal, "Post-CABG follow-up, sternal wound check", "Doctor, the wound is healing well, it itches a little at night. I walked to the market yesterday, no chest pain, no breathlessness. I am taking all the tablets, but the small white one upsets my stomach.",
                             "Post-CABG follow-up — sternal wound check", "icd_i20_0", [("drug_cetirizine_10", "1 tab", "po", "hs", 7, "Night-time itch at the sternal wound"), ("drug_omeprazole_20", "1 cap", "po", "od", 14, "Aspirin-induced dyspepsia")], tests=("test_ecg",), days_ago=2)

        # a learned rule taught by Dr. Bilal
        env["hms.ai.rule"].create({"doctor_id": bilal.id, "department_id": card.id, "scope": "doctor", "trigger_keywords": "sternal wound, itch, itching, night", "min_matches": 2,
                                   "drug_id": self._ref("drug_cetirizine_10").id, "dose": "1 tab", "route": "po", "frequency": "hs", "duration_days": 7, "reason": "Sternal wound itch at night — my standard answer"})

        # ---- today ----
        now = fields.Datetime.now()
        Visit = env["hms.visit"]
        # 1. Rashid Ahmed — the STEMI story: registered with discount pending (held)
        rashid = Visit.create({"patient_id": P("rashid").id, "department_id": med.id, "doctor_id": ayesha.id, "complaint": "Central chest pain radiating to left arm for 2 hours, with sweating", "arrival_time": now - timedelta(minutes=55)})
        rashid.consent_ids.write({"state": "signed", "signed_at": now - timedelta(minutes=50), "signed_by_name": "Rashid Ahmed", "taken_by_id": S("nasreen").id})
        env["hms.discount.request"].create({"visit_id": rashid.id, "percent": 15, "reason": "hardship", "reason_note": "Son requested concession; family runs a small shop", "requested_by_id": S("nasreen").id})
        # 2. Mizan Akhtar — COPD flare, triaged, in Dr. Ayesha's queue
        mizan = Visit.create({"patient_id": P("mizan").id, "department_id": med.id, "doctor_id": ayesha.id, "complaint": "Worsening breathlessness and productive cough for 3 days", "arrival_time": now - timedelta(minutes=70)})
        env["hms.vitals"].create({"visit_id": mizan.id, "nurse_id": hina.id, "bp_sys": 138, "bp_dia": 84, "heart_rate": 98, "resp_rate": 24, "temperature": 37.6, "spo2": 91, "weight": 64})
        env["hms.order"].create({"visit_id": mizan.id, "test_id": self._ref("test_cbc").id, "urgency": "urgent", "ordered_by_id": ayesha.id, "reason": "Infective exacerbation?"})
        env["hms.order"].create({"visit_id": mizan.id, "test_id": self._ref("test_cxr").id, "urgency": "urgent", "ordered_by_id": ayesha.id})
        # 3. Bilal Khan (child) — fever & loose motions, triaged to paeds
        bk = Visit.create({"patient_id": P("bilal_k").id, "department_id": paeds.id, "doctor_id": farhan.id, "complaint": "Loose motions and fever for 2 days", "arrival_time": now - timedelta(minutes=40)})
        env["hms.vitals"].create({"visit_id": bk.id, "nurse_id": hina.id, "heart_rate": 124, "resp_rate": 28, "temperature": 38.4, "spo2": 97, "weight": 15})
        env["hms.order"].create({"visit_id": bk.id, "test_id": self._ref("test_stool_re").id, "urgency": "routine", "ordered_by_id": farhan.id})
        # 4. Saima — follow-up, registered, waiting for vitals
        Visit.create({"patient_id": P("saima").id, "department_id": med.id, "doctor_id": ayesha.id, "complaint": "Follow-up after typhoid — feeling better, still weak", "visit_type": "followup", "arrival_time": now - timedelta(minutes=20)})
        # 5. Iqbal — ER chest pain, high EWS, with cardiology
        iq = Visit.create({"patient_id": P("iqbal").id, "department_id": card.id, "doctor_id": bilal.id, "complaint": "Chest tightness and sweating since morning", "visit_type": "er", "arrival_time": now - timedelta(minutes=30)})
        env["hms.vitals"].create({"visit_id": iq.id, "nurse_id": hina.id, "bp_sys": 96, "bp_dia": 62, "heart_rate": 112, "resp_rate": 22, "temperature": 36.8, "spo2": 93})
        trop = env["hms.order"].create({"visit_id": iq.id, "test_id": self._ref("test_trop").id, "urgency": "stat", "ordered_by_id": bilal.id, "reason": "Chest pain, rule out ACS"})
        trop.write({"scanned_band": P("iqbal").mrn, "scanned_specimen": trop.specimen_barcode})
        trop.action_collect()
        trop.write({"result_value": "4.82"})
        trop.action_enter_result()
        trop.action_verify_release()  # critical → call log opens
        env["hms.order"].create({"visit_id": iq.id, "test_id": self._ref("test_ecg").id, "urgency": "stat", "ordered_by_id": bilal.id})
        # 6. Karim Uddin — admitted post-CABG day 10 in CCU with orders and MAR
        kv = Visit.create({"patient_id": P("karim").id, "department_id": card.id, "doctor_id": bilal.id, "complaint": "Post-CABG observation — atrial fibrillation overnight", "visit_type": "ipd", "arrival_time": now - timedelta(days=1, hours=6)})
        kv.consent_ids.write({"state": "signed", "signed_at": now - timedelta(days=1), "signed_by_name": "Karim Uddin", "taken_by_id": S("nasreen").id})
        adm = env["hms.admission"].create({"visit_id": kv.id, "patient_id": P("karim").id, "doctor_id": bilal.id, "department_id": card.id, "ward_id": self._ref("ward_ccu").id, "bed_id": self._ref("bed_ccu_1").id, "diagnosis": "Post-CABG day 10; paroxysmal AF", "admitted_at": now - timedelta(days=1, hours=5)})
        env["hms.vitals"].create({"visit_id": kv.id, "admission_id": adm.id, "nurse_id": hina.id, "bp_sys": 124, "bp_dia": 72, "heart_rate": 88, "resp_rate": 17, "temperature": 36.8, "spo2": 97})
        env["hms.ward.order"].create({"admission_id": adm.id, "doctor_id": bilal.id, "order_type": "medication", "drug_id": self._ref("drug_enoxaparin_60").id, "dose": "60 mg", "route": "sc", "frequency": "bd", "duration_days": 3, "instruction": "Anticoagulation for new AF"})
        env["hms.ward.order"].create({"admission_id": adm.id, "doctor_id": bilal.id, "order_type": "medication", "drug_id": self._ref("drug_bisoprolol_5").id, "dose": "5 mg", "route": "po", "frequency": "od", "duration_days": 3, "instruction": "Rate control"})
        env["hms.progress.note"].create({"admission_id": adm.id, "doctor_id": bilal.id, "note": "Day 10 post off-pump CABG. Sternal wound clean. AF overnight, rate 110-130, now 88 on bisoprolol. Haemodynamically stable.", "plan": "Enoxaparin, continue bisoprolol, echo tomorrow, mobilise."})
        ho = env["hms.handoff"].create({"admission_id": adm.id, "from_nurse_id": hina.id, "to_nurse_id": hina.id, "shift": "night"})
        ho.action_ai_draft()
        ho.action_send()
        # 7. a scheduled surgery for tomorrow
        fv = Visit.create({"patient_id": P("fatima").id, "department_id": D("surgery").id, "doctor_id": sana.id, "complaint": "Symptomatic gallstones — planned laparoscopic cholecystectomy", "arrival_time": now - timedelta(minutes=10)})
        env["hms.surgery"].create({"visit_id": fv.id, "procedure": "Laparoscopic cholecystectomy", "surgeon_id": sana.id, "anaesthetist_id": ayesha.id, "theatre_id": self._ref("theatre_1").id, "scheduled_at": now + timedelta(days=1, hours=2), "price": 85000, "anaesthesia_type": "ga"})
        _logger.info("Stratos HMS demo scenario generated.")
        return True
