import React from 'react';
import { ScreenId } from '../types';

interface BottomNavProps {
  currentScreen: ScreenId;
  onNavigate: (screen: ScreenId) => void;
}

export const BottomNav: React.FC<BottomNavProps> = ({ currentScreen, onNavigate }) => {
  const navItems: { id: ScreenId; label: string; icon: string }[] = [
    { id: 'flow', label: 'Hub', icon: 'dashboard' },
    { id: 'voice', label: 'Voice', icon: 'mic' },
    { id: 'soap', label: 'SOAP', icon: 'assignment' },
    { id: 'treatment', label: 'Treatment', icon: 'medication' },
    { id: 'patients', label: 'Patient', icon: 'pets' },
  ];

  return (
    <nav className="fixed bottom-0 w-full z-50 pb-safe bg-surface-container-lowest/90 backdrop-blur-xl border-t border-surface-container shadow-[0_-4px_16px_rgba(14,77,69,0.06)]">
      <div className="flex justify-between items-center h-16 px-2 max-w-lg mx-auto">
        {navItems.map((item) => {
          const isActive = currentScreen === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`flex flex-col items-center justify-center flex-1 h-full min-w-[48px] transition-all ${
                isActive
                  ? 'text-primary font-semibold scale-105'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <span className={`material-symbols-outlined text-[24px] ${isActive ? 'text-primary font-bold' : ''}`}>
                {item.icon}
              </span>
              <span className="font-label text-[11px] mt-0.5 tracking-tight">{item.label}</span>
              {isActive && (
                <span className="w-1.5 h-1.5 rounded-full bg-primary mt-0.5"></span>
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
};
