import React from 'react';
import { Clinician, ClinicPractice, ScreenId } from '../types';

interface AuthAndPracticeSwitcherScreenProps {
  clinician: Clinician;
  onUpdateClinician: (updated: Clinician) => void;
  onNavigate: (screen: ScreenId) => void;
}

export const AuthAndPracticeSwitcherScreen: React.FC<AuthAndPracticeSwitcherScreenProps> = ({
  clinician,
  onUpdateClinician,
  onNavigate,
}) => {
  const practices: ClinicPractice[] = [
    {
      id: 3,
      name: 'VetCairn Downtown Animal Hospital',
      code: 'VC-DT-01',
      location: '124 Mercer St, New York, NY',
    },
    {
      id: 5,
      name: 'VetCairn Westside Specialty Clinic',
      code: 'VC-WS-02',
      location: '540 W 57th St, New York, NY',
    },
    {
      id: 8,
      name: 'VetCairn Emergency & Referral Centre',
      code: 'VC-EM-03',
      location: '88 10th Ave, New York, NY',
    },
  ];

  return (
    <div className="flex flex-col w-full max-w-lg mx-auto px-4 pt-20 pb-28 space-y-4">
      {/* Clinician Card */}
      <div className="w-full bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container flex items-center gap-3.5">
        <div className="w-14 h-14 rounded-full overflow-hidden bg-surface-container border-2 border-primary/20 flex-shrink-0">
          {clinician.avatarUrl && <img src={clinician.avatarUrl} alt="" className="w-full h-full object-cover" />}
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="font-headline font-bold text-primary text-base tracking-tight truncate">
            {clinician.name}
          </h1>
          <p className="text-xs text-on-surface-variant font-medium">License: {clinician.licenseNumber}</p>
          <span className="inline-block mt-1 px-2 py-0.5 rounded-full bg-secondary-fixed/50 text-on-secondary-fixed-variant text-[11px] font-bold uppercase tracking-wider">
            Role: {clinician.role}
          </span>
        </div>
      </div>

      {/* Practice Switcher */}
      <div className="w-full bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-3">
        <div className="flex items-center justify-between border-b border-surface-container pb-2">
          <h2 className="font-headline font-bold text-xs uppercase tracking-wider text-primary">
            Select Active Practice Location
          </h2>
          <span className="text-[11px] text-secondary font-semibold">Odoo Multi-Company</span>
        </div>

        <div className="space-y-2">
          {practices.map((practice) => {
            const isSelected = clinician.clinicId === practice.id;
            return (
              <button
                key={practice.id}
                onClick={() =>
                  onUpdateClinician({
                    ...clinician,
                    clinicId: practice.id,
                    clinicName: practice.name,
                  })
                }
                className={`w-full p-3 rounded-xl border text-left flex items-center justify-between transition-all ${
                  isSelected
                    ? 'border-primary bg-primary-container/5 shadow-sm'
                    : 'border-surface-container hover:bg-surface-container-low'
                }`}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-headline font-bold text-primary text-xs sm:text-sm truncate">
                      {practice.name}
                    </span>
                    <span className="font-code-vital text-[10px] px-1.5 py-0.5 rounded bg-surface-container text-on-surface-variant">
                      {practice.code}
                    </span>
                  </div>
                  <p className="text-[11px] text-on-surface-variant truncate mt-0.5">{practice.location}</p>
                </div>
                {isSelected ? (
                  <span className="material-symbols-outlined text-primary text-xl flex-shrink-0">
                    check_circle
                  </span>
                ) : (
                  <span className="material-symbols-outlined text-outline-variant text-xl flex-shrink-0">
                    radio_button_unchecked
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Backend Connection Diagnostics */}
      <div className="w-full bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-2.5 text-xs">
        <h2 className="font-headline font-bold text-xs uppercase tracking-wider text-primary border-b border-surface-container pb-1.5">
          Backend Topology & Edge Gateways
        </h2>
        <div className="flex justify-between items-center py-1">
          <span className="text-on-surface-variant">Odoo 19 Core</span>
          <span className="font-code-vital text-secondary font-semibold">Connected (:8069)</span>
        </div>
        <div className="flex justify-between items-center py-1">
          <span className="text-on-surface-variant">FastMCP Protocol Bridge</span>
          <span className="font-code-vital text-secondary font-semibold">Active SSE (:8008)</span>
        </div>
        <div className="flex justify-between items-center py-1">
          <span className="text-on-surface-variant">Alamia Edge AI Gateway</span>
          <span className="font-code-vital text-secondary font-semibold">Cloudflare Workers AI (Free Tier)</span>
        </div>
        <div className="flex justify-between items-center py-1">
          <span className="text-on-surface-variant">Active Model</span>
          <span className="font-code-vital text-primary font-semibold">@cf/meta/llama-3.1-8b-instruct</span>
        </div>
      </div>

      {/* Return to Voice CTA */}
      <button
        onClick={() => onNavigate('voice')}
        className="w-full min-h-[48px] rounded-xl bg-primary text-on-primary font-headline font-bold text-sm shadow-md flex items-center justify-center gap-2"
      >
        <span>Return to Active Consultation</span>
        <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
      </button>
    </div>
  );
};
