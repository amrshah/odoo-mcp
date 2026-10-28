import React, { useState } from 'react';
import { Patient, ScreenId } from '../types';

interface AIWorkspaceScreenProps {
  patient: Patient;
  onNavigate: (screen: ScreenId) => void;
}

export const AIWorkspaceScreen: React.FC<AIWorkspaceScreenProps> = ({ patient, onNavigate }) => {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<
    { role: 'user' | 'assistant'; content: string; time: string; cards?: string[] }[]
  >([
    {
      role: 'assistant',
      content:
        `Hello Dr. Sarah Lin. I have loaded Barnaby's longitudinal record from Odoo 19 (PAT-000004). Weight: ${patient.weightKg} kg. Penicillin allergy flagged. How can I assist with this consultation?`,
      time: '10:14 AM',
    },
    {
      role: 'user',
      content: 'Check drug interaction: Can we administer oral Apoquel while Barnaby is on topical Surolan?',
      time: '10:15 AM',
    },
    {
      role: 'assistant',
      content:
        '**Zero Drug Interaction Flagged.**\n\nTopical Surolan (miconazole + polymyxin B + prednisolone) acts locally in the external auditory canal with minimal systemic absorption.\n\nOral Oclacitinib (Apoquel) at standard 0.4-0.6 mg/kg (Barnaby: 16 mg q12h x 14 days, then q24h) is safe to co-administer to alleviate secondary allergic pruritus while treating the otitis externa.',
      time: '10:15 AM',
      cards: ['Apoquel (Oclacitinib) 16mg • Safe', 'Formulary Clearance Verified'],
    },
  ]);

  const handleSend = () => {
    if (!query.trim()) return;
    const userMsg = query;
    setQuery('');
    setMessages((prev) => [
      ...prev,
      {
        role: 'user',
        content: userMsg,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
      {
        role: 'assistant',
        content:
          `Evaluating clinical intent via Alamia AI Gateway on Cloudflare... Processed patient context for ${patient.name} (${patient.species}). No contraindications found with current Odoo formulary rules.`,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  return (
    <div className="flex flex-col w-full max-w-lg mx-auto px-4 pt-20 pb-28 space-y-4">
      {/* Header Info */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-tertiary-container text-white flex items-center justify-center">
            <span className="material-symbols-outlined text-lg">psychology</span>
          </div>
          <div>
            <h1 className="font-headline font-bold text-primary text-base">Alamia Clinical Copilot</h1>
            <p className="text-[11px] text-on-surface-variant font-medium">Edge SLM • VetCairn Institutional Memory</p>
          </div>
        </div>
        <span className="px-2.5 py-0.5 rounded-full bg-secondary-fixed/40 text-on-secondary-fixed-variant text-[11px] font-bold">
          Latency &lt; 850ms
        </span>
      </div>

      {/* Chat Stream */}
      <div className="space-y-3">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex flex-col space-y-1 ${
              msg.role === 'user' ? 'items-end' : 'items-start'
            }`}
          >
            <span className="text-[10px] text-on-surface-variant font-code-vital px-1">{msg.time}</span>
            <div
              className={`p-3.5 rounded-xl text-xs leading-relaxed max-w-[90%] shadow-sm ${
                msg.role === 'user'
                  ? 'bg-primary text-on-primary rounded-tr-sm'
                  : 'bg-surface-container-lowest text-on-surface border border-surface-container rounded-tl-sm'
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>
              {msg.cards && (
                <div className="mt-2.5 pt-2 border-t border-surface-container flex flex-wrap gap-1.5">
                  {msg.cards.map((c, ci) => (
                    <span
                      key={ci}
                      className="px-2 py-0.5 rounded bg-secondary-fixed text-on-secondary-fixed-variant font-semibold text-[10px] flex items-center gap-1"
                    >
                      <span className="material-symbols-outlined text-[13px]">check</span>
                      {c}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input Box */}
      <div className="fixed bottom-16 left-0 right-0 p-3 bg-surface/90 backdrop-blur-xl border-t border-surface-container z-40">
        <div className="max-w-lg mx-auto flex items-center gap-2 bg-surface-container-lowest rounded-xl p-1.5 border border-surface-container shadow-sm">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask Copilot (e.g., dosage, differential diagnosis)..."
            className="flex-1 px-3 py-2 text-xs bg-transparent focus:outline-none"
          />
          <button
            onClick={handleSend}
            disabled={!query.trim()}
            className="w-9 h-9 rounded-lg bg-primary text-on-primary disabled:opacity-40 flex items-center justify-center flex-shrink-0 transition active:scale-95"
          >
            <span className="material-symbols-outlined text-[18px]">send</span>
          </button>
        </div>
      </div>
    </div>
  );
};
