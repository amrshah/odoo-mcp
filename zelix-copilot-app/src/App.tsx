import React, { useState } from 'react';
import { Clinician, Patient, ScreenId } from './types';
import { ApiService } from './services/api';
import { Header } from './components/Header';
import { BottomNav } from './components/BottomNav';

// All 11 Stitch Design Screens
import { ConsultationFlowScreen } from './screens/ConsultationFlowScreen';
import { VoiceConsultationScreen } from './screens/VoiceConsultationScreen';
import { SoapNoteEditorScreen } from './screens/SoapNoteEditorScreen';
import { PatientContextScreen } from './screens/PatientContextScreen';
import { TreatmentPlanScreen } from './screens/TreatmentPlanScreen';
import { PetOwnerMessagingScreen } from './screens/PetOwnerMessagingScreen';
import { ConsultationHistoryScreen } from './screens/ConsultationHistoryScreen';
import { AIWorkspaceScreen } from './screens/AIWorkspaceScreen';
import { ClinicalNotificationsHubScreen } from './screens/ClinicalNotificationsHubScreen';
import { VeterinarianProfileScreen } from './screens/VeterinarianProfileScreen';
import { AuthAndPracticeSwitcherScreen } from './screens/AuthAndPracticeSwitcherScreen';

export const App: React.FC = () => {
  const [currentScreen, setCurrentScreen] = useState<ScreenId>('flow');
  const [clinician, setClinician] = useState<Clinician>(ApiService.getActiveClinician());
  const [patient] = useState<Patient>(ApiService.getSamplePatient());

  const renderScreen = () => {
    switch (currentScreen) {
      case 'flow':
        return <ConsultationFlowScreen patient={patient} onNavigate={setCurrentScreen} />;
      case 'voice':
        return <VoiceConsultationScreen patient={patient} onNavigate={setCurrentScreen} />;
      case 'soap':
        return <SoapNoteEditorScreen patient={patient} onNavigate={setCurrentScreen} />;
      case 'patients':
        return <PatientContextScreen patient={patient} onNavigate={setCurrentScreen} />;
      case 'treatment':
        return <TreatmentPlanScreen patient={patient} onNavigate={setCurrentScreen} />;
      case 'messaging':
        return <PetOwnerMessagingScreen patient={patient} onNavigate={setCurrentScreen} />;
      case 'history':
        return <ConsultationHistoryScreen onNavigate={setCurrentScreen} />;
      case 'workspace':
        return <AIWorkspaceScreen patient={patient} onNavigate={setCurrentScreen} />;
      case 'notifications':
        return <ClinicalNotificationsHubScreen onNavigate={setCurrentScreen} />;
      case 'profile':
        return <VeterinarianProfileScreen clinician={clinician} onNavigate={setCurrentScreen} />;
      case 'auth':
        return (
          <AuthAndPracticeSwitcherScreen
            clinician={clinician}
            onUpdateClinician={setClinician}
            onNavigate={setCurrentScreen}
          />
        );
      default:
        return <ConsultationFlowScreen patient={patient} onNavigate={setCurrentScreen} />;
    }
  };

  return (
    <div className="bg-surface min-h-screen text-on-surface flex flex-col antialiased selection:bg-secondary-fixed selection:text-on-secondary-fixed-variant">
      <Header clinician={clinician} currentScreen={currentScreen} onNavigate={setCurrentScreen} />
      <main className="flex-1 w-full">{renderScreen()}</main>
      <BottomNav currentScreen={currentScreen} onNavigate={setCurrentScreen} />
    </div>
  );
};

export default App;
