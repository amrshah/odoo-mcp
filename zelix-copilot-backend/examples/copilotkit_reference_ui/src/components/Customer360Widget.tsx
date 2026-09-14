import React from "react";

export interface CustomerData {
  id: string;
  name: string;
  email: string;
  tier?: string;
  balance?: number;
}

export interface InvoiceData {
  id: string;
  amount: number;
  status: string;
}

export interface Customer360Props {
  customer: CustomerData;
  invoices: InvoiceData[];
  pendingTasksCount?: number;
}

export const Customer360Widget: React.FC<Customer360Props> = ({
  customer,
  invoices,
  pendingTasksCount = 0,
}) => {
  const totalDue = invoices
    .filter((inv) => inv.status.toLowerCase() === "overdue")
    .reduce((sum, inv) => sum + inv.amount, 0);

  return (
    <div className="p-4 rounded-xl border border-slate-200 bg-white shadow-sm max-w-md my-2">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div>
          <h3 className="font-semibold text-slate-900 text-lg">{customer.name}</h3>
          <p className="text-xs text-slate-500">{customer.email} • ID: {customer.id}</p>
        </div>
        {customer.tier && (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 uppercase">
            {customer.tier}
          </span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2 py-3 text-center">
        <div className="bg-slate-50 p-2 rounded-lg">
          <span className="block text-xs text-slate-500">Invoices</span>
          <span className="font-bold text-slate-800 text-sm">{invoices.length}</span>
        </div>
        <div className="bg-slate-50 p-2 rounded-lg">
          <span className="block text-xs text-slate-500">Overdue</span>
          <span className="font-bold text-red-600 text-sm">${totalDue.toFixed(2)}</span>
        </div>
        <div className="bg-slate-50 p-2 rounded-lg">
          <span className="block text-xs text-slate-500">Open Tasks</span>
          <span className="font-bold text-slate-800 text-sm">{pendingTasksCount}</span>
        </div>
      </div>
    </div>
  );
};
