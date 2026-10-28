import React, { useState } from 'react';
import { Patient, ScreenId } from '../types';

interface PetOwnerMessagingScreenProps {
  patient: Patient;
  onNavigate: (screen: ScreenId) => void;
}

export const PetOwnerMessagingScreen: React.FC<PetOwnerMessagingScreenProps> = ({ patient, onNavigate }) => {
  const [selectedTemplate, setSelectedTemplate] = useState('instructions');
  const [selectedTone, setSelectedTone] = useState('friendly');
  const [activeTab, setActiveTab] = useState<'client' | 'clinical'>('client');
  const [isSent, setIsSent] = useState(false);

  const messageTemplates = [
    { id: 'instructions', label: 'Post-Visit Instructions', icon: 'assignment_turned_in' },
    { id: 'medication', label: 'Medication Guidance', icon: 'medication' },
    { id: 'followup', label: 'Follow-Up Check', icon: 'contact_support' },
    { id: 'appointment', label: 'Appointment Reminder', icon: 'event' },
    { id: 'lab', label: 'Lab Results', icon: 'science' },
  ];

  const tones = [
    { id: 'friendly', label: 'Friendly & Clear', icon: 'sentiment_satisfied' },
    { id: 'clinical', label: 'Professional Clinical', icon: 'stethoscope' },
    { id: 'empathetic', label: 'Reassuring / Empathetic', icon: 'favorite' },
    { id: 'bulleted', label: 'Concise Bulleted', icon: 'format_list_bulleted' },
  ];

  const clientText = `Hi Eleanor! 🐾 Dr. Sarah Lin here from VetCairn Downtown.

Thank you for bringing Barnaby in today! His ear cytology confirmed a mixed yeast/bacterial otitis externa in his left ear.

Here is your care plan:
1. Epi-Otic Ear Cleanser: Flush the left ear once daily in the morning, massage gently for 30s, and wipe away excess.
2. Surolan Otic Drops: Apply 5-7 drops into the left ear twice daily (12 hours apart), 30 minutes after cleaning.
3. Keep ears strictly dry: Please pause swimming for the next 10 days!

We've scheduled Barnaby's recheck for Oct 28th at 10:30 AM. Reply to this text if you have any questions!`;

  const clinicalReference = `SOAP Assessment: Acute bilateral otitis externa (AS moderate mixed fungal/bacterial).
Rx Prescribed: Surolan Otic Suspension 0.5 mL AS q12h x 10d; Epi-Otic Advanced flush q24h.
Instructions: Complete 10-day regimen even if symptoms resolve earlier. Strict water cessation. Recheck cytology in 14 days.`;

  return (
    <div className="flex flex-col w-full max-w-lg mx-auto px-4 pt-20 pb-28 space-y-4">
      {/* Patient Strip */}
      <div className="w-full bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container relative overflow-hidden">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="relative w-12 h-12 rounded-full overflow-hidden bg-surface-container border border-surface-container flex-shrink-0">
              {patient.photoUrl && <img src={patient.photoUrl} alt="" className="w-full h-full object-cover" />}
              <span className="absolute bottom-0 right-0 w-3 h-3 rounded-full bg-secondary ring-2 ring-surface-container-lowest"></span>
            </div>
            <div className="flex flex-col min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-headline font-bold text-primary text-base truncate">{patient.name}</span>
                <span className="font-code-vital text-xs px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-medium">
                  {patient.weightKg} kg
                </span>
              </div>
              <span className="text-xs text-on-surface-variant truncate">
                {patient.species} • {patient.breed} ({patient.age})
              </span>
              <div className="flex items-center gap-1.5 mt-0.5 text-xs text-on-surface-variant">
                <span className="material-symbols-outlined text-[14px] text-secondary">person</span>
                <span className="font-medium truncate">{patient.primaryOwnerName}</span>
                <span className="w-1 h-1 rounded-full bg-outline-variant"></span>
                <span className="text-secondary font-semibold">SMS & Portal Active</span>
              </div>
            </div>
          </div>
          <span className="px-2.5 py-1 rounded-full bg-secondary-fixed/40 text-on-secondary-fixed-variant text-xs font-semibold flex items-center gap-1 flex-shrink-0">
            <span className="material-symbols-outlined text-[14px]">verified</span>
            Verified Rx
          </span>
        </div>
      </div>

      {/* AI Context Banner */}
      <div className="rounded-xl bg-surface-container-low p-3.5 shadow-sm border border-surface-container flex items-start gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-tertiary-fixed text-on-tertiary-fixed flex items-center justify-center flex-shrink-0 mt-0.5">
          <span className="material-symbols-outlined text-[16px]">auto_awesome</span>
        </div>
        <div className="flex-1 min-w-0 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-on-tertiary-fixed">AI Copilot Clinical Synthesis</span>
            <span className="font-code-vital text-on-surface-variant text-[10px]">Grade 5.8 Lexile</span>
          </div>
          <p className="text-on-surface mt-0.5">
            Auto-synthesized from today's <span className="font-semibold text-primary">Otitis Externa SOAP Note</span> &{' '}
            <span className="font-semibold text-primary">Treatment Plan</span>.
          </p>
        </div>
      </div>

      {/* Template Chips */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="font-bold text-on-surface-variant uppercase tracking-wider text-[11px]">Message Template</span>
          <span className="text-secondary font-medium">5 Available</span>
        </div>
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
          {messageTemplates.map((t) => (
            <button
              key={t.id}
              onClick={() => setSelectedTemplate(t.id)}
              className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-semibold flex items-center gap-1.5 transition-all ${
                selectedTemplate === t.id
                  ? 'bg-primary text-on-primary shadow-sm'
                  : 'bg-surface-container text-on-surface hover:bg-surface-container-high'
              }`}
            >
              <span className="material-symbols-outlined text-[15px]">{t.icon}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Tone Chips */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="font-bold text-on-surface-variant uppercase tracking-wider text-[11px]">AI Empathy & Tone</span>
          <span className="font-code-vital text-on-surface-variant text-[10px]">Client Friendly</span>
        </div>
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
          {tones.map((tone) => (
            <button
              key={tone.id}
              onClick={() => setSelectedTone(tone.id)}
              className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1 transition-all ${
                selectedTone === tone.id
                  ? 'bg-secondary-fixed text-on-secondary-fixed shadow-sm'
                  : 'bg-surface-container text-on-surface hover:bg-surface-container-high'
              }`}
            >
              <span className="material-symbols-outlined text-[15px]">{tone.icon}</span>
              <span>{tone.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Message Comparison View */}
      <div className="bg-surface-container-lowest rounded-xl shadow-sm border border-surface-container overflow-hidden">
        <div className="flex items-center bg-surface-container p-1 rounded-t-xl text-xs font-semibold">
          <button
            onClick={() => setActiveTab('client')}
            className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-1.5 transition-all ${
              activeTab === 'client' ? 'bg-surface-container-lowest text-primary shadow-sm' : 'text-on-surface-variant'
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">sms</span>
            <span>Client SMS / Portal Preview</span>
          </button>
          <button
            onClick={() => setActiveTab('clinical')}
            className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-1.5 transition-all ${
              activeTab === 'clinical' ? 'bg-surface-container-lowest text-primary shadow-sm' : 'text-on-surface-variant'
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">medical_services</span>
            <span>Clinical Source View</span>
          </button>
        </div>

        <div className="p-4 text-xs font-body leading-relaxed">
          {activeTab === 'client' ? (
            <div className="bg-surface-container-low/60 rounded-xl p-3.5 border border-surface-container whitespace-pre-wrap font-sans text-on-surface">
              {clientText}
            </div>
          ) : (
            <div className="bg-surface-container-low/60 rounded-xl p-3.5 border border-surface-container whitespace-pre-wrap font-code-vital text-[11px] text-on-surface">
              {clinicalReference}
            </div>
          )}
        </div>
      </div>

      {/* Send CTA */}
      <div className="pt-2">
        <button
          onClick={() => setIsSent(true)}
          disabled={isSent}
          className={`w-full min-h-[52px] rounded-xl shadow-md flex items-center justify-center gap-2.5 active:scale-98 transition-all font-headline font-bold text-sm ${
            isSent ? 'bg-secondary text-white' : 'bg-primary text-on-primary hover:bg-primary-container'
          }`}
        >
          <span className="material-symbols-outlined text-[20px]">{isSent ? 'done_all' : 'send'}</span>
          <span>{isSent ? 'Sent to Eleanor Vance via SMS & Pet Portal' : 'Send via SMS & Pet Portal (Twilio/Odoo)'}</span>
        </button>
      </div>
    </div>
  );
};
