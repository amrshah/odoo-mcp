import React from 'react';
import { Clinician, ScreenId } from '../types';

interface HeaderProps {
  clinician: Clinician;
  currentScreen: ScreenId;
  onNavigate: (screen: ScreenId) => void;
}

export const Header: React.FC<HeaderProps> = ({ clinician, currentScreen, onNavigate }) => {
  const getScreenTitle = () => {
    switch (currentScreen) {
      case 'flow':
        return 'Consultation Flow';
      case 'voice':
        return 'Voice Consult';
      case 'soap':
        return 'SOAP Note';
      case 'workspace':
        return 'AI Workspace';
      case 'patients':
        return 'Patient Chart';
      case 'treatment':
        return 'Treatment Plan';
      case 'history':
        return 'Consultation History';
      case 'messaging':
        return 'Client Messaging';
      case 'notifications':
        return 'Clinical Alerts';
      case 'profile':
        return 'Veterinarian Profile';
      case 'auth':
        return 'Practices & Auth';
      default:
        return 'Copilot';
    }
  };

  return (
    <header className="fixed top-0 w-full z-50 pt-safe bg-surface/90 backdrop-blur-xl border-b border-surface-container shadow-[0_1px_8px_rgba(0,0,0,0.03)]">
      <div className="h-16 px-4 flex items-center justify-between gap-3 max-w-lg mx-auto">
        {/* Brand & Active Subtitle */}
        <button
          onClick={() => onNavigate('flow')}
          className="flex items-center gap-3 min-w-0 text-left hover:opacity-90 transition-opacity"
        >
          <div className="w-9 h-9 rounded-xl bg-primary-container flex items-center justify-center text-white font-display font-bold text-lg shadow-sm flex-shrink-0">
            Z
          </div>
          <div className="flex flex-col min-w-0">
            <span className="font-headline font-semibold text-primary text-base tracking-tight truncate">
              ZelixVet Copilot
            </span>
            <span className="font-label text-xs text-on-surface-variant truncate">
              {getScreenTitle()}
            </span>
          </div>
        </button>

        {/* PMS Status, Notifications, & Clinician Profile */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-secondary-fixed/40 text-on-secondary-fixed-variant text-xs font-semibold">
            <span className="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
            <span>Odoo Live</span>
          </div>

          <button
            onClick={() => onNavigate('notifications')}
            aria-label="Clinical Alerts"
            className="w-9 h-9 rounded-lg hover:bg-surface-container flex items-center justify-center text-on-surface-variant relative transition"
          >
            <span className="material-symbols-outlined text-[22px]">notifications</span>
            <span className="w-2 h-2 rounded-full bg-error absolute top-2 right-2 ring-2 ring-surface"></span>
          </button>

          <button
            onClick={() => onNavigate('profile')}
            aria-label="Dr. Sarah Lin Profile"
            className="w-9 h-9 rounded-full overflow-hidden border-2 border-primary-container/20 hover:border-primary transition-all flex items-center justify-center bg-surface-container"
          >
            {clinician.avatarUrl ? (
              <img src={clinician.avatarUrl} alt={clinician.name} className="w-full h-full object-cover" />
            ) : (
              <span className="material-symbols-outlined text-primary text-xl">person</span>
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
