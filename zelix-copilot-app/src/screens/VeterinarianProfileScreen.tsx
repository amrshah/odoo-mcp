import React from 'react';
import { Clinician, ScreenId } from '../types';

interface VeterinarianProfileScreenProps {
  clinician: Clinician;
  onNavigate: (screen: ScreenId) => void;
}

export const VeterinarianProfileScreen: React.FC<VeterinarianProfileScreenProps> = ({
  clinician,
  onNavigate,
}) => {
  return (
    <div className="flex flex-col w-full max-w-lg mx-auto px-4 pt-20 pb-28 space-y-4">
      {/* Clinician Overview Hero Card */}
      <div className="w-full bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container relative overflow-hidden">
        <div className="flex items-start gap-3.5 relative">
          <div className="relative flex-shrink-0">
            <div className="w-16 h-16 rounded-xl overflow-hidden shadow-sm bg-surface-container border border-surface-container">
              {clinician.avatarUrl && (
                <img src={clinician.avatarUrl} alt={clinician.name} className="w-full h-full object-cover" />
              )}
            </div>
            <span className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-secondary shadow-sm ring-2 ring-surface-container-lowest"></span>
          </div>

          <div className="flex-1 min-w-0">
            <h1 className="font-headline font-bold text-primary text-base truncate">{clinician.name}</h1>
            <p className="text-xs font-semibold text-primary truncate">DACVS (Small Animal Surgery)</p>
            <div className="flex items-center gap-1.5 mt-0.5 text-xs text-on-surface-variant truncate">
              <span className="material-symbols-outlined text-[15px] text-outline">local_hospital</span>
              <span className="truncate">{clinician.clinicName}</span>
            </div>
            <div className="flex items-center gap-1.5 mt-2">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[11px] font-semibold">
                <span className="material-symbols-outlined text-[13px]">sync_saved_locally</span>
                Odoo 19 Synced
              </span>
              <span className="px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant text-[11px] font-medium font-code-vital">
                Lic: {clinician.licenseNumber}
              </span>
            </div>
          </div>
        </div>

        {/* Micro Vitals Ribbon */}
        <div className="grid grid-cols-3 gap-2 mt-3.5 pt-2 border-t border-surface-container text-center text-xs">
          <div className="bg-surface-container-low rounded-lg p-2">
            <span className="text-[10px] text-on-surface-variant font-code-vital">ID</span>
            <p className="font-semibold text-primary font-code-vital">SL-4921</p>
          </div>
          <div className="bg-surface-container-low rounded-lg p-2">
            <span className="text-[10px] text-on-surface-variant font-code-vital">Role</span>
            <p className="font-semibold text-primary">Lead Surgeon</p>
          </div>
          <div className="bg-surface-container-low rounded-lg p-2">
            <span className="text-[10px] text-on-surface-variant font-code-vital">Copilot Tier</span>
            <p className="font-semibold text-secondary">Clinical Edge</p>
          </div>
        </div>
      </div>

      {/* Bento-style Telemetry & Productivity Metrics */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-1.5 font-headline font-bold text-primary">
            <span className="material-symbols-outlined text-[18px]">monitoring</span>
            <span>Practice Telemetry (30-Day Window)</span>
          </div>
          <span className="text-on-surface-variant font-code-vital text-[11px]">PMS Audit Ledger</span>
        </div>

        <div className="grid grid-cols-3 gap-2 text-xs">
          <div className="bg-surface-container-lowest p-3 rounded-xl shadow-sm border border-surface-container flex flex-col justify-between">
            <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center text-primary mb-1">
              <span className="material-symbols-outlined text-[16px]">clinical_notes</span>
            </div>
            <div>
              <div className="font-headline font-bold text-lg text-primary">342</div>
              <p className="text-[10px] text-on-surface-variant mt-0.5 leading-tight">SOAP Notes Charted</p>
            </div>
          </div>

          <div className="bg-surface-container-lowest p-3 rounded-xl shadow-sm border border-surface-container flex flex-col justify-between">
            <div className="w-7 h-7 rounded-lg bg-secondary-fixed text-on-secondary-fixed flex items-center justify-center mb-1">
              <span className="material-symbols-outlined text-[16px]">schedule</span>
            </div>
            <div>
              <div className="font-headline font-bold text-lg text-secondary">1h 48m</div>
              <p className="text-[10px] text-on-surface-variant mt-0.5 leading-tight">Saved / Shift</p>
            </div>
          </div>

          <div className="bg-surface-container-lowest p-3 rounded-xl shadow-sm border border-surface-container flex flex-col justify-between">
            <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center text-primary mb-1">
              <span className="material-symbols-outlined text-[16px]">cloud_done</span>
            </div>
            <div>
              <div className="font-headline font-bold text-lg text-primary">99.4%</div>
              <p className="text-[10px] text-on-surface-variant mt-0.5 leading-tight">Auto-Push to Odoo</p>
            </div>
          </div>
        </div>
      </div>

      {/* Board Certifications & Security Keys */}
      <div className="bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-3 text-xs">
        <h2 className="font-headline font-bold text-xs uppercase tracking-wider text-primary border-b border-surface-container pb-1.5">
          Board Credentials & Cryptographic Keys
        </h2>

        <div className="space-y-2">
          <div className="p-2.5 rounded-lg bg-surface-container-low flex justify-between items-center">
            <div>
              <p className="font-semibold text-primary">American College of Veterinary Surgeons</p>
              <p className="text-[10px] text-on-surface-variant">Board Certified Diplomate (DACVS)</p>
            </div>
            <span className="material-symbols-outlined text-secondary text-lg">verified</span>
          </div>

          <div className="p-2.5 rounded-lg bg-surface-container-low flex justify-between items-center">
            <div>
              <p className="font-semibold text-primary">DEA Schedule II-V Prescribing Key</p>
              <p className="text-[10px] text-on-surface-variant font-code-vital">DEA-NY-8492019 • Verified Active</p>
            </div>
            <span className="material-symbols-outlined text-secondary text-lg">lock</span>
          </div>
        </div>
      </div>

      {/* Switch Practice Button */}
      <button
        onClick={() => onNavigate('auth')}
        className="w-full min-h-[48px] rounded-xl bg-surface-container-lowest border border-primary text-primary hover:bg-surface-container font-headline font-bold text-xs flex items-center justify-center gap-2 shadow-sm transition"
      >
        <span className="material-symbols-outlined text-[18px]">swap_horiz</span>
        <span>Switch Practice Location (Odoo Multi-Company)</span>
      </button>
    </div>
  );
};
