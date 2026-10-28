import React, { useState } from 'react';
import { ScreenId } from '../types';

interface ClinicalNotificationsHubScreenProps {
  onNavigate: (screen: ScreenId) => void;
}

export const ClinicalNotificationsHubScreen: React.FC<ClinicalNotificationsHubScreenProps> = ({ onNavigate }) => {
  const [filter, setFilter] = useState<'all' | 'action' | 'lab' | 'pms' | 'chat'>('all');

  const notifications = [
    {
      id: 1,
      category: 'action lab',
      urgency: 'high',
      title: 'Barnaby (Golden Retriever · 4.5y)',
      subtitle: 'STAT Cytology · Requires Signature',
      detail: 'Left ear (AS) cytology: Malassezia pachydermatis (3+), cocci (1+). SOAP note drafted and awaiting Dr. Sarah Lin sign-off.',
      time: '12 min ago',
      icon: 'science',
      actionLabel: 'Review SOAP',
      actionScreen: 'soap' as ScreenId,
    },
    {
      id: 2,
      category: 'action pms',
      urgency: 'high',
      title: 'PMS Outbox Verification',
      subtitle: 'Encounter #1041 Committed',
      detail: 'Odoo 19 background sync completed for patient Max (PAT-000004). All billing items and clinical encounter ledger updated.',
      time: '45 min ago',
      icon: 'sync_saved_locally',
      actionLabel: 'View Record',
      actionScreen: 'patients' as ScreenId,
    },
    {
      id: 3,
      category: 'chat',
      urgency: 'normal',
      title: 'Eleanor Vance (Barnaby)',
      subtitle: 'Client Portal Inquiry',
      detail: 'Asked whether ear drops should be refrigerated. AI auto-replied with product storage guidance.',
      time: '2 hours ago',
      icon: 'forum',
      actionLabel: 'Open Chat',
      actionScreen: 'messaging' as ScreenId,
    },
    {
      id: 4,
      category: 'lab',
      urgency: 'normal',
      title: 'Milo (French Bulldog)',
      subtitle: 'Pre-Anesthetic Blood Panel Complete',
      detail: 'CBC and Chemistry 17 within normal limits. ALT, BUN, and Creatinine unremarkable.',
      time: '3 hours ago',
      icon: 'health_metrics',
      actionLabel: 'View History',
      actionScreen: 'history' as ScreenId,
    },
  ];

  const filtered = notifications.filter((n) => {
    if (filter === 'all') return true;
    return n.category.includes(filter);
  });

  return (
    <div className="flex flex-col w-full max-w-lg mx-auto px-4 pt-20 pb-28 space-y-4">
      {/* Top Utility Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h1 className="font-headline font-bold text-primary text-lg">Alerts & Inquiries</h1>
          <span className="px-2 py-0.5 rounded-full bg-error-container text-on-error-container text-[11px] font-bold font-code-vital">
            2 Urgent
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onNavigate('flow')}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-surface-container text-on-surface-variant hover:text-primary text-xs font-semibold"
          >
            <span className="material-symbols-outlined text-[16px]">done_all</span>
            <span>Mark Read</span>
          </button>
        </div>
      </div>

      {/* Filter Chips */}
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-0.5 text-xs font-semibold">
        <button
          onClick={() => setFilter('all')}
          className={`flex-shrink-0 px-3 py-1.5 rounded-full transition ${
            filter === 'all' ? 'bg-primary text-on-primary shadow-sm' : 'bg-surface-container text-on-surface'
          }`}
        >
          <span>All ({notifications.length})</span>
        </button>

        <button
          onClick={() => setFilter('action')}
          className={`flex-shrink-0 px-3 py-1.5 rounded-full flex items-center gap-1.5 transition ${
            filter === 'action' ? 'bg-primary text-on-primary shadow-sm' : 'bg-surface-container text-on-surface'
          }`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-error"></span>
          <span>Action Required (2)</span>
        </button>

        <button
          onClick={() => setFilter('lab')}
          className={`flex-shrink-0 px-3 py-1.5 rounded-full transition ${
            filter === 'lab' ? 'bg-primary text-on-primary shadow-sm' : 'bg-surface-container text-on-surface'
          }`}
        >
          <span>Lab & Cytology</span>
        </button>

        <button
          onClick={() => setFilter('chat')}
          className={`flex-shrink-0 px-3 py-1.5 rounded-full transition ${
            filter === 'chat' ? 'bg-primary text-on-primary shadow-sm' : 'bg-surface-container text-on-surface'
          }`}
        >
          <span>Owner Messages</span>
        </button>
      </div>

      {/* Notifications Stream */}
      <div className="space-y-3">
        {filtered.map((item) => (
          <div
            key={item.id}
            className="relative rounded-xl bg-surface-container-lowest p-4 shadow-sm border border-surface-container flex flex-col gap-2.5 overflow-hidden"
          >
            {item.urgency === 'high' && <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-error"></div>}

            <div className="flex items-start justify-between gap-2 pl-1">
              <div className="flex items-center gap-3">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                    item.urgency === 'high'
                      ? 'bg-error-container text-error'
                      : 'bg-surface-container text-primary'
                  }`}
                >
                  <span className="material-symbols-outlined text-[22px]">{item.icon}</span>
                </div>
                <div>
                  <h2 className="font-headline font-bold text-primary text-sm">{item.title}</h2>
                  <p
                    className={`text-xs font-semibold ${
                      item.urgency === 'high' ? 'text-error' : 'text-secondary'
                    }`}
                  >
                    {item.subtitle}
                  </p>
                </div>
              </div>
              <span className="text-[10px] text-on-surface-variant font-code-vital">{item.time}</span>
            </div>

            <p className="text-xs text-on-surface leading-relaxed pl-1">{item.detail}</p>

            <div className="pt-2 pl-1 flex justify-end">
              <button
                onClick={() => onNavigate(item.actionScreen)}
                className="px-3.5 py-1.5 rounded-lg bg-primary text-on-primary text-xs font-semibold flex items-center gap-1 shadow-sm active:scale-95 transition"
              >
                <span>{item.actionLabel}</span>
                <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
