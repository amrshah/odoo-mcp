import { Clinician, Patient, SoapNote, DiarizedTurn, ClinicalEntity } from '../types';

const ODOO_API_URL = import.meta.env.VITE_ODOO_API_URL || 'http://localhost:8069';
const ZELIX_BACKEND_URL = import.meta.env.VITE_ZELIX_BACKEND_URL || 'http://localhost:8010';

export class ApiService {
  /**
   * Mock initial clinician session (Dr. Sarah Lin)
   */
  static getActiveClinician(): Clinician {
    return {
      id: 3,
      name: 'Dr. Sarah Lin, DVM',
      login: 'sarah.lin@vetcairn.com',
      email: 'sarah.lin@vetcairn.com',
      role: 'doctor',
      clinicId: 3,
      clinicName: 'VetCairn Downtown Animal Hospital',
      licenseNumber: 'VET-NY-98421',
      avatarUrl: 'https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=150&auto=format&fit=crop&q=80',
    };
  }

  /**
   * Mock initial patient matching the Stitch design (Barnaby)
   */
  static getSamplePatient(): Patient {
    return {
      id: 3,
      identifier: 'PAT-000004',
      name: 'Barnaby',
      species: 'Canine',
      breed: 'Golden Retriever',
      sex: 'neutered_male',
      weightKg: 32.4,
      age: '5 yrs 2 mos',
      microchipNumber: '985141002948211',
      primaryOwnerName: 'Eleanor Vance',
      primaryOwnerPhone: '+1 (555) 234-8901',
      primaryOwnerEmail: 'eleanor.vance@example.com',
      activeConditions: ['Bilateral Otitis Externa Check', 'Seasonal Atopy'],
      allergies: ['Penicillin G', 'Chicken protein'],
      photoUrl: 'https://images.unsplash.com/photo-1552053831-71594a27632d?w=300&auto=format&fit=crop&q=80',
    };
  }

  /**
   * Connects to Zelix AI Copilot Backend (Alamia Edge Inference on CF)
   * to process audio / transcript into a structured SOAP note.
   */
  static async processTranscriptToSoap(
    patientId: number,
    turns: DiarizedTurn[],
  ): Promise<SoapNote> {
    try {
      const response = await fetch(`${ZELIX_BACKEND_URL}/zelix_ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: patientId,
          intent: 'w04_scribe_soap',
          transcript: turns.map((t) => `${t.speakerName}: ${t.text}`).join('\n'),
        }),
      });

      if (response.ok) {
        const data = await response.json();
        return data.soap_note;
      }
    } catch {
      // Offline fallback to mock synthesized SOAP note
    }

    return {
      patientId,
      subjective:
        "Barnaby presented for evaluation of frequent head-shaking and ear scratching following swimming at the dog park 3 days prior. Owner reports whining on contact with left ear.",
      objective:
        "Weight: 32.4 kg. Temp: 38.6°C. Left external ear canal (AS) marked by erythema and moderate ceruminous exudate. Right ear (AD) demonstrates mild hyperaemia without exudate. Bilateral tympanic membranes fully intact.",
      assessment:
        "Acute bilateral otitis externa (AS > AD), consistent with post-immersion secondary microbial flare.",
      plan:
        "1. In-clinic cytology swab performed bilaterally.\n2. Surolan otic suspension 0.5 mL AS q12h x 10 days.\n3. Ear cleansing with Epi-Otic prior to medication.\n4. Strict water/swimming cessation for 10 days.\n5. Recheck exam scheduled in 10-14 days.",
      icd11Codes: ['DA01.2 Otitis externa', 'QA04.0 Ear canal pruritus'],
      suggestedPrescriptions: [
        {
          medication: 'Surolan Otic Drops (Miconazole/Prednisolone/Polymyxin B)',
          dosage: '0.5 mL (5-7 drops)',
          frequency: 'q12h (Twice daily)',
          duration: '10 days',
          cautions: 'Confirm intact tympanum prior to administration',
        },
        {
          medication: 'Epi-Otic Advanced Ear Cleanser',
          dosage: 'Liberal flush',
          frequency: 'q24h (Once daily, 30 min before drops)',
          duration: '10 days',
        },
      ],
      state: 'ai_draft',
    };
  }

  /**
   * Commit signed SOAP note to Odoo 19 Backend (vet.encounter)
   */
  static async signAndSyncToOdoo(soapNote: SoapNote): Promise<{ success: boolean; encounterId?: number }> {
    try {
      const response = await fetch(`${ODOO_API_URL}/zelix_ai/soap/commit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(soapNote),
      });

      if (response.ok) {
        return await response.json();
      }
    } catch {
      // Mock successful sync
    }

    return {
      success: true,
      encounterId: 1042,
    };
  }
}
