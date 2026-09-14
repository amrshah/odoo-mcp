import React, { useState } from "react";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { Customer360Widget } from "./components/Customer360Widget";
import { HITLApprovalModal, ActionProposalData } from "./components/HITLApprovalModal";
import "@copilotkit/react-ui/styles.css";

export const App: React.FC = () => {
  // Context state representing current EmployeeContext
  const [activeCustomer, setActiveCustomer] = useState({
    id: "cust_1",
    name: "Acme Corp",
    email: "contact@acme.com",
    tier: "Gold",
  });

  const [activeInvoices, setActiveInvoices] = useState([
    { id: "inv_1", amount: 1500, status: "overdue" },
    { id: "inv_2", amount: 300, status: "paid" },
  ]);

  const [pendingInterrupt, setPendingInterrupt] = useState<{
    proposal: ActionProposalData;
    prompt: string;
  } | null>(null);

  const handleApprove = (actionId: string) => {
    console.log("Approved Action:", actionId);
    setPendingInterrupt(null);
  };

  const handleReject = (actionId: string) => {
    console.log("Rejected Action:", actionId);
    setPendingInterrupt(null);
  };

  return (
    <CopilotKit runtimeUrl="/api/copilotkit/ag-ui">
      <div className="min-h-screen bg-slate-50 flex">
        {/* Main Application Area */}
        <main className="flex-1 p-8">
          <header className="mb-6">
            <h1 className="text-2xl font-bold text-slate-900">Alamia Copilot Workspace</h1>
            <p className="text-sm text-slate-500">Connected to Alamia Core via AG-UI protocol</p>
          </header>

          <div className="space-y-4">
            <h2 className="text-sm font-semibold uppercase text-slate-400 tracking-wider">Active Workspace View</h2>
            <Customer360Widget
              customer={activeCustomer}
              invoices={activeInvoices}
              pendingTasksCount={1}
            />

            {pendingInterrupt && (
              <HITLApprovalModal
                proposal={pendingInterrupt.proposal}
                prompt={pendingInterrupt.prompt}
                onApprove={handleApprove}
                onReject={handleReject}
              />
            )}
          </div>
        </main>

        {/* CopilotKit Embedded Chat Interface */}
        <aside className="w-96 border-l border-slate-200 bg-white h-screen flex flex-col">
          <CopilotChat
            labels={{
              title: "Alamia AI Copilot",
              initial: "How can I assist you with your customer or operational tasks today?",
            }}
          />
        </aside>
      </div>
    </CopilotKit>
  );
};

export default App;
