import React from 'react';
import { Patient, ScreenId } from '../types';

interface TreatmentPlanScreenProps {
  patient: Patient;
  onNavigate: (screen: ScreenId) => void;
}

export const TreatmentPlanScreen: React.FC<TreatmentPlanScreenProps> = ({ patient, onNavigate }) => {
  return (
    <div className="flex flex-col w-full max-w-lg mx-auto px-4 pt-20 pb-28 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-headline font-bold text-primary text-lg">Active Treatment Plan</h1>
          <p className="text-xs text-on-surface-variant">Otitis Externa Care Protocol • {patient.name}</p>
        </div>
        <span className="px-2.5 py-1 rounded-full bg-secondary-fixed/50 text-on-secondary-fixed-variant text-xs font-bold">
          Active (Day 1 of 10)
        </span>
      </div>

      {/* Medication 1: Surolan */}
      <div className="bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-secondary/10 text-secondary flex items-center justify-center flex-shrink-0">
              <span className="material-symbols-outlined text-xl">medication</span>
            </div>
            <div>
              <h2 className="font-headline font-bold text-primary text-xs sm:text-sm">
                Surolan Otic Suspension
              </h2>
              <p className="text-[11px] text-on-surface-variant font-code-vital">
                Miconazole + Polymyxin B + Prednisolone
              </p>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant text-[10px] font-bold">
            q12h
          </span>
        </div>

        <div className="p-3 bg-surface-container-low/70 rounded-lg text-xs space-y-1">
          <div className="flex justify-between">
            <span className="text-on-surface-variant">Dosage</span>
            <span className="font-code-vital font-semibold text-primary">0.5 mL (5-7 drops)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-on-surface-variant">Target</span>
            <span className="font-semibold text-primary">Left Ear (AS) Only</span>
          </div>
          <div className="flex justify-between">
            <span className="text-on-surface-variant">Duration</span>
            <span className="font-semibold text-primary">10 Days</span>
          </div>
        </div>

        <div className="p-2.5 bg-tertiary-fixed/30 border border-tertiary/20 rounded-lg text-xs text-on-tertiary-fixed-variant flex items-center gap-2">
          <span className="material-symbols-outlined text-[16px]">info</span>
          <span>Instill drops after cleaning with Epi-Otic. Massage base of ear gently for 30 seconds.</span>
        </div>
      </div>

      {/* Medication 2: Epi-Otic */}
      <div className="bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-primary/10 text-primary flex items-center justify-center flex-shrink-0">
              <span className="material-symbols-outlined text-xl">sanitizer</span>
            </div>
            <div>
              <h2 className="font-headline font-bold text-primary text-xs sm:text-sm">
                Epi-Otic Advanced Ear Cleanser
              </h2>
              <p className="text-[11px] text-on-surface-variant font-code-vital">
                Salicylic acid 0.2% + PCMX
              </p>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-surface-container text-on-surface text-[10px] font-bold">
            q24h
          </span>
        </div>

        <div className="p-3 bg-surface-container-low/70 rounded-lg text-xs space-y-1">
          <div className="flex justify-between">
            <span className="text-on-surface-variant">Dosage</span>
            <span className="font-semibold text-primary">Liberal ear canal flush</span>
          </div>
          <div className="flex justify-between">
            <span className="text-on-surface-variant">Timing</span>
            <span className="font-semibold text-primary">Morning, 30 min before drops</span>
          </div>
        </div>
      </div>

      {/* Schedule & Follow-up */}
      <div className="bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-2.5 text-xs">
        <h2 className="font-headline font-bold text-xs uppercase tracking-wider text-primary border-b border-surface-container pb-1.5">
          Follow-up & Milestone Checks
        </h2>
        <div className="flex items-center justify-between py-1">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-secondary text-[18px]">event_repeat</span>
            <div>
              <p className="font-semibold text-on-surface">Recheck Otoscopy & Cytology</p>
              <p className="text-[10px] text-on-surface-variant">14 Days Post-Treatment Start</p>
            </div>
          </div>
          <span className="px-2.5 py-1 rounded-md bg-secondary text-white text-[11px] font-semibold">
            Scheduled
          </span>
        </div>
      </div>

      {/* Discharge Summary Generator CTA */}
      <button
        onClick={() => onNavigate('soap')}
        className="w-full min-h-[48px] rounded-xl bg-surface-container-lowest border border-primary text-primary hover:bg-surface-container text-xs font-headline font-bold flex items-center justify-center gap-2 shadow-sm transition"
      >
        <span className="material-symbols-outlined text-[18px]">share</span>
        <span>Export Owner Care Instructions to Portal</span>
      </button>
    </div>
  );
};
