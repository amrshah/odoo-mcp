import React, { useState } from 'react';
import { ScreenId } from '../types';

interface ConsultationHistoryScreenProps {
  onNavigate: (screen: ScreenId) => void;
}

export const ConsultationHistoryScreen: React.FC<ConsultationHistoryScreenProps> = ({ onNavigate }) => {
  const [filter, setFilter] = useState<'all' | 'review' | 'draft' | 'approved'>('all');
  const [searchTerm, setSearchTerm] = useState('');

  const consults = [
    {
      id: 1,
      patientName: 'Barnaby',
      ownerName: 'Eleanor Vance',
      species: 'Canine • Golden Retriever',
      weight: '32.4 kg',
      chiefComplaint: 'Bilateral Otitis Externa Check',
      time: 'Today 10:15 AM',
      status: 'review',
      statusLabel: 'Awaiting Signature',
      statusColor: 'bg-error-container text-on-error-container',
      audioDuration: '05:23',
      photoUrl: 'https://images.unsplash.com/photo-1552053831-71594a27632d?w=150&auto=format&fit=crop&q=80',
    },
    {
      id: 2,
      patientName: 'Luna',
      ownerName: 'Marcus Thorne',
      species: 'Feline • Domestic Shorthair',
      weight: '4.2 kg',
      chiefComplaint: 'Annual FVRCP Vaccination & Dental Assessment',
      time: 'Yesterday 03:45 PM',
      status: 'approved',
      statusLabel: 'Approved & Synced',
      statusColor: 'bg-secondary-fixed text-on-secondary-fixed-variant',
      audioDuration: '08:12',
      photoUrl: 'https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=150&auto=format&fit=crop&q=80',
    },
    {
      id: 3,
      patientName: 'Milo',
      ownerName: 'Chloe Bennett',
      species: 'Canine • French Bulldog',
      weight: '12.8 kg',
      chiefComplaint: 'Stenotic Nares Pre-Op Surgical Brief',
      time: 'Yesterday 11:30 AM',
      status: 'draft',
      statusLabel: 'Draft Synthesized',
      statusColor: 'bg-tertiary-fixed text-on-tertiary-fixed',
      audioDuration: '04:15',
      photoUrl: 'https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=150&auto=format&fit=crop&q=80',
    },
  ];

  const filteredConsults = consults.filter((c) => {
    if (filter !== 'all' && c.status !== filter) return false;
    if (
      searchTerm &&
      !c.patientName.toLowerCase().includes(searchTerm.toLowerCase()) &&
      !c.ownerName.toLowerCase().includes(searchTerm.toLowerCase()) &&
      !c.chiefComplaint.toLowerCase().includes(searchTerm.toLowerCase())
    ) {
      return false;
    }
    return true;
  });

  return (
    <div className="flex flex-col w-full max-w-lg mx-auto px-4 pt-20 pb-28 space-y-4">
      {/* Practice Cadence Overview */}
      <div className="w-full bg-surface-container-low rounded-xl p-4 shadow-sm border border-surface-container">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5 font-headline font-bold text-xs uppercase tracking-wider text-primary">
            <span className="material-symbols-outlined text-[18px]">analytics</span>
            <span>Practice Cadence (Week 42)</span>
          </div>
          <span className="font-code-vital text-xs text-secondary font-semibold">100% Synced</span>
        </div>

        <div className="grid grid-cols-3 gap-2 text-xs">
          <div className="bg-surface-container-lowest p-2.5 rounded-lg shadow-sm">
            <span className="text-[10px] text-on-surface-variant">Consults</span>
            <p className="font-headline font-bold text-base text-primary mt-0.5">14</p>
            <span className="text-[10px] text-secondary font-medium">+4 vs Last Week</span>
          </div>
          <div className="bg-surface-container-lowest p-2.5 rounded-lg shadow-sm">
            <span className="text-[10px] text-on-surface-variant">Audio Vault</span>
            <p className="font-headline font-bold text-base text-primary mt-0.5">100%</p>
            <span className="text-[10px] text-secondary font-medium">Encrypted</span>
          </div>
          <div className="bg-surface-container-lowest p-2.5 rounded-lg shadow-sm">
            <span className="text-[10px] text-on-surface-variant">Avg Draft</span>
            <p className="font-headline font-bold text-base text-primary mt-0.5">38s</p>
            <span className="text-[10px] text-on-surface-variant font-code-vital">Fast SLM</span>
          </div>
        </div>
      </div>

      {/* Search Input */}
      <div className="relative w-full">
        <span className="material-symbols-outlined text-outline text-[20px] absolute left-3 top-2.5 pointer-events-none">
          search
        </span>
        <input
          type="search"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search patient, owner, or diagnosis..."
          className="w-full bg-surface-container-lowest pl-10 pr-4 py-2.5 rounded-xl text-xs text-on-surface border border-surface-container focus:outline-none shadow-sm"
        />
      </div>

      {/* Filter Chips */}
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-0.5 text-xs font-semibold">
        <button
          onClick={() => setFilter('all')}
          className={`flex-shrink-0 px-3 py-1.5 rounded-full flex items-center gap-1.5 transition ${
            filter === 'all' ? 'bg-primary text-on-primary shadow-sm' : 'bg-surface-container text-on-surface'
          }`}
        >
          <span>All Consultations</span>
          <span className="px-1.5 py-0.2 rounded-full bg-primary-container text-white text-[10px]">14</span>
        </button>

        <button
          onClick={() => setFilter('review')}
          className={`flex-shrink-0 px-3 py-1.5 rounded-full flex items-center gap-1.5 transition ${
            filter === 'review' ? 'bg-primary text-on-primary shadow-sm' : 'bg-surface-container text-on-surface'
          }`}
        >
          <span>Awaiting Review</span>
          <span className="px-1.5 py-0.2 rounded-full bg-error text-white text-[10px]">1</span>
        </button>

        <button
          onClick={() => setFilter('approved')}
          className={`flex-shrink-0 px-3 py-1.5 rounded-full flex items-center gap-1.5 transition ${
            filter === 'approved' ? 'bg-primary text-on-primary shadow-sm' : 'bg-surface-container text-on-surface'
          }`}
        >
          <span className="material-symbols-outlined text-[14px] text-secondary">check_circle</span>
          <span>Approved & Synced</span>
        </button>
      </div>

      {/* Consultations Feed */}
      <div className="space-y-3">
        {filteredConsults.map((c) => (
          <div
            key={c.id}
            onClick={() => onNavigate('soap')}
            className="w-full bg-surface-container-lowest rounded-xl p-3.5 shadow-sm border border-surface-container cursor-pointer hover:border-primary transition flex flex-col space-y-2.5"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-11 h-11 rounded-xl overflow-hidden bg-surface-container flex-shrink-0">
                  <img src={c.photoUrl} alt="" className="w-full h-full object-cover" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-headline font-bold text-primary text-sm truncate">{c.patientName}</span>
                    <span className="text-[11px] text-on-surface-variant font-code-vital">{c.weight}</span>
                  </div>
                  <p className="text-[11px] text-on-surface-variant truncate">{c.species}</p>
                  <p className="text-[11px] text-on-surface font-medium truncate mt-0.5">{c.chiefComplaint}</p>
                </div>
              </div>

              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider flex-shrink-0 ${c.statusColor}`}>
                {c.statusLabel}
              </span>
            </div>

            <div className="flex items-center justify-between text-[11px] text-on-surface-variant pt-2 border-t border-surface-container font-code-vital">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[15px] text-secondary">mic</span>
                <span>Audio Vault: {c.audioDuration}</span>
              </div>
              <span>{c.time}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
