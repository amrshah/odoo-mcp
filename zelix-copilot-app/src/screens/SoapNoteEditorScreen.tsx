import React, { useState } from 'react';
import { Patient, SoapNote, ScreenId } from '../types';
import { ApiService } from '../services/api';

interface SoapNoteEditorScreenProps {
  patient: Patient;
  onNavigate: (screen: ScreenId) => void;
}

export const SoapNoteEditorScreen: React.FC<SoapNoteEditorScreenProps> = ({ patient, onNavigate }) => {
  const [soapNote, setSoapNote] = useState<SoapNote>({
    patientId: patient.id,
    subjective:
      "Barnaby presented for evaluation of frequent head-shaking and persistent left ear scratching over the past 3 days following swimming at the local dog park. Owner notes acute onset whining when touching base of left pinna.",
    objective:
      "Vitals: Weight 32.4 kg | Temp 38.6°C | HR 96 bpm | RR 24 bpm.\nEars: Left ear canal (AS) exhibits erythema, moderate dark ceruminous discharge, mild stenosis. Right ear canal (AD) clear with mild hyperaemia. Tympanic membranes intact bilaterally.\nCytology AS: Malassezia pachydermatis (3+), cocci (1+).",
    assessment:
      "Acute bilateral otitis externa (AS moderate mixed fungal/bacterial, AD mild reactive), secondary to aquatic moisture exposure.",
    plan:
      "1. Gentle mechanical ear flushing with Epi-Otic cleansing solution in-clinic.\n2. Surolan otic suspension 0.5 mL AS q12h x 10 days.\n3. Epi-Otic ear flush q24h prior to medication.\n4. Avoid all swimming and ear bathing for 10 days.\n5. Clinical re-evaluation and repeat cytology in 14 days.",
    icd11Codes: ['DA01.2 Otitis externa', 'QA04.0 Ear canal pruritus', 'XM01.4 Canine Otic Cytology'],
    suggestedPrescriptions: [
      {
        medication: 'Surolan Otic Suspension (Miconazole / Polymyxin B / Prednisolone)',
        dosage: '0.5 mL (5-7 drops) in Left Ear (AS)',
        frequency: 'q12h (Twice daily)',
        duration: '10 days',
        cautions: 'Ensure tympanum integrity confirmed prior to instillation.',
      },
      {
        medication: 'Epi-Otic Advanced Ear Cleanser',
        dosage: 'Liberal irrigation, massage ear base 60s, wipe excess',
        frequency: 'q24h (Once daily before drops)',
        duration: '10 days',
      },
    ],
    state: 'ai_draft',
  });

  const [isSigning, setIsSigning] = useState(false);
  const [syncSuccess, setSyncSuccess] = useState(false);

  const handleSignAndSync = async () => {
    setIsSigning(true);
    const result = await ApiService.signAndSyncToOdoo({
      ...soapNote,
      state: 'veterinarian_approved',
      vetSignature: 'Dr. Sarah Lin, DVM (NY-98421)',
      signedAt: new Date().toISOString(),
    });
    setIsSigning(false);
    if (result.success) {
      setSoapNote((prev) => ({
        ...prev,
        state: 'veterinarian_approved',
        vetSignature: 'Dr. Sarah Lin, DVM (NY-98421)',
      }));
      setSyncSuccess(true);
    }
  };

  return (
    <div className="flex flex-col w-full max-w-lg mx-auto px-4 pt-20 pb-28 space-y-4">
      {/* Top Status & Verification Badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 ${
              soapNote.state === 'veterinarian_approved'
                ? 'bg-secondary-fixed text-on-secondary-fixed-variant'
                : 'bg-tertiary-fixed text-on-tertiary-fixed'
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">
              {soapNote.state === 'veterinarian_approved' ? 'verified' : 'auto_awesome'}
            </span>
            <span>
              {soapNote.state === 'veterinarian_approved' ? 'Veterinarian Approved' : 'AI Draft Generated'}
            </span>
          </span>
        </div>

        <button
          onClick={() => onNavigate('voice')}
          className="text-xs text-primary font-semibold flex items-center gap-1 hover:underline"
        >
          <span className="material-symbols-outlined text-[16px]">mic</span>
          <span>View Voice Consult</span>
        </button>
      </div>

      {syncSuccess && (
        <div className="p-3 bg-secondary-fixed/40 border border-secondary/30 rounded-xl flex items-center gap-2.5 text-xs text-on-secondary-fixed-variant font-medium">
          <span className="material-symbols-outlined text-secondary text-lg">check_circle</span>
          <span>Successfully signed and synced to Odoo PMS (Encounter #1042 committed to database).</span>
        </div>
      )}

      {/* Patient Header Card */}
      <div className="bg-surface-container-lowest rounded-xl p-3.5 shadow-sm border border-surface-container flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg overflow-hidden bg-surface-container flex-shrink-0">
            {patient.photoUrl && <img src={patient.photoUrl} alt="" className="w-full h-full object-cover" />}
          </div>
          <div>
            <h2 className="font-headline font-bold text-primary text-sm">{patient.name}</h2>
            <p className="text-xs text-on-surface-variant">
              {patient.species} • {patient.breed} • {patient.weightKg} kg
            </p>
          </div>
        </div>
        <button
          onClick={() => onNavigate('patients')}
          className="text-xs text-primary font-semibold hover:underline"
        >
          Patient Chart →
        </button>
      </div>

      {/* Subjective Section */}
      <div className="bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-2">
        <div className="flex items-center justify-between border-b border-surface-container pb-1.5">
          <span className="font-headline font-bold text-xs uppercase tracking-wider text-primary">
            S • Subjective (History & Symptoms)
          </span>
          <span className="text-[10px] text-on-surface-variant font-code-vital">From Owner / Voice</span>
        </div>
        <textarea
          value={soapNote.subjective}
          onChange={(e) => setSoapNote({ ...soapNote, subjective: e.target.value })}
          rows={3}
          className="w-full text-xs font-body leading-relaxed bg-surface-container-low/50 rounded-lg p-2.5 border border-surface-container focus:outline-none focus:border-primary"
        />
      </div>

      {/* Objective Section */}
      <div className="bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-2">
        <div className="flex items-center justify-between border-b border-surface-container pb-1.5">
          <span className="font-headline font-bold text-xs uppercase tracking-wider text-primary">
            O • Objective (Exam & Vitals)
          </span>
          <span className="text-[10px] text-on-surface-variant font-code-vital">Physical Findings</span>
        </div>
        <textarea
          value={soapNote.objective}
          onChange={(e) => setSoapNote({ ...soapNote, objective: e.target.value })}
          rows={4}
          className="w-full text-xs font-body leading-relaxed bg-surface-container-low/50 rounded-lg p-2.5 border border-surface-container focus:outline-none focus:border-primary"
        />
      </div>

      {/* Assessment Section */}
      <div className="bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-2">
        <div className="flex items-center justify-between border-b border-surface-container pb-1.5">
          <span className="font-headline font-bold text-xs uppercase tracking-wider text-primary">
            A • Assessment (Diagnosis)
          </span>
          <span className="text-[10px] text-secondary font-semibold font-code-vital">AI Evaluated</span>
        </div>
        <textarea
          value={soapNote.assessment}
          onChange={(e) => setSoapNote({ ...soapNote, assessment: e.target.value })}
          rows={2}
          className="w-full text-xs font-body leading-relaxed bg-surface-container-low/50 rounded-lg p-2.5 border border-surface-container focus:outline-none focus:border-primary"
        />

        {/* ICD-11 Veterinary Chips */}
        <div className="flex flex-wrap gap-1.5 pt-1">
          {soapNote.icd11Codes.map((code, idx) => (
            <span
              key={idx}
              className="px-2 py-0.5 rounded-md bg-surface-container font-code-vital text-[11px] text-on-surface-variant font-medium"
            >
              {code}
            </span>
          ))}
        </div>
      </div>

      {/* Plan Section */}
      <div className="bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-2">
        <div className="flex items-center justify-between border-b border-surface-container pb-1.5">
          <span className="font-headline font-bold text-xs uppercase tracking-wider text-primary">
            P • Plan (Treatment & Orders)
          </span>
          <span className="text-[10px] text-on-surface-variant font-code-vital">Clinical Protocol</span>
        </div>
        <textarea
          value={soapNote.plan}
          onChange={(e) => setSoapNote({ ...soapNote, plan: e.target.value })}
          rows={4}
          className="w-full text-xs font-body leading-relaxed bg-surface-container-low/50 rounded-lg p-2.5 border border-surface-container focus:outline-none focus:border-primary"
        />
      </div>

      {/* Suggested Prescriptions Card */}
      <div className="bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-3">
        <div className="flex items-center justify-between border-b border-surface-container pb-1.5">
          <div className="flex items-center gap-1.5 text-primary text-xs font-bold uppercase tracking-wider">
            <span className="material-symbols-outlined text-[18px]">medication</span>
            <span>Structured Prescriptions</span>
          </div>
          <button
            onClick={() => onNavigate('treatment')}
            className="text-xs text-primary font-semibold hover:underline"
          >
            Manage Rx →
          </button>
        </div>

        {soapNote.suggestedPrescriptions.map((rx, idx) => (
          <div key={idx} className="p-3 rounded-lg bg-surface-container-low/70 border border-surface-container space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-primary text-xs">{rx.medication}</span>
              <span className="px-2 py-0.5 rounded-full bg-secondary-fixed/50 text-on-secondary-fixed-variant text-[10px] font-bold">
                Auto-Dosed
              </span>
            </div>
            <div className="text-xs text-on-surface-variant flex items-center gap-2">
              <span className="font-code-vital text-on-surface">{rx.dosage}</span>
              <span>•</span>
              <span>{rx.frequency}</span>
              <span>•</span>
              <span>{rx.duration}</span>
            </div>
            {rx.cautions && (
              <div className="text-[11px] text-error flex items-center gap-1 pt-0.5">
                <span className="material-symbols-outlined text-[13px]">warning</span>
                <span>{rx.cautions}</span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Human-in-the-Loop Sign Off Trigger */}
      <div className="pt-2">
        <button
          onClick={handleSignAndSync}
          disabled={isSigning || soapNote.state === 'veterinarian_approved'}
          className={`w-full min-h-[52px] rounded-xl shadow-md flex items-center justify-center gap-2.5 active:scale-98 transition-all font-headline font-bold text-sm ${
            soapNote.state === 'veterinarian_approved'
              ? 'bg-secondary text-white'
              : 'bg-primary text-on-primary hover:bg-primary-container'
          }`}
        >
          <span className="material-symbols-outlined text-[20px]">
            {soapNote.state === 'veterinarian_approved' ? 'check_circle' : 'draw'}
          </span>
          <span>
            {isSigning
              ? 'Committing to Odoo...'
              : soapNote.state === 'veterinarian_approved'
              ? 'Signed & Verified by Dr. Sarah Lin'
              : 'Sign & Sync to Odoo PMS'}
          </span>
        </button>
      </div>
    </div>
  );
};
