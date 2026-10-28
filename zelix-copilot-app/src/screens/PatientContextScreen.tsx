import React from 'react';
import { Patient, ScreenId } from '../types';

interface PatientContextScreenProps {
  patient: Patient;
  onNavigate: (screen: ScreenId) => void;
}

export const PatientContextScreen: React.FC<PatientContextScreenProps> = ({ patient, onNavigate }) => {
  return (
    <div className="flex flex-col w-full max-w-lg mx-auto px-4 pt-20 pb-28 space-y-4">
      {/* Patient Hero Card */}
      <div className="w-full bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container flex flex-col items-center text-center space-y-3">
        <div className="w-20 h-20 rounded-2xl overflow-hidden bg-surface-container border-2 border-primary-container/20 shadow-sm">
          {patient.photoUrl ? (
            <img src={patient.photoUrl} alt={patient.name} className="w-full h-full object-cover" />
          ) : (
            <span className="material-symbols-outlined text-primary text-4xl flex items-center justify-center h-full">
              pets
            </span>
          )}
        </div>
        <div>
          <h1 className="font-headline font-bold text-primary text-xl tracking-tight">{patient.name}</h1>
          <p className="text-xs text-on-surface-variant font-medium">
            {patient.species} • {patient.breed} • {patient.age}
          </p>
          <span className="inline-block mt-1 font-code-vital text-xs px-2.5 py-0.5 rounded-full bg-surface-container text-on-surface">
            ID: {patient.identifier} • Microchip: {patient.microchipNumber}
          </span>
        </div>

        {/* Quick Action Bar */}
        <div className="grid grid-cols-3 gap-2 w-full pt-1">
          <button
            onClick={() => onNavigate('voice')}
            className="p-2.5 rounded-lg bg-primary text-on-primary text-xs font-semibold flex flex-col items-center gap-1 shadow-sm"
          >
            <span className="material-symbols-outlined text-[18px]">mic</span>
            <span>Start Consult</span>
          </button>
          <button
            onClick={() => onNavigate('soap')}
            className="p-2.5 rounded-lg bg-surface-container text-primary text-xs font-semibold flex flex-col items-center gap-1 border border-surface-container"
          >
            <span className="material-symbols-outlined text-[18px]">assignment</span>
            <span>View SOAP</span>
          </button>
          <button
            onClick={() => onNavigate('treatment')}
            className="p-2.5 rounded-lg bg-surface-container text-primary text-xs font-semibold flex flex-col items-center gap-1 border border-surface-container"
          >
            <span className="material-symbols-outlined text-[18px]">medication</span>
            <span>Treatment</span>
          </button>
        </div>
      </div>

      {/* Allergies & Alerts Warning Card */}
      <div className="bg-error-container/40 border border-error/20 rounded-xl p-4 shadow-sm space-y-2">
        <div className="flex items-center gap-2 text-error font-headline font-bold text-xs uppercase tracking-wider">
          <span className="material-symbols-outlined text-[18px]">warning</span>
          <span>Critical Clinical Alerts</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {patient.allergies.map((allergy, i) => (
            <span
              key={i}
              className="px-2.5 py-1 rounded-md bg-error-container text-on-error-container text-xs font-semibold flex items-center gap-1"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-error"></span>
              Allergy: {allergy}
            </span>
          ))}
        </div>
      </div>

      {/* Vitals Telemetry History */}
      <div className="bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-3">
        <div className="flex items-center justify-between border-b border-surface-container pb-2">
          <h2 className="font-headline font-bold text-xs uppercase tracking-wider text-primary">
            Recent Telemetry & Vitals
          </h2>
          <span className="font-code-vital text-xs text-secondary font-semibold">Today 10:15 AM</span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="p-2.5 rounded-lg bg-surface-container-low/70">
            <span className="text-on-surface-variant text-[11px]">Weight</span>
            <p className="font-code-vital font-bold text-base text-primary">{patient.weightKg} kg</p>
            <span className="text-[10px] text-secondary">Stable (+0.2 kg / 3 mos)</span>
          </div>

          <div className="p-2.5 rounded-lg bg-surface-container-low/70">
            <span className="text-on-surface-variant text-[11px]">Body Temperature</span>
            <p className="font-code-vital font-bold text-base text-primary">38.6 °C</p>
            <span className="text-[10px] text-on-surface-variant">Normothermic</span>
          </div>

          <div className="p-2.5 rounded-lg bg-surface-container-low/70">
            <span className="text-on-surface-variant text-[11px]">Heart Rate</span>
            <p className="font-code-vital font-bold text-base text-primary">96 bpm</p>
            <span className="text-[10px] text-on-surface-variant">Sinus rhythm</span>
          </div>

          <div className="p-2.5 rounded-lg bg-surface-container-low/70">
            <span className="text-on-surface-variant text-[11px]">Respiratory Rate</span>
            <p className="font-code-vital font-bold text-base text-primary">24 bpm</p>
            <span className="text-[10px] text-on-surface-variant">Eupneic</span>
          </div>
        </div>
      </div>

      {/* Owner & Emergency Contact */}
      <div className="bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-2 text-xs">
        <h2 className="font-headline font-bold text-xs uppercase tracking-wider text-primary border-b border-surface-container pb-1.5">
          Owner & Emergency Contact
        </h2>
        <div className="flex justify-between items-center py-1">
          <span className="text-on-surface-variant">Primary Owner</span>
          <span className="font-semibold text-on-surface">{patient.primaryOwnerName}</span>
        </div>
        <div className="flex justify-between items-center py-1">
          <span className="text-on-surface-variant">Phone</span>
          <a href={`tel:${patient.primaryOwnerPhone}`} className="font-code-vital text-primary font-semibold hover:underline">
            {patient.primaryOwnerPhone}
          </a>
        </div>
        <div className="flex justify-between items-center py-1">
          <span className="text-on-surface-variant">Email</span>
          <span className="text-on-surface">{patient.primaryOwnerEmail}</span>
        </div>
      </div>
    </div>
  );
};
