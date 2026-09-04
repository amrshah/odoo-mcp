from datetime import timedelta
from odoo import fields

def _track(env, record, sequence, label=None):
    env["vet.demo.registry"].sudo().create({"model_name":record._name,"res_id":record.id,"sequence":sequence,"label":label or record.display_name})
    return record

def post_init_hook(env):
    now=fields.Datetime.now(); today=fields.Date.context_today(env["vet.patient"]); company=env.company; user=env.ref("base.user_admin")
    clinic=_track(env,env["vet.clinic"].create({"name":"VetCairn Demo Hospital","code":"DEMO-HOSP","company_id":company.id,"opening_hour":8,"closing_hour":20}),10)
    species=[]
    for i,(name,code) in enumerate((("Demo Canine","DCAN"),("Demo Feline","DFEL"),("Demo Rabbit","DRAB"))):
        sp=_track(env,env["vet.species"].create({"name":name,"code":code}),11+i); species.append(sp); _track(env,env["vet.breed"].create({"name":f"{name} Mixed Breed","species_id":sp.id}),20+i)
    appt_type=_track(env,env["vet.appointment.type"].create({"name":"Demo Consultation","code":"DEMO-CONS","company_id":company.id,"duration":0.5}),25)
    diag_type=_track(env,env["vet.diagnostic.type"].create({"name":"Demo Wellness Panel","code":"DEMO-LAB","company_id":company.id,"category":"laboratory"}),26)
    vaccines=[_track(env,env["vet.vaccine.protocol"].create({"name":f"Demo Annual Vaccine {i+1}","code":f"DEMO-VAX-{i+1}","company_id":company.id,"species_id":sp.id,"booster_interval_months":12}),27+i) for i,sp in enumerate(species)]
    med=_track(env,env["vet.medication"].create({"name":"Demo Amoxicillin","code":"DEMO-AMOX","company_id":company.id,"dosage_form":"tablet","default_route":"oral"}),28)
    reminder_type=_track(env,env["vet.reminder.type"].create({"name":"Demo Follow-up","code":"DEMO-FUP","company_id":company.id,"default_channel":"phone","subject_template":"Demo clinical follow-up","message_template":"Call the client and record recovery progress."}),29)
    task_type=_track(env,env["vet.task.type"].create({"name":"Demo Care Follow-up","code":"DEMO-CARE","company_id":company.id,"clinical":True}),30)
    doc_type=_track(env,env["vet.document.type"].create({"name":"Demo Consent","code":"DEMO-CONSENT","company_id":company.id}),31)
    diagnosis=_track(env,env["vet.diagnosis"].create({"name":"Demo Gastroenteritis","code":"DEMO-GE","company_id":company.id,"category":"other"}),32)
    comm_template=_track(env,env["vet.communication.template"].create({"name":"Demo Recovery Call","company_id":company.id,"channel":"phone","subject":"Recovery check","body":"<p>Record appetite, comfort, and medication tolerance.</p>"}),33)
    product=_track(env,env["product.product"].create({"name":"Demo Veterinary Consultation","is_vet_item":True,"vet_item_type":"service","type":"service","list_price":65.0}),34)
    ward=_track(env,env["vet.ward"].create({"name":"Demo Recovery Ward","clinic_id":clinic.id}),35)
    beds=[_track(env,env["vet.bed"].create({"name":f"Demo Cage {i+1}","ward_id":ward.id}),36+i) for i in range(3)]
    insurers=[_track(env,env["res.partner"].create({"name":f"Demo Pet Insurance {i+1}","is_company":True}),40+i) for i in range(3)]
    cases=(("Bailey","Jordan Smith","phone","555-0101"),("Luna","Taylor Jones","email","555-0102"),("Milo","Morgan Lee","phone","555-0103"))
    for i,(pet,owner,channel,phone) in enumerate(cases):
        seq=100+i*30
        client=_track(env,env["res.partner"].create({"name":owner,"is_vet_client":True,"phone":phone,"email":f"demo{i+1}@example.test","vet_preferred_clinic_id":clinic.id}),seq)
        patient=_track(env,env["vet.patient"].create({"name":pet,"clinic_id":clinic.id,"species_id":species[i].id,"birthdate":today-timedelta(days=365*(i+2)),"ownership_ids":[(0,0,{"partner_id":client.id,"is_primary":True})]}),seq+1)
        appointment=_track(env,env["vet.appointment"].create({"clinic_id":clinic.id,"patient_id":patient.id,"provider_id":user.id,"appointment_type_id":appt_type.id,"start_datetime":now+timedelta(days=i,hours=1),"reason":["Vomiting and reduced appetite","Annual wellness examination","Reduced appetite and lethargy"][i]}),seq+2)
        encounter=_track(env,env["vet.encounter"].create({"clinic_id":clinic.id,"patient_id":patient.id,"appointment_id":appointment.id,"provider_id":user.id,"chief_complaint":appointment.reason}),seq+3)
        _track(env,env["vet.diagnostic.order"].create({"clinic_id":clinic.id,"patient_id":patient.id,"encounter_id":encounter.id,"diagnostic_type_id":diag_type.id,"requested_by_id":user.id,"clinical_question":"Assess general health and hydration."}),seq+4)
        _track(env,env["vet.prescription"].create({"clinic_id":clinic.id,"patient_id":patient.id,"encounter_id":encounter.id,"prescriber_id":user.id,"medication_id":med.id,"dose":"1 tablet","route":"oral","frequency":"Twice daily","duration":"7 days","quantity":14,"instructions":"Give with food.","clinical_indication":"Demo treatment"}),seq+5)
        plan=_track(env,env["vet.treatment.plan"].create({"title":f"{pet} demo care plan","clinic_id":clinic.id,"patient_id":patient.id,"encounter_id":encounter.id,"provider_id":user.id,"care_setting":"inpatient" if i==0 else "outpatient"}),seq+6)
        _track(env,env["vet.treatment.line"].create({"plan_id":plan.id,"name":"Monitor temperature and comfort","category":"monitoring","instructions":"Record observations and escalate deterioration."}),seq+7)
        _track(env,env["vet.vaccination"].create({"clinic_id":clinic.id,"patient_id":patient.id,"protocol_id":vaccines[i].id,"planned_date":today+timedelta(days=30+i)}),seq+8)
        _track(env,env["vet.reminder"].create({"clinic_id":clinic.id,"patient_id":patient.id,"reminder_type_id":reminder_type.id,"channel":channel,"due_date":today+timedelta(days=2+i),"subject":"Demo patient follow-up","message":"Contact the client and record progress."}),seq+9)
        _track(env,env["vet.task"].create({"title":f"Review {pet} clinical progress","clinic_id":clinic.id,"task_type_id":task_type.id,"assigned_user_id":user.id,"patient_id":patient.id,"due_datetime":now+timedelta(days=1+i)}),seq+10)
        _track(env,env["vet.communication"].create({"clinic_id":clinic.id,"client_id":client.id,"patient_id":patient.id,"template_id":comm_template.id,"direction":"outbound","channel":"phone","subject":"Recovery check","body":"<p>Demo communication history entry.</p>"}),seq+11)
        _track(env,env["vet.patient.document"].create({"title":"Demo treatment consent","clinic_id":clinic.id,"patient_id":patient.id,"document_type_id":doc_type.id,"filename":"demo-consent.txt","file_data":b"RGVtbyBjb25zZW50"}),seq+12)
        charge=_track(env,env["vet.charge"].create({"clinic_id":clinic.id,"patient_id":patient.id,"appointment_id":appointment.id,"encounter_id":encounter.id,"product_id":product.id,"description":"Demo consultation charge","quantity":1,"unit_price":65}),seq+13)
        invoice=_track(env,env["account.move"].create({"move_type":"out_invoice","partner_id":client.id,"vet_patient_id":patient.id,"vet_clinic_id":clinic.id,"invoice_line_ids":[(0,0,{"product_id":product.id,"name":"Demo consultation","quantity":1,"price_unit":65})]}),seq+14)
        _track(env,env["vet.insurance.claim"].create({"clinic_id":clinic.id,"patient_id":patient.id,"insurer_id":insurers[i].id,"policy_number":f"DEMO-POL-{i+1}","invoice_id":invoice.id,"claimed_amount":50}),seq+15)
        _track(env,env["vet.financial.adjustment"].create({"clinic_id":clinic.id,"partner_id":client.id,"patient_id":patient.id,"invoice_id":invoice.id,"adjustment_type":["deposit","credit","writeoff"][i],"amount":10,"reason":"Demo financial scenario"}),seq+16)
        _track(env,env["vet.admission"].create({"clinic_id":clinic.id,"patient_id":patient.id,"encounter_id":encounter.id,"attending_id":user.id,"ward_id":ward.id,"bed_id":beds[i].id,"reason":"Demo observation admission"}),seq+17)
    batch=_track(env,env["vet.migration.batch"].create({"name":"Demo Migration Rehearsal","source":"Sanitized demonstration export","line_ids":[(0,0,{"record_type":"client","source_key":f"DEMO-{i}","payload":{"name":name}}) for i,name in enumerate(("Demo Client A","Demo Client B","Demo Client C"),1)]}),500)
    batch.action_validate()

def cleanup_demo_data(env):
    registry=env["vet.demo.registry"].sudo().search([],order="sequence desc,id desc")
    for line in registry:
        if line.model_name in env:
            record=env[line.model_name].sudo().browse(line.res_id).exists()
            if record:
                try: record.unlink()
                except Exception: pass
    registry.unlink()

def uninstall_hook(env): cleanup_demo_data(env)
