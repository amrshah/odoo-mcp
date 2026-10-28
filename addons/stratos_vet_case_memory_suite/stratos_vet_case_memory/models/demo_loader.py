"""50 finalised demo cases, replayed through the real engine.

Each historical case is entered as a draft, the suggestion engine is run,
the demo vet approves what matches the real treatment and rejects the
rest, missing items are added by hand, the case is finalised and the
outcome recorded. So the decision history, knowledge base and reports
are genuine, and the engine visibly "learns" as the history grows.
"""
import random
from datetime import datetime, timedelta

from odoo import _, api, models

R = "stratos_vet_case_memory."

# (key, species, count, breeds, age months, weight kg, core signs, optional
#  signs, temp, heart rate, resp rate, diagnosis, tests, drugs, outcomes,
#  variants {index: (tests, drugs)}, sex, repro)
CONDITIONS = [
    ("parvo", "dog", 6, ["German Shepherd", "Labrador Retriever", "Mixed breed", "Rottweiler",
                         "Siberian Husky", "Golden Retriever"],
     (2, 8), (3, 14), ["vomiting", "bloody_diarrhoea", "lethargy", "anorexia"],
     ["fever", "dehydration", "abdominal_pain"], (39.4, 40.6), (120, 170), (25, 40),
     "parvo", ["parvo_snap", "cbc"],
     [("fluids", 0, "Continuous", 3), ("maropitant", 1, "Once daily", 3),
      ("metronidazole", 15, "Twice daily", 5), ("ampicillin", 22, "Three times daily", 5)],
     ["resolved", "resolved", "resolved", "improved", "not_improved", "died"],
     {4: (["parvo_snap"], [("metronidazole", 15, "Twice daily", 5)]),
      5: (["parvo_snap"], [("metronidazole", 15, "Twice daily", 5)])}, None, "intact"),
    ("babesia", "dog", 5, ["German Shepherd", "Bully Kutta", "Labrador Retriever", "Mixed breed",
                           "Pakistani Mastiff"],
     (18, 96), (18, 42), ["fever", "pale_gums", "lethargy", "anorexia"],
     ["dark_urine", "lymph"], (39.8, 41.0), (110, 150), (24, 40),
     "babesia", ["smear", "cbc"],
     [("imidocarb", 6.6, "Once, repeat after 14 days", 1), ("doxycycline", 10, "Once daily", 21)],
     ["resolved", "resolved", "improved", "resolved", "improved"], {}, None, "intact"),
    ("gastro", "dog", 4, ["Labrador Retriever", "Shih Tzu", "Mixed breed", "Golden Retriever"],
     (12, 84), (6, 35), ["vomiting", "diarrhoea"], ["anorexia", "abdominal_pain", "lethargy"],
     (38.5, 39.3), (90, 120), (18, 30), "gastro", ["faecal"],
     [("maropitant", 1, "Once daily", 3), ("metronidazole", 15, "Twice daily", 5),
      ("famotidine", 0.5, "Twice daily", 5)],
     ["resolved"] * 4, {}, None, "intact"),
    ("mange", "dog", 3, ["Mixed breed", "German Shepherd", "Bully Kutta"],
     (6, 60), (10, 35), ["pruritus", "alopecia", "crusts"], ["weight_loss"],
     (38.4, 39.2), (80, 110), (16, 26), "mange", ["scraping"],
     [("ivermectin", 0.3, "Once weekly", 3), ("chlorhex", 0, "Twice weekly", 21)],
     ["resolved", "improved", "resolved"], {}, None, "intact"),
    ("otitis", "dog", 2, ["Labrador Retriever", "Golden Retriever"],
     (24, 96), (25, 35), ["head_shaking", "ear_discharge"], ["pruritus"],
     (38.4, 39.0), (80, 110), (16, 24), "otitis", ["ear_cyto"],
     [("otic", 0, "Twice daily", 7), ("meloxicam", 0.1, "Once daily", 5)],
     ["resolved", "resolved"], {}, None, "intact"),
    ("flutd", "cat", 5, ["Persian", "Domestic shorthair", "Himalayan", "Persian", "Siamese"],
     (24, 96), (3.5, 6.5), ["straining", "haematuria", "frequent_urination"],
     ["abdominal_pain", "lethargy"], (38.3, 39.2), (150, 200), (24, 36), "flutd",
     ["urinalysis", "us_abd"], [("buprenorphine", 0.02, "Three times daily", 3)],
     ["resolved", "resolved", "improved", "resolved", "improved"], {}, "male", "neutered"),
    ("uri", "cat", 5, ["Persian", "Domestic shorthair", "Siamese", "Himalayan", "Persian"],
     (3, 60), (1.5, 5.0), ["sneezing", "nasal_discharge", "ocular_discharge"],
     ["fever", "anorexia"], (39.2, 40.2), (160, 210), (28, 40), "uri", ["felv"],
     [("doxycycline", 5, "Twice daily", 7)],
     ["resolved", "resolved", "improved", "resolved", "not_improved"],
     {4: (["felv"], [("amoxiclav", 12.5, "Twice daily", 7)])}, None, "intact"),
    ("fad", "cat", 2, ["Domestic shorthair", "Persian"],
     (12, 72), (3.0, 5.5), ["pruritus", "fleas", "alopecia"], ["crusts"],
     (38.4, 39.1), (150, 190), (24, 32), "fad", ["scraping"],
     [("fipronil", 0, "Once monthly", 1)], ["resolved", "resolved"], {}, None, "neutered"),
    ("mastitis", "cattle", 6, ["Sahiwal", "Holstein Friesian cross", "Cholistani", "Sahiwal",
                               "Red Sindhi", "Holstein Friesian cross"],
     (36, 96), (350, 550), ["swollen_udder", "abnormal_milk", "milk_drop"], ["fever", "anorexia"],
     (39.3, 40.8), (70, 95), (24, 40), "mastitis", ["cmt", "milk_cs"],
     [("cloxacillin", 0, "Twice daily", 3), ("meloxicam", 0.5, "Once daily", 3)],
     ["resolved", "resolved", "improved", "resolved", "resolved", "improved"],
     {5: (["cmt", "milk_cs"], [("ceftiofur", 2.2, "Once daily", 5),
                               ("cloxacillin", 0, "Twice daily", 3)])}, "female", "lactating"),
    ("theileria", "cattle", 4, ["Holstein Friesian cross", "Sahiwal", "Holstein Friesian cross",
                                "Cholistani"],
     (24, 84), (300, 500), ["fever", "lymph", "anorexia", "pale_gums"], ["milk_drop", "lethargy"],
     (40.0, 41.5), (80, 110), (30, 50), "theileria", ["smear", "cbc"],
     [("buparvaquone", 2.5, "Once, repeat after 48–72 h if needed", 1),
      ("oxytet", 20, "Once, repeat after 72 h", 2)],
     ["resolved", "improved", "resolved", "died"], {}, "female", "lactating"),
    ("brucella", "cattle", 2, ["Sahiwal", "Holstein Friesian cross"],
     (30, 72), (350, 480), ["abortion", "retained_placenta"], ["fever"],
     (38.6, 39.6), (65, 85), (20, 32), "brucella", ["rbpt"], [],
     ["improved", "improved"], {}, "female", "intact"),
    ("ppr", "goat", 3, ["Beetal", "Teddy", "Kamori"],
     (6, 24), (15, 35), ["fever", "nasal_discharge", "mouth_lesions", "diarrhoea"],
     ["ocular_discharge", "cough"], (40.0, 41.2), (90, 120), (30, 45), "ppr", ["ppr_ag"],
     [("oxytet", 20, "Once, repeat after 72 h", 2)],
     ["improved", "resolved", "died"], {}, None, "intact"),
    ("pneumonia", "goat", 3, ["Beetal", "Dera Din Panah", "Teddy"],
     (8, 48), (18, 45), ["cough", "nasal_discharge", "dyspnoea", "fever"], ["anorexia"],
     (39.8, 41.0), (90, 130), (35, 55), "pneumonia", ["cbc"],
     [("oxytet", 20, "Once, repeat after 72 h", 2), ("meloxicam", 0.5, "Once daily", 3)],
     ["resolved", "resolved", "improved"], {}, None, "intact"),
]

PET_NAMES = ["Tiger", "Moti", "Sheru", "Max", "Bella", "Leo", "Coco", "Simba", "Luna", "Oscar",
             "Zara", "Buddy", "Rex", "Shadow", "Toby", "Daisy", "Lucky", "Raja", "Kaalu", "Jimmy",
             "Billo", "Snowy", "Kitty", "Ginger", "Misty", "Lucy", "Whiskers", "Pari", "Shiro",
             "Nala", "Tom", "Cookie"]
PET_OWNERS = ["Ahmed Raza", "Fatima Khan", "Usman Tariq", "Sana Javed", "Bilal Hussain",
              "Mehwish Ali", "Hassan Shah", "Ayesha Siddiqui", "Omer Farooq", "Hira Batool",
              "Kamran Akmal", "Nadia Rehman"]
FARM_OWNERS = ["Haji Muhammad Aslam (Dairy Farm, Okara)", "Chaudhry Riaz (Pattoki Dairy)",
               "Malik Nawaz (Goat Farm, Chakwal)", "Rana Shahid (Sahiwal Livestock)",
               "Sardar Imtiaz (Cattle Farm, Gujranwala)"]
REJECT_REASONS = ["not_fit", "better_option", "owner", "not_fit", "not_fit"]

VOICE_SAMPLES = {
    "parvo": "Owner says the puppy has been vomiting since yesterday and has bloody diarrhoea. "
             "Not eating, very lethargic. Temperature 40.2. Heart rate 160. Gums tacky, "
             "looks dehydrated. Suspect parvo. Plan parvo test and start fluids.",
    "mastitis": "Cow has a swollen and hot udder on the left hind quarter, clots in milk, "
                "milk drop since two days. Temperature 40.1. Looks like clinical mastitis. "
                "Plan CMT and milk culture.",
    "uri": "Cat sneezing a lot with nasal discharge and watery eyes. Mild fever, temperature "
           "39.6. Still eating a little. Likely upper respiratory infection.",
}


class VetCmDemoLoader(models.AbstractModel):
    _name = "vet.cm.demo.loader"
    _description = "Vet Case Memory demo data loader"

    @api.model
    def _users(self):
        Users = self.env["res.users"].with_context(no_reset_password=True)
        vet_g = self.env.ref(R + "group_vet_cm_vet")
        mgr_g = self.env.ref(R + "group_vet_cm_manager")
        nurse_g = self.env.ref(R + "group_vet_cm_nurse")
        user_g = self.env.ref("base.group_user")
        out = {}
        for login, name, group in [("dr.ayesha", "Dr. Ayesha Malik", mgr_g),
                                   ("dr.hamza", "Dr. Hamza Qureshi", vet_g),
                                   ("nurse.sana", "Sana Iqbal (Vet Nurse)", nurse_g)]:
            u = Users.search([("login", "=", login)], limit=1)
            if not u:
                u = Users.create({"login": login, "name": name, "password": login + "123",
                                  "group_ids": [(6, 0, [user_g.id, group.id])]})
            out[login] = u
        return out

    @api.model
    def action_load_demo(self):
        Case = self.env["vet.cm.case"].sudo()
        if Case.search_count([("is_demo", "=", True)]):
            return self._notify(_("Demo cases are already loaded."))
        rng = random.Random(42)
        users = self._users()
        vets = [users["dr.ayesha"], users["dr.hamza"]]
        ref = lambda x: self.env.ref(R + x)

        pet_owners = [self.env["res.partner"].create({"name": n, "phone": f"0300-{1234500 + i}"})
                      for i, n in enumerate(PET_OWNERS)]
        farm_owners = [self.env["res.partner"].create({"name": n, "phone": f"0321-{7654300 + i}"})
                       for i, n in enumerate(FARM_OWNERS)]

        # Build all 50 histories, then shuffle into a timeline.
        histories = []
        for (key, sp, n, breeds, age, wt, core, opt, temp, hr, rr, dx, tests, drugs,
             outcomes, variants, sex, repro) in CONDITIONS:
            for i in range(n):
                t, d = variants.get(i, (tests, drugs))
                histories.append(dict(
                    key=key, sp=sp, breed=breeds[i % len(breeds)],
                    age=rng.randint(*age), weight=round(rng.uniform(*wt), 1),
                    symptoms=core + rng.sample(opt, k=rng.randint(0, min(2, len(opt)))),
                    temp=round(rng.uniform(*temp), 1), hr=rng.randint(*hr), rr=rng.randint(*rr),
                    dx=dx, tests=t, drugs=d, outcome=outcomes[i],
                    sex=sex or rng.choice(["male", "female"]), repro=repro))
        rng.shuffle(histories)
        start = datetime(2026, 4, 1, 9, 0)
        step = (datetime(2026, 10, 20, 9, 0) - start) / len(histories)
        pet_i = farm_i = 0
        tag_no = {"cattle": 100, "goat": 200}
        for idx, h in enumerate(histories):
            date = start + step * idx + timedelta(hours=rng.randint(0, 7))
            vet = vets[idx % 2]
            if h["sp"] in ("dog", "cat"):
                name, owner = PET_NAMES[pet_i % len(PET_NAMES)], pet_owners[pet_i % len(pet_owners)]
                pet_i += 1
            else:
                tag_no[h["sp"]] += 1
                prefix = "Cow" if h["sp"] == "cattle" else "Goat"
                name, owner = f"{prefix} #{tag_no[h['sp']]}", farm_owners[farm_i % len(farm_owners)]
                farm_i += 1
            self._replay(h, name, owner, vet, date, rng, ref)

        self._open_cases(pet_owners, farm_owners, vets, ref)
        return self._notify(_("50 finalised demo cases and 6 open cases loaded."))

    @api.model
    def _replay(self, h, name, owner, vet, date, rng, ref):
        env_vet = self.with_user(vet).env
        case = env_vet["vet.cm.case"].create({
            "animal_name": name, "owner_id": owner.id, "species_id": ref("sp_" + h["sp"]).id,
            "breed": h["breed"], "sex": h["sex"], "repro_status": h["repro"],
            "age_months": h["age"], "weight_kg": h["weight"], "temperature": h["temp"],
            "heart_rate": h["hr"], "resp_rate": h["rr"], "date": date, "vet_id": vet.id,
            "complaint": ", ".join(ref("sym_" + s).name for s in h["symptoms"]),
            "symptom_ids": [(6, 0, [ref("sym_" + s).id for s in h["symptoms"]])],
            "is_demo": True,
        })
        if h["key"] in VOICE_SAMPLES and rng.random() < 0.5:
            note = env_vet["vet.cm.voice.note"].browse(case.add_voice_note(VOICE_SAMPLES[h["key"]]))
            note.action_apply()
            note.sudo().write({"create_date": date})

        sug = env_vet["vet.cm.suggestion"]._run_engine(case)
        real = {("diagnosis", ref("dx_" + h["dx"]).id)}
        real |= {("test", ref("test_" + t).id) for t in h["tests"]}
        doses = {ref("drug_" + d).id: (mg, fq, dy) for d, mg, fq, dy in h["drugs"]}
        real |= {("drug", i) for i in doses}
        when = date + timedelta(minutes=20)
        for line in sug.line_ids.filtered(lambda l: not l.blocked):
            rec = line.diagnosis_id or line.test_id or line.drug_id
            if (line.item_type, rec.id) in real:
                if line.item_type == "drug":
                    mg, fq, dy = doses[rec.id]
                    line.write({"final_mgkg": mg or line.final_mgkg,
                                "final_frequency": fq, "final_days": dy})
                line.action_approve()
            else:
                reason = ("not_fit" if line.item_type != "drug"
                          else rng.choice(REJECT_REASONS))
                env_vet["vet.cm.reject.wizard"].create({
                    "line_ids": [(6, 0, line.ids)],
                    "reason_type": reason,
                }).action_confirm()
        sug.sudo().write({"date": date + timedelta(minutes=10)})
        sug.line_ids.sudo().write({"decided_on": when})

        # Items the vet added that the system did not suggest
        if not case.diagnosis_id:
            case.diagnosis_id = ref("dx_" + h["dx"])
        for t in h["tests"]:
            if ref("test_" + t) not in case.test_line_ids.test_id:
                env_vet["vet.cm.case.test"].create({"case_id": case.id,
                                                    "test_id": ref("test_" + t).id})
        for d, mg, fq, dy in h["drugs"]:
            if ref("drug_" + d) not in case.treatment_line_ids.drug_id:
                env_vet["vet.cm.case.treatment"].create({
                    "case_id": case.id, "drug_id": ref("drug_" + d).id,
                    "dose_mgkg": mg, "frequency": fq, "days": dy})
        case.test_line_ids.write({"state": "done"})
        case.treatment_line_ids.write({"state": "confirmed"})
        case.plan = "; ".join(case.test_line_ids.test_id.mapped("name") +
                              case.treatment_line_ids.drug_id.mapped("name"))
        case.action_finalise()
        case.write({"outcome": h["outcome"], "outcome_date": (date + timedelta(days=7)).date(),
                    "outcome_note": {
                        "resolved": "Recheck: clinically normal.",
                        "improved": "Recheck: improving, continue care.",
                        "not_improved": "Recheck: no improvement, referred / plan changed.",
                        "died": "Animal died / euthanised.",
                    }[h["outcome"]]})

    @api.model
    def _open_cases(self, pet_owners, farm_owners, vets, ref):
        Case = self.env["vet.cm.case"].sudo()
        now = datetime.now()
        open_defs = [
            ("Bruno", "dog", "Labrador Retriever", 4, 9.0, "male", "intact", pet_owners[0],
             [], "Vomiting and bloody stool since yesterday – owner very worried.", 0, 0, 0),
            ("Mano", "cat", "Persian", 36, 4.2, "female", "neutered", pet_owners[1],
             ["sneezing", "nasal_discharge", "ocular_discharge", "fever"],
             "Sneezing for 3 days, eyes watering.", 39.7, 190, 34),
            ("Cow #A-112", "cattle", "Sahiwal", 60, 420.0, "female", "lactating", farm_owners[0],
             ["swollen_udder", "abnormal_milk", "milk_drop", "fever"],
             "Milk has clots, udder hard and hot.", 40.3, 88, 32),
            ("Buffalo #B-07", "buffalo", "Nili-Ravi", 72, 550.0, "female", "lactating",
             farm_owners[1], ["swollen_udder", "abnormal_milk", "milk_drop"],
             "Swollen quarter, watery milk.", 39.9, 70, 28),
            ("Rocky", "dog", "Rough Collie", 36, 25.0, "male", "intact", pet_owners[2],
             ["pruritus", "alopecia", "crusts"], "Scratching all night, bald patches.",
             38.8, 95, 20),
            ("Goat #G-31", "goat", "Beetal", 12, 30.0, "female", "intact", farm_owners[2],
             ["fever", "nasal_discharge", "mouth_lesions", "diarrhoea"],
             "Several goats in the herd sick; sores in mouth.", 40.8, 110, 40),
        ]
        for i, (name, sp, breed, age, wt, sex, repro, owner, syms, complaint, t, hr, rr) in \
                enumerate(open_defs):
            case = Case.create({
                "animal_name": name, "species_id": ref("sp_" + sp).id, "breed": breed,
                "age_months": age, "weight_kg": wt, "sex": sex, "repro_status": repro,
                "owner_id": owner.id, "complaint": complaint, "temperature": t,
                "heart_rate": hr, "resp_rate": rr, "vet_id": vets[i % 2].id,
                "date": now - timedelta(minutes=30 * (6 - i)), "is_demo": True,
                "symptom_ids": [(6, 0, [ref("sym_" + s).id for s in syms])],
            })
            if name == "Bruno":
                case.with_user(vets[0]).add_voice_note(VOICE_SAMPLES["parvo"])

    @api.model
    def _notify(self, msg):
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("Vet Clinical Suggestions"), "message": msg,
                           "type": "success", "sticky": False,
                           "next": {"type": "ir.actions.act_window_close"}}}
