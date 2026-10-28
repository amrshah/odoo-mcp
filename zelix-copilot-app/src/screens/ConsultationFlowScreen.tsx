import React from 'react';
import { Patient, ScreenId } from '../types';

interface ConsultationFlowScreenProps {
  patient: Patient;
  onNavigate: (screen: ScreenId) => void;
}

export const ConsultationFlowScreen: React.FC<ConsultationFlowScreenProps> = ({ patient, onNavigate }) => {
  return (
    <div className="flex flex-col w-full max-w-lg mx-auto px-4 pt-20 pb-28 space-y-4">
      {/* Active Patient Context Card */}
      <div className="w-full bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container flex flex-col gap-2.5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-12 h-12 rounded-full overflow-hidden bg-surface-container flex-shrink-0">
              {patient.photoUrl && <img src={patient.photoUrl} alt="" className="w-full h-full object-cover" />}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <h2 className="font-headline font-bold text-primary text-base truncate">{patient.name}</h2>
                <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-error-container text-on-error-container text-[11px] font-bold">
                  <span className="material-symbols-outlined text-[13px] mr-1">warning</span>
                  Penicillin Allergy
                </span>
              </div>
              <p className="text-xs text-on-surface-variant truncate">
                {patient.species} • {patient.breed} • <span className="font-code-vital text-on-surface font-semibold">{patient.weightKg} kg</span>
              </p>
            </div>
          </div>

          <button
            onClick={() => onNavigate('patients')}
            className="text-xs text-primary font-semibold flex items-center gap-1 hover:underline flex-shrink-0"
          >
            <span className="material-symbols-outlined text-[16px]">swap_horiz</span>
            <span>Switch</span>
          </button>
        </div>

        <div className="flex items-center justify-between pt-1.5 bg-surface-container-low px-3 py-1.5 rounded-lg text-xs text-on-surface-variant">
          <div className="flex items-center gap-1.5 truncate">
            <span className="material-symbols-outlined text-[15px]">person</span>
            <span className="truncate">Client: <strong className="text-on-surface font-semibold">{patient.primaryOwnerName}</strong></span>
          </div>
          <span className="font-code-vital text-[11px] px-1.5 py-0.5 rounded bg-surface-container text-on-surface font-semibold">
            {patient.identifier}
          </span>
        </div>
      </div>

      {/* Greeting Header */}
      <div>
        <div className="flex items-center gap-1.5 text-secondary text-xs font-bold uppercase tracking-wider">
          <span className="material-symbols-outlined text-[16px]">auto_awesome</span>
          <span>Ambient Clinical Intelligence</span>
        </div>
        <h1 className="font-headline font-bold text-xl text-primary tracking-tight mt-0.5">
          How can I help with your next consultation?
        </h1>
      </div>

      {/* Primary Quick Actions 2x3 Grid */}
      <div className="grid grid-cols-2 gap-3 w-full">
        {/* Action 1: Start Voice Consult */}
        <button
          onClick={() => onNavigate('voice')}
          className="p-4 rounded-xl bg-primary text-on-primary shadow-sm flex flex-col justify-between items-start gap-3 transition-all active:scale-98 text-left"
        >
          <div className="w-10 h-10 rounded-lg bg-surface-container-lowest/15 flex items-center justify-center">
            <span className="material-symbols-outlined text-[24px] text-secondary-fixed">mic</span>
          </div>
          <div>
            <span className="font-headline font-bold text-sm block tracking-tight">Start Voice Consult</span>
            <span className="text-xs text-on-primary-container block mt-0.5">Real-time transcribing</span>
          </div>
        </button>

        {/* Action 2: Draft SOAP Note */}
        <button
          onClick={() => onNavigate('soap')}
          className="p-4 rounded-xl bg-surface-container-lowest text-on-surface shadow-sm border border-surface-container flex flex-col justify-between items-start gap-3 transition-all active:scale-98 text-left hover:border-primary"
        >
          <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center text-primary">
            <span className="material-symbols-outlined text-[22px]">clinical_notes</span>
          </div>
          <div>
            <span className="font-headline font-bold text-sm block text-primary">Draft a SOAP Note</span>
            <span className="text-xs text-on-surface-variant block mt-0.5">Synthesis from context</span>
          </div>
        </button>

        {/* Action 3: Prepare Treatment Plan */}
        <button
          onClick={() => onNavigate('treatment')}
          className="p-4 rounded-xl bg-surface-container-lowest text-on-surface shadow-sm border border-surface-container flex flex-col justify-between items-start gap-3 transition-all active:scale-98 text-left hover:border-primary"
        >
          <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center text-secondary">
            <span className="material-symbols-outlined text-[22px]">prescriptions</span>
          </div>
          <div>
            <span className="font-headline font-bold text-sm block text-primary">Treatment Plan</span>
            <span className="text-xs text-on-surface-variant block mt-0.5">Protocols & dosing</span>
          </div>
        </button>

        {/* Action 4: Pet Owner Message */}
        <button
          onClick={() => onNavigate('messaging')}
          className="p-4 rounded-xl bg-surface-container-lowest text-on-surface shadow-sm border border-surface-container flex flex-col justify-between items-start gap-3 transition-all active:scale-98 text-left hover:border-primary"
        >
          <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center text-tertiary-container">
            <span className="material-symbols-outlined text-[22px]">forum</span>
          </div>
          <div>
            <span className="font-headline font-bold text-sm block text-primary">Owner Message</span>
            <span className="text-xs text-on-surface-variant block mt-0.5">Discharge & care tips</span>
          </div>
        </button>

        {/* Action 5: Summarize History */}
        <button
          onClick={() => onNavigate('history')}
          className="p-4 rounded-xl bg-surface-container-lowest text-on-surface shadow-sm border border-surface-container flex flex-col justify-between items-start gap-3 transition-all active:scale-98 text-left hover:border-primary"
        >
          <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center text-primary">
            <span className="material-symbols-outlined text-[22px]">history</span>
          </div>
          <div>
            <span className="font-headline font-bold text-sm block text-primary">Consult History</span>
            <span className="text-xs text-on-surface-variant block mt-0.5">Past records & audits</span>
          </div>
        </button>

        {/* Action 6: Clinical Alerts Hub */}
        <button
          onClick={() => onNavigate('notifications')}
          className="p-4 rounded-xl bg-surface-container-lowest text-on-surface shadow-sm border border-surface-container flex flex-col justify-between items-start gap-3 transition-all active:scale-98 text-left hover:border-primary"
        >
          <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center text-error">
            <span className="material-symbols-outlined text-[22px]">notifications_active</span>
          </div>
          <div>
            <span className="font-headline font-bold text-sm block text-primary">Alerts Hub</span>
            <span className="text-xs text-on-surface-variant block mt-0.5">STAT lab & recalls</span>
          </div>
        </button>
      </div>
    </div>
  );
};
