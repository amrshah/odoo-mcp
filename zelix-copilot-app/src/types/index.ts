/**
 * Domain types matching Odoo 19 (VetCairn) and Zelix AI Copilot Backend
 */

export interface Clinician {
  id: number;
  name: string;
  login: string;
  email: string;
  role: 'doctor' | 'technician' | 'receptionist' | 'practice_manager';
  clinicId: number;
  clinicName: string;
  licenseNumber: string;
  avatarUrl?: string;
}

export interface ClinicPractice {
  id: number;
  name: string;
  code: string;
  location: string;
}

export interface Patient {
  id: number;
  identifier: string; // e.g. PAT-000004
  name: string;
  species: string; // Canine, Feline, Equine
  breed: string;
  sex: 'male' | 'female' | 'neutered_male' | 'spayed_female';
  weightKg: number;
  age: string;
  microchipNumber?: string;
  primaryOwnerName: string;
  primaryOwnerPhone: string;
  primaryOwnerEmail: string;
  activeConditions: string[];
  allergies: string[];
  photoUrl?: string;
}

export interface DiarizedTurn {
  id: string;
  speaker: 'veterinarian' | 'owner' | 'ai';
  speakerName: string;
  speakerInitials: string;
  timestamp: string;
  text: string;
  isLive?: boolean;
}

export interface ClinicalEntity {
  id: string;
  type: 'symptom' | 'vital' | 'diagnosis' | 'procedure' | 'medication';
  label: string;
  detail: string;
  status: 'observed' | 'planned' | 'alert';
}

export interface SoapNote {
  id?: number;
  encounterId?: number;
  patientId: number;
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
  icd11Codes: string[];
  suggestedPrescriptions: {
    medication: string;
    dosage: string;
    frequency: string;
    duration: string;
    cautions?: string;
  }[];
  state: 'ai_draft' | 'veterinarian_approved';
  vetSignature?: string;
  signedAt?: string;
}

export type ScreenId =
  | 'flow'
  | 'voice'
  | 'soap'
  | 'workspace'
  | 'patients'
  | 'treatment'
  | 'history'
  | 'messaging'
  | 'notifications'
  | 'profile'
  | 'auth';
