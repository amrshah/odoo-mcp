import React, { useState, useEffect } from 'react';
import { Patient, DiarizedTurn, ClinicalEntity, ScreenId } from '../types';

interface VoiceConsultationScreenProps {
  patient: Patient;
  onNavigate: (screen: ScreenId) => void;
  onProcessedSoap?: () => void;
}

export const VoiceConsultationScreen: React.FC<VoiceConsultationScreenProps> = ({
  patient,
  onNavigate,
}) => {
  const [isRecording, setIsRecording] = useState<boolean>(true);
  const [seconds, setSeconds] = useState<number>(323); // 05:23
  const [waveformHeights, setWaveformHeights] = useState<number[]>([
    56, 48, 57, 30, 97, 77, 94, 26, 44, 17, 91, 30, 22, 81, 44, 19, 88, 82, 55, 94,
  ]);

  // Audio waveform animation
  useEffect(() => {
    if (!isRecording) return;
    const interval = setInterval(() => {
      setWaveformHeights((prev) =>
        prev.map(() => Math.floor(Math.random() * 85) + 15)
      );
    }, 160);
    return () => clearInterval(interval);
  }, [isRecording]);

  // Timer counter
  useEffect(() => {
    if (!isRecording) return;
    const interval = setInterval(() => {
      setSeconds((s) => s + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [isRecording]);

  const formatTimer = (totalSec: number) => {
    const mins = String(Math.floor(totalSec / 60)).padStart(2, '0');
    const secs = String(totalSec % 60).padStart(2, '0');
    return `${mins}:${secs}`;
  };

  const diarizedTurns: DiarizedTurn[] = [
    {
      id: '1',
      speaker: 'veterinarian',
      speakerName: 'Dr. Sarah Lin (Veterinarian)',
      speakerInitials: 'SL',
      timestamp: '03:12',
      text: "Barnaby's left ear canal shows marked erythema and moderate ceruminous exudate. Right ear has mild hyperaemia without exudate. Tympanic membranes intact bilaterally.",
    },
    {
      id: '2',
      speaker: 'owner',
      speakerName: 'Eleanor Vance (Pet Owner)',
      speakerInitials: 'EV',
      timestamp: '03:48',
      text: "He's been shaking his head intensely since Tuesday after swimming in the dog park pond. He whines whenever we scratch behind his left ear.",
    },
    {
      id: '3',
      speaker: 'veterinarian',
      speakerName: 'Dr. Sarah Lin (Veterinarian)',
      speakerInitials: 'SL',
      timestamp: 'Just now',
      text: "Understood. We will perform cytology swab right now and begin topical antimicrobial treatment. Let's ensure strict water immersion cessation for 10 days.",
      isLive: true,
    },
  ];

  const clinicalEntities: ClinicalEntity[] = [
    { id: '1', type: 'symptom', label: 'Erythema AS', detail: '(Left Ear)', status: 'alert' },
    { id: '2', type: 'symptom', label: 'Ceruminous Exudate AS', detail: '', status: 'observed' },
    { id: '3', type: 'vital', label: 'Normal AD Tympanum', detail: '(Right intact)', status: 'observed' },
    { id: '4', type: 'procedure', label: 'Ear Cytology Swab', detail: 'Planned', status: 'planned' },
  ];

  return (
    <div className="flex flex-col w-full max-w-lg mx-auto px-4 pt-20 pb-28 space-y-4">
      {/* Patient Context Banner */}
      <div className="w-full bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container relative">
        <div className="flex items-center justify-between gap-3 mb-2">
          <button
            onClick={() => onNavigate('patients')}
            className="flex items-center gap-3 min-w-0 text-left hover:opacity-90 transition-opacity"
          >
            <div className="w-12 h-12 rounded-xl overflow-hidden flex-shrink-0 bg-surface-container border border-surface-container">
              {patient.photoUrl ? (
                <img src={patient.photoUrl} alt={patient.name} className="w-full h-full object-cover" />
              ) : (
                <span className="material-symbols-outlined text-primary text-2xl flex items-center justify-center h-full">
                  pets
                </span>
              )}
            </div>
            <div className="flex flex-col min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-headline font-bold text-primary text-lg tracking-tight truncate">
                  {patient.name}
                </span>
                <span className="px-2 py-0.5 rounded-full bg-surface-container font-label text-xs text-on-surface-variant font-medium">
                  {patient.species} • {patient.breed}
                </span>
              </div>
              <div className="flex items-center gap-2 text-on-surface-variant text-xs mt-0.5">
                <span className="font-code-vital text-on-surface font-semibold">{patient.weightKg} kg</span>
                <span className="w-1 h-1 rounded-full bg-outline-variant"></span>
                <span>{patient.age}</span>
                <span className="w-1 h-1 rounded-full bg-outline-variant"></span>
                <span className="text-secondary font-medium">Bilateral Otitis Check</span>
              </div>
            </div>
          </button>

          <button
            onClick={() => onNavigate('patients')}
            aria-label="View Patient Chart"
            className="w-9 h-9 rounded-full bg-surface-container-low flex items-center justify-center text-on-surface-variant hover:text-primary transition-colors flex-shrink-0"
          >
            <span className="material-symbols-outlined text-[20px]">medical_information</span>
          </button>
        </div>

        {/* Sensor & Audio Hardware Status Pill */}
        <div className="flex items-center justify-between gap-2 text-on-surface-variant bg-surface-container-low/80 px-3 py-1.5 rounded-lg text-xs">
          <div className="flex items-center gap-2 min-w-0">
            <span className="relative flex h-2 w-2 flex-shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-secondary-fixed-dim opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-secondary"></span>
            </span>
            <span className="font-label text-on-surface font-semibold truncate">Mic Calibrated</span>
            <span className="hidden sm:inline-block text-on-surface-variant truncate">
              • Array (AI Denoise Active)
            </span>
          </div>
          <div className="flex items-center gap-1 text-secondary font-semibold font-code-vital">
            <span className="material-symbols-outlined text-[15px]">spatial_audio</span>
            <span>48kHz</span>
          </div>
        </div>
      </div>

      {/* Real-time Recording Console Card */}
      <div className="w-full bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container flex flex-col space-y-3.5">
        {/* Status & Timer */}
        <div className="flex items-center justify-between">
          <div
            className={`flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
              isRecording
                ? 'bg-error-container text-on-error-container'
                : 'bg-surface-container text-on-surface-variant'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isRecording ? 'bg-error animate-pulse' : 'bg-on-surface-variant'
              }`}
            ></span>
            <span>{isRecording ? 'Recording In Progress' : 'Recording Paused'}</span>
          </div>

          <div className="flex items-center gap-1.5 font-code-vital text-xl text-primary font-bold">
            <span className="material-symbols-outlined text-secondary text-[20px]">schedule</span>
            <span>{formatTimer(seconds)}</span>
          </div>
        </div>

        {/* Live Audio dB Visualizer Waves */}
        <div className="w-full bg-surface-container-low rounded-xl px-3.5 py-2.5 flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-on-surface-variant text-xs">
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined text-[15px] text-secondary">graphic_eq</span>
              <span>Acoustic Input Spectrum</span>
            </span>
            <span className="font-code-vital text-primary-container font-semibold">
              {isRecording ? '-18.4 dBFS' : 'Muted'}
            </span>
          </div>

          <div className="h-9 flex items-center justify-between gap-1 w-full">
            {waveformHeights.map((h, i) => (
              <div
                key={i}
                className="flex-1 rounded-full transition-all duration-150"
                style={{
                  height: `${isRecording ? h : 10}%`,
                  backgroundColor: i % 3 === 0 ? '#00352f' : i % 2 === 0 ? '#006c49' : '#0e4d45',
                  opacity: 0.85,
                }}
              />
            ))}
          </div>
        </div>

        {/* Bedside Controls */}
        <div className="grid grid-cols-12 gap-2 pt-1">
          <button
            onClick={() => setSeconds(0)}
            className="col-span-3 min-h-[48px] bg-surface-container rounded-lg text-xs font-semibold text-on-surface hover:bg-surface-variant flex flex-col items-center justify-center gap-0.5 active:scale-95 transition"
          >
            <span className="material-symbols-outlined text-[18px] text-error">delete_outline</span>
            <span>Discard</span>
          </button>

          <button
            onClick={() => setIsRecording(!isRecording)}
            className="col-span-3 min-h-[48px] bg-surface-container rounded-lg text-xs font-semibold text-on-surface hover:bg-surface-variant flex flex-col items-center justify-center gap-0.5 active:scale-95 transition"
          >
            <span className="material-symbols-outlined text-[18px] text-on-surface-variant">
              {isRecording ? 'pause_circle' : 'play_circle'}
            </span>
            <span>{isRecording ? 'Pause' : 'Resume'}</span>
          </button>

          <button
            onClick={() => {
              setIsRecording(false);
              onNavigate('soap');
            }}
            className="col-span-6 min-h-[48px] bg-primary text-on-primary rounded-lg text-xs font-bold flex items-center justify-center gap-2 shadow-sm hover:bg-primary-container active:scale-95 transition px-3"
          >
            <span className="material-symbols-outlined text-[20px] text-secondary-fixed">stop_circle</span>
            <span className="text-sm font-headline">Stop & Process</span>
          </button>
        </div>
      </div>

      {/* Live Diarized Transcription Stream */}
      <div className="w-full bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-surface-container space-y-3">
        <div className="flex items-center justify-between pb-1 border-b border-surface-container">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-secondary animate-ping"></span>
            <h2 className="font-headline font-bold text-primary text-sm">Live Diarized Transcript</h2>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-tertiary-fixed text-on-tertiary-fixed text-xs font-semibold flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px]">auto_awesome</span>
            2 Speakers
          </span>
        </div>

        {diarizedTurns.map((turn) => (
          <div key={turn.id} className="flex flex-col space-y-1">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-5 h-5 rounded-full bg-primary-fixed flex items-center justify-center text-on-primary-fixed font-bold text-[10px]">
                  {turn.speakerInitials}
                </div>
                <span className="font-semibold text-primary">{turn.speakerName}</span>
                {turn.isLive && <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-pulse"></span>}
              </div>
              <span className="font-code-vital text-on-surface-variant text-[10px]">{turn.timestamp}</span>
            </div>
            <div
              className={`rounded-xl p-3 text-xs leading-relaxed ${
                turn.speaker === 'veterinarian'
                  ? 'bg-surface-container-low text-on-surface border border-surface-container/60'
                  : 'bg-surface-container text-on-surface'
              }`}
            >
              {turn.text}
              {turn.isLive && (
                <span className="inline-block w-1.5 h-3.5 ml-1 bg-secondary animate-pulse align-middle"></span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Real-time Clinical Extraction Chips */}
      <div className="w-full bg-surface-container-low rounded-xl p-4 shadow-sm border border-surface-container space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-primary text-xs font-bold uppercase tracking-wider">
            <span className="material-symbols-outlined text-[18px] text-tertiary-container">auto_fix_high</span>
            <span>Live Clinical Entity Extraction</span>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-secondary-fixed/40 text-on-secondary-fixed-variant text-[11px] font-semibold">
            Auto-Parsed
          </span>
        </div>

        <div className="flex flex-wrap gap-2 pt-1">
          {clinicalEntities.map((entity) => (
            <div
              key={entity.id}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-lowest shadow-sm text-xs"
            >
              <span
                className={`material-symbols-outlined text-[15px] ${
                  entity.status === 'alert'
                    ? 'text-error'
                    : entity.status === 'planned'
                    ? 'text-tertiary-container'
                    : 'text-secondary'
                }`}
              >
                {entity.status === 'alert'
                  ? 'warning'
                  : entity.status === 'planned'
                  ? 'science'
                  : 'check_circle'}
              </span>
              <span className="font-semibold text-primary">{entity.label}</span>
              {entity.detail && (
                <span className="text-on-surface-variant font-code-vital text-[10px]">{entity.detail}</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Primary Bottom Action */}
      <div className="pt-2">
        <button
          onClick={() => onNavigate('soap')}
          className="w-full min-h-[52px] rounded-xl bg-primary text-on-primary hover:bg-primary-container shadow-md flex items-center justify-center gap-2 active:scale-98 transition-all font-headline font-bold text-sm"
        >
          <span className="material-symbols-outlined text-[20px] text-secondary-fixed">auto_awesome</span>
          <span>Process Recording to SOAP Note</span>
          <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
        </button>
      </div>
    </div>
  );
};
