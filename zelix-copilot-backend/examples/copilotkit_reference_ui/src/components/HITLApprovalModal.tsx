import React, { useState } from "react";

export interface ActionProposalData {
  action_id: string;
  action_type: string;
  target: { type: string; id: string };
  reason: string;
  risk_level: string;
  proposed_changes?: Record<string, any>;
}

export interface HITLApprovalModalProps {
  proposal: ActionProposalData;
  prompt: string;
  onApprove: (actionId: string) => void;
  onReject: (actionId: string) => void;
}

export const HITLApprovalModal: React.FC<HITLApprovalModalProps> = ({
  proposal,
  prompt,
  onApprove,
  onReject,
}) => {
  const [resolved, setResolved] = useState<string | null>(null);

  const getRiskBadgeClass = (risk: string) => {
    switch (risk.toUpperCase()) {
      case "CRITICAL":
      case "HIGH":
        return "bg-red-100 text-red-800 border-red-300";
      case "MEDIUM":
        return "bg-amber-100 text-amber-800 border-amber-300";
      default:
        return "bg-blue-100 text-blue-800 border-blue-300";
    }
  };

  if (resolved) {
    return (
      <div className="p-3 my-2 rounded-lg bg-slate-100 border border-slate-200 text-xs text-slate-600">
        Action {proposal.action_id} was <strong>{resolved}</strong> by operator.
      </div>
    );
  }

  return (
    <div className="p-4 rounded-xl border-2 border-amber-300 bg-amber-50/50 shadow-sm max-w-md my-3">
      <div className="flex items-center justify-between pb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-amber-800">
          Human Confirmation Required
        </span>
        <span className={`px-2 py-0.5 rounded text-xs font-bold border ${getRiskBadgeClass(proposal.risk_level)}`}>
          {proposal.risk_level} RISK
        </span>
      </div>

      <p className="text-sm text-slate-800 font-medium py-1">{prompt}</p>

      <div className="bg-white p-2.5 rounded-lg border border-slate-200 my-2 text-xs space-y-1 text-slate-700">
        <div><strong>Action:</strong> {proposal.action_type}</div>
        <div><strong>Target:</strong> {proposal.target.type}:{proposal.target.id}</div>
        <div><strong>Reason:</strong> {proposal.reason}</div>
        {proposal.proposed_changes && Object.keys(proposal.proposed_changes).length > 0 && (
          <div>
            <strong>Changes:</strong>
            <pre className="bg-slate-50 p-1.5 rounded mt-1 overflow-x-auto text-[11px]">
              {JSON.stringify(proposal.proposed_changes, null, 2)}
            </pre>
          </div>
        )}
      </div>

      <div className="flex justify-end space-x-2 pt-2">
        <button
          onClick={() => {
            setResolved("REJECTED");
            onReject(proposal.action_id);
          }}
          className="px-3 py-1.5 text-xs font-semibold rounded-md border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 transition"
        >
          Reject
        </button>
        <button
          onClick={() => {
            setResolved("APPROVED");
            onApprove(proposal.action_id);
          }}
          className="px-3 py-1.5 text-xs font-semibold rounded-md bg-amber-600 hover:bg-amber-700 text-white shadow-sm transition"
        >
          Confirm & Execute
        </button>
      </div>
    </div>
  );
};
