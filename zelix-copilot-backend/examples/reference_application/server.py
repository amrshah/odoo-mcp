"""Interactive Web Server for Alamia AI Copilot Reference Application.

Hosts the interactive web workspace combining:
1. Host Application Store (Customers, Invoices, Tasks)
2. Interactive Direct Skill Trigger buttons
3. Real-Time AG-UI Protocol Stream Inspector
4. Embedded CopilotKit-powered Chat Interface with Generative UI & HITL Confirmation Modals
"""

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from adapters.ag_ui.events import AGUIEvent, AGUIEventType, InterruptData
from adapters.ag_ui.serializer import AGUISerializer
from adapters.ag_ui.server import AGUIHandler
from adapters.ai.providers.mock_provider import MockAIModelProvider
from adapters.application.reference.in_memory_adapter import InMemoryApplicationAdapter
from core.actions.proposal import ActionProposal, ActionStatus
from core.actions.statemachine import ActionStateMachine
from core.ai.models import ChatMessage, ChatRole
from core.ai.router import AIModelRouter
from core.roles.manifest import RoleManifest
from core.roles.registry import RoleRegistry
from core.runtime.engine import CopilotEngine
from core.sessions.context import EmployeeContext
from core.skills.registry import SkillRegistry
from core.tools.reference_tools import (
    GetCustomerInvoicesTool,
    GetCustomerTasksTool,
    GetCustomerTool,
    GetWorkItemsTool,
)
from core.tools.registry import ToolRegistry
from skills.examples.customer_360 import Customer360Skill
from skills.examples.daily_briefing import DailyBriefingSkill
from skills.examples.payment_followup import PaymentFollowupSkill


def create_reference_engine():
    adapter = InMemoryApplicationAdapter()

    # Seed sample entities
    adapter.create("customer", {
        "id": "cust_101",
        "name": "Acme Global Industries",
        "email": "finance@acmeglobal.com",
        "tier": "enterprise",
        "balance": 8400.0,
    })
    adapter.create("customer", {
        "id": "cust_102",
        "name": "Starlight Technologies",
        "email": "ops@starlight.io",
        "tier": "growth",
        "balance": 1200.0,
    })

    adapter.create("invoice", {
        "id": "inv_801",
        "customer_id": "cust_101",
        "amount": 5400.0,
        "status": "overdue",
    })
    adapter.create("invoice", {
        "id": "inv_802",
        "customer_id": "cust_101",
        "amount": 3000.0,
        "status": "paid",
    })
    adapter.create("invoice", {
        "id": "inv_803",
        "customer_id": "cust_102",
        "amount": 1200.0,
        "status": "overdue",
    })

    adapter.create("task", {
        "id": "task_501",
        "title": "Prepare Q3 enterprise summary",
        "priority": "high",
        "status": "pending",
    })

    skills = SkillRegistry()
    skills.register(Customer360Skill())
    skills.register(PaymentFollowupSkill())
    skills.register(DailyBriefingSkill())

    tools = ToolRegistry()
    tools.register(GetCustomerTool(adapter))
    tools.register(GetCustomerInvoicesTool(adapter))
    tools.register(GetCustomerTasksTool(adapter))
    tools.register(GetWorkItemsTool(adapter))

    roles = RoleRegistry()
    roles.register(RoleManifest(
        id="finance_assistant",
        name="Finance Assistant",
        skills=["customer_360", "payment_followup"],
        permissions=["customers.read", "invoices.read", "tasks.read", "tasks.create", "financial.write"],
    ))
    roles.register(RoleManifest(
        id="executive_assistant",
        name="Executive Assistant",
        skills=["daily_briefing"],
        permissions=["tasks.read"],
    ))
    roles.register(RoleManifest(
        id="read_only_viewer",
        name="Read Only Viewer",
        skills=["customer_360"],
        permissions=["customers.read", "invoices.read"],
    ))

    ai_router = AIModelRouter(default_provider=MockAIModelProvider())

    engine = CopilotEngine(
        skill_registry=skills,
        tool_registry=tools,
        role_registry=roles,
        ai_router=ai_router,
        application_adapter=adapter,
    )

    return engine, adapter


# Global runtime instances
ENGINE, ADAPTER = create_reference_engine()
AG_UI_HANDLER = AGUIHandler(engine=ENGINE)
PENDING_ACTIONS: Dict[str, Tuple[ActionProposal, EmployeeContext]] = {}


def extract_target_customer_id(q: str) -> str:
    """Extract customer ID or company name dynamically from natural language query."""
    # 1. Look for cust_xxx explicitly (e.g. cust_2101, cust_101)
    match_cust = re.search(r"\bcust_([a-zA-Z0-9_-]+)\b", q)
    if match_cust:
        return f"cust_{match_cust.group(1)}"

    # 2. Look for 'customer <id/name>', 'cust <id/name>', 'client <id/name>'
    match_named = re.search(r"\b(?:customer|cust|client|account)\s+([a-zA-Z0-9_-]+)\b", q)
    if match_named:
        val = match_named.group(1).lower()
        if "acme" in val:
            return "cust_101"
        elif "starlight" in val:
            return "cust_102"
        elif val.startswith("cust_"):
            return val
        else:
            return f"cust_{val}"

    # 3. Explicit company names
    if "acme" in q:
        return "cust_101"
    if "starlight" in q:
        return "cust_102"

    # 4. Standalone numbers like 101, 102, 2101
    match_num = re.search(r"\b(\d+)\b", q)
    if match_num:
        num = match_num.group(1)
        return f"cust_{num}"

    return "cust_101"


def process_natural_language_query(query: str, role: str) -> Dict[str, Any]:
    """Parse natural language query and route through Alamia Copilot Engine via AG-UI."""
    role_perms = {
        "finance_assistant": ["customers.read", "invoices.read", "tasks.read", "tasks.create", "financial.write"],
        "executive_assistant": ["tasks.read"],
        "read_only_viewer": ["customers.read"],
    }
    context = EmployeeContext(
        user_id=f"user_{role}",
        role=role,
        permissions=role_perms.get(role, ["customers.read"]),
    )

    q = query.lower().strip()

    # 1. Customer 360 lookup (e.g. "show me customer 101", "get customer 2101", "who is acme")
    if "customer" in q or "acme" in q or "starlight" in q or "cust_" in q or ("show" in q and re.search(r"\b\d+\b", q)):
        target_cust = extract_target_customer_id(q)
        result = ENGINE.execute_skill("customer_360", context, customer_id=target_cust)
        return {
            "query": query,
            "skill_id": "customer_360",
            "success": result.success,
            "output": result.output if result.success else {},
            "proposed_actions": result.proposed_actions,
            "error": result.error,
            "message": f"Retrieved Customer 360 overview for {target_cust}." if result.success else result.error,
        }

    # 2. Overdue invoices check
    elif "invoice" in q and ("overdue" in q or "unpaid" in q or "what" in q or "show" in q):
        invoices = ADAPTER.search("invoice", {"status": "overdue"})
        total = sum(i.get("amount", 0) for i in invoices)
        return {
            "query": query,
            "skill_id": "invoice_query",
            "success": True,
            "output": {"overdue_invoices": invoices, "total_overdue": total, "count": len(invoices)},
            "proposed_actions": [],
            "message": f"Found {len(invoices)} overdue invoice(s) totaling ${total:.2f}.",
        }

    # 3. Operational briefing (e.g. "give me my daily operational briefing", "briefing", "work items")
    elif "briefing" in q or "task" in q or "work" in q:
        result = ENGINE.execute_skill("daily_briefing", context)
        return {
            "query": query,
            "skill_id": "daily_briefing",
            "success": result.success,
            "output": result.output,
            "proposed_actions": result.proposed_actions,
            "error": result.error,
            "message": result.output.get("briefing_text") if result.success else result.error,
        }

    # 4. Payment follow-up with ActionProposal mutation (e.g. "follow up on overdue payments", "collect payment")
    elif "follow" in q or "payment" in q or "collect" in q:
        target_cust = extract_target_customer_id(q)
        # Always require confirmation for payment followup to demonstrate HITL flow
        ENGINE.policies.confirmation_policy.always_require_confirmation_actions.add("create_followup")
        result = ENGINE.execute_skill("payment_followup", context, customer_id=target_cust)

        # Register pending interrupt for HITL confirmation
        for raw_prop in result.proposed_actions:
            prop = ActionProposal.model_validate(raw_prop)
            PENDING_ACTIONS[prop.action_id] = (prop, context)

        return {
            "query": query,
            "skill_id": "payment_followup",
            "success": result.success,
            "output": result.output,
            "proposed_actions": result.proposed_actions,
            "error": result.error,
            "message": f"Analyzed overdue accounts for {target_cust}. Proposed follow-up action awaiting your confirmation." if result.success else result.error,
        }

    # Fallback general query
    return {
        "query": query,
        "skill_id": "general_assistant",
        "success": True,
        "output": {"status": "ready", "available_skills": ["customer_360", "payment_followup", "daily_briefing"]},
        "proposed_actions": [],
        "message": f"I received your request: '{query}'. You can ask me to view customers, inspect overdue invoices, generate a daily briefing, or perform payment follow-ups.",
    }


HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Alamia AI Copilot — Live Interactive Workspace & CopilotKit Chat</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @keyframes pulse-slow { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    .animate-pulse-slow { animation: pulse-slow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    .custom-scrollbar::-webkit-scrollbar { width: 6px; }
    .custom-scrollbar::-webkit-scrollbar-track { background: #0f172a; }
    .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans antialiased overflow-hidden">
  <div class="flex flex-col h-screen">
    <!-- Navbar -->
    <header class="bg-slate-900 border-b border-slate-800 px-6 py-3 flex items-center justify-between shrink-0 shadow-md">
      <div class="flex items-center space-x-3">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/30">
          <i class="fa-solid fa-robot text-base"></i>
        </div>
        <div>
          <h1 class="font-bold text-base text-white tracking-tight flex items-center">
            Alamia AI Copilot Starter
            <span class="ml-2 px-2 py-0.5 text-[10px] font-semibold bg-indigo-950 text-indigo-300 border border-indigo-700/80 rounded-full">CopilotKit + AG-UI</span>
          </h1>
          <p class="text-xs text-slate-400">Autonomous Business Employee & Copilot UX</p>
        </div>
      </div>

      <div class="flex items-center space-x-4">
        <div class="flex items-center space-x-2 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-700 text-xs shadow-inner">
          <span class="text-slate-400"><i class="fa-solid fa-user-shield text-slate-400 mr-1"></i> Active Role:</span>
          <select id="roleSelect" onchange="updateRole()" class="bg-transparent text-indigo-400 font-bold focus:outline-none cursor-pointer">
            <option value="finance_assistant" selected>Finance Assistant (All Perms)</option>
            <option value="executive_assistant">Executive Assistant (Tasks Only)</option>
            <option value="read_only_viewer">Read-Only Viewer (Read Customers)</option>
          </select>
        </div>
        <div class="flex items-center space-x-2 text-xs text-emerald-400 bg-emerald-950/80 border border-emerald-800 px-3 py-1 rounded-full">
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-slow"></span>
          <span class="font-medium">AG-UI Runtime Ready</span>
        </div>
      </div>
    </header>

    <!-- Main Workspace Grid (3 Columns) -->
    <div class="grid grid-cols-12 flex-1 overflow-hidden">
      
      <!-- 1. LEFT COLUMN: Host Application Data Store (3 Cols) -->
      <section class="col-span-3 bg-slate-900/80 border-r border-slate-800 flex flex-col overflow-hidden">
        <div class="px-4 py-3 border-b border-slate-800 flex items-center justify-between shrink-0 bg-slate-900">
          <div class="flex items-center space-x-2">
            <i class="fa-solid fa-database text-slate-400 text-xs"></i>
            <h2 class="font-semibold text-xs text-slate-200 uppercase tracking-wider">Host Application State</h2>
          </div>
          <button onclick="refreshState()" class="text-xs text-slate-400 hover:text-indigo-400 transition" title="Refresh State">
            <i class="fa-solid fa-arrows-rotate"></i>
          </button>
        </div>

        <div class="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar" id="storeContainer">
          <!-- Customers Section -->
          <div>
            <div class="flex justify-between items-center mb-2">
              <h3 class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Customers</h3>
              <span class="text-[10px] text-slate-500 font-mono" id="custCount">2 records</span>
            </div>
            <div id="customersList" class="space-y-2">Loading...</div>
          </div>

          <!-- Invoices Section -->
          <div>
            <div class="flex justify-between items-center mb-2">
              <h3 class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Invoices</h3>
              <span class="text-[10px] text-slate-500 font-mono" id="invCount">3 records</span>
            </div>
            <div id="invoicesList" class="space-y-2">Loading...</div>
          </div>

          <!-- Tasks Section -->
          <div>
            <div class="flex justify-between items-center mb-2">
              <h3 class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Tasks</h3>
              <span class="text-[10px] text-slate-500 font-mono" id="taskCount">1 record</span>
            </div>
            <div id="tasksList" class="space-y-2">Loading...</div>
          </div>
        </div>
      </section>

      <!-- 2. CENTER COLUMN: CopilotKit Conversational Chat Interface (5 Cols) -->
      <section class="col-span-5 bg-slate-950 flex flex-col overflow-hidden border-r border-slate-800">
        <!-- Chat Header -->
        <div class="px-5 py-3 border-b border-slate-800 bg-slate-900 flex items-center justify-between shrink-0">
          <div class="flex items-center space-x-2">
            <div class="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center text-xs text-white">
              <i class="fa-solid fa-comments"></i>
            </div>
            <div>
              <h2 class="font-bold text-xs text-white">CopilotKit Conversational Interface</h2>
              <p class="text-[10px] text-slate-400">Natural Language Agent & Generative UI</p>
            </div>
          </div>
          <button onclick="clearChat()" class="text-[11px] text-slate-400 hover:text-slate-200 transition" title="Clear chat history">
            <i class="fa-solid fa-trash-can mr-1"></i> Clear
          </button>
        </div>

        <!-- Chat Suggestions / Quick Prompts -->
        <div class="px-4 py-2.5 bg-slate-900/60 border-b border-slate-800/80 flex items-center space-x-2 overflow-x-auto shrink-0 custom-scrollbar">
          <span class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider shrink-0">Prompts:</span>
          <button onclick="sendQuickPrompt('Show me customer 101')" class="px-2.5 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md border border-slate-700 transition shrink-0">
            Show customer 101
          </button>
          <button onclick="sendQuickPrompt('What invoices are overdue?')" class="px-2.5 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md border border-slate-700 transition shrink-0">
            What invoices are overdue?
          </button>
          <button onclick="sendQuickPrompt('Give me my daily operational briefing')" class="px-2.5 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md border border-slate-700 transition shrink-0">
            Daily briefing
          </button>
          <button onclick="sendQuickPrompt('Follow up on overdue payments')" class="px-2.5 py-1 text-[11px] bg-amber-950/60 hover:bg-amber-900/60 text-amber-300 rounded-md border border-amber-800/80 transition shrink-0 font-medium">
            Follow up overdue (HITL)
          </button>
        </div>

        <!-- Chat Message Log -->
        <div class="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar" id="chatContainer">
          <!-- Initial Assistant Welcome -->
          <div class="flex items-start space-x-3">
            <div class="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0 text-xs text-white shadow">
              <i class="fa-solid fa-robot"></i>
            </div>
            <div class="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-none p-3.5 max-w-[90%] text-xs text-slate-200 shadow-sm space-y-2">
              <p class="font-semibold text-indigo-400">Hello! I'm your Alamia AI Copilot.</p>
              <p class="text-slate-300">You can interact with me conversationally or ask me to execute tasks like:</p>
              <ul class="list-disc list-inside space-y-1 text-slate-400 text-[11px]">
                <li><code class="text-indigo-300">"Show me customer 101"</code> (Generates Customer 360 View)</li>
                <li><code class="text-indigo-300">"What invoices are overdue?"</code> (Summarizes unpaid bills)</li>
                <li><code class="text-indigo-300">"Give me my daily operational briefing"</code> (Briefs tasks)</li>
                <li><code class="text-amber-300">"Follow up on overdue payments"</code> (Proposes mutation with Human Confirmation)</li>
              </ul>
            </div>
          </div>
        </div>

        <!-- Chat Input Bar -->
        <div class="p-3 bg-slate-900 border-t border-slate-800 shrink-0">
          <form onsubmit="handleChatSubmit(event)" class="flex items-center space-x-2">
            <input 
              type="text" 
              id="chatInput" 
              placeholder="Type your message or request..." 
              class="flex-1 bg-slate-950 border border-slate-700 focus:border-indigo-500 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none shadow-inner"
            />
            <button 
              type="submit" 
              class="bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white px-4 py-2.5 rounded-xl text-xs font-semibold shadow-md transition flex items-center space-x-1.5"
            >
              <span>Send</span>
              <i class="fa-solid fa-paper-plane text-[10px]"></i>
            </button>
          </form>
        </div>
      </section>

      <!-- 3. RIGHT COLUMN: Direct Skill Triggers & AG-UI Event Stream (4 Cols) -->
      <section class="col-span-4 bg-slate-900 flex flex-col overflow-hidden">
        <!-- Direct Skill Triggers Header -->
        <div class="px-4 py-3 border-b border-slate-800 flex items-center justify-between shrink-0 bg-slate-900">
          <div class="flex items-center space-x-2">
            <i class="fa-solid fa-bolt text-amber-400 text-xs"></i>
            <h2 class="font-semibold text-xs text-slate-200 uppercase tracking-wider">Direct Skill Triggers</h2>
          </div>
          <span class="text-[10px] text-slate-500 font-mono">Compare Direct vs Chat</span>
        </div>

        <!-- Direct Trigger Buttons -->
        <div class="p-3 border-b border-slate-800 bg-slate-950/40 grid grid-cols-3 gap-2">
          <button onclick="sendQuickPrompt('Show me customer 101')" class="p-2.5 bg-slate-800 hover:bg-slate-700/80 border border-slate-700 rounded-lg text-left transition">
            <div class="text-indigo-400 text-[11px] font-bold"><i class="fa-solid fa-user-check mr-1"></i> Cust 360</div>
            <p class="text-[10px] text-slate-400">cust_101</p>
          </button>
          <button onclick="sendQuickPrompt('Follow up on overdue payments')" class="p-2.5 bg-slate-800 hover:bg-slate-700/80 border border-slate-700 rounded-lg text-left transition">
            <div class="text-amber-400 text-[11px] font-bold"><i class="fa-solid fa-receipt mr-1"></i> Follow-up</div>
            <p class="text-[10px] text-slate-400">HITL Action</p>
          </button>
          <button onclick="sendQuickPrompt('Give me my daily operational briefing')" class="p-2.5 bg-slate-800 hover:bg-slate-700/80 border border-slate-700 rounded-lg text-left transition">
            <div class="text-emerald-400 text-[11px] font-bold"><i class="fa-solid fa-chart-line mr-1"></i> Briefing</div>
            <p class="text-[10px] text-slate-400">Daily tasks</p>
          </button>
        </div>

        <!-- AG-UI Event Stream Header -->
        <div class="px-4 py-2.5 border-b border-slate-800 flex items-center justify-between shrink-0 bg-slate-950">
          <div class="flex items-center space-x-2">
            <i class="fa-solid fa-satellite-dish text-indigo-400 text-xs"></i>
            <h2 class="font-semibold text-xs text-slate-300 uppercase tracking-wider">AG-UI Event Inspector</h2>
          </div>
          <span class="text-[10px] text-emerald-400 font-mono flex items-center">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1"></span> SSE Active
          </span>
        </div>

        <!-- AG-UI Stream Output -->
        <div class="flex-1 overflow-y-auto p-3 font-mono text-[11px] space-y-2 bg-slate-950 custom-scrollbar" id="eventStream">
          <div class="text-slate-600 text-xs italic">[Awaiting protocol events...]</div>
        </div>

        <!-- Audit Bar -->
        <div class="p-2.5 border-t border-slate-800 bg-slate-900 flex items-center justify-between text-[11px] text-slate-400 shrink-0">
          <span>Audit Log Records:</span>
          <span id="auditCount" class="font-bold text-indigo-400 font-mono">0</span>
        </div>
      </section>

    </div>
  </div>

  <script>
    let currentRole = "finance_assistant";

    function updateRole() {
      currentRole = document.getElementById("roleSelect").value;
      logEvent("ROLE_CHANGED", { role: currentRole });
      addChatMessage("assistant", `Switched active role to <strong>${currentRole}</strong>. Permissions and security policies have been dynamically updated.`);
    }

    async function refreshState() {
      try {
        const res = await fetch("/api/state");
        const data = await res.json();
        renderState(data);
      } catch (e) {
        console.error("Failed to load state", e);
      }
    }

    function renderState(data) {
      // Customers
      const custDiv = document.getElementById("customersList");
      custDiv.innerHTML = Object.values(data.customers).map(c => `
        <div class="p-2.5 bg-slate-950/90 rounded-lg border border-slate-800 text-xs shadow-sm hover:border-slate-700 transition">
          <div class="flex justify-between items-center mb-0.5">
            <span class="font-bold text-slate-100">${c.name}</span>
            <span class="text-[9px] font-bold px-1.5 py-0.2 rounded bg-indigo-950 text-indigo-300 border border-indigo-800 uppercase">${c.tier || 'standard'}</span>
          </div>
          <div class="text-slate-400 text-[11px]">${c.email}</div>
          <div class="text-slate-300 text-[11px] mt-1 flex justify-between">
            <span>ID: <strong class="text-slate-400 font-mono">${c.id}</strong></span>
            <span>Balance: <strong class="text-emerald-400 font-mono">$${c.balance.toFixed(2)}</strong></span>
          </div>
        </div>
      `).join("");
      document.getElementById("custCount").innerText = Object.keys(data.customers).length + " records";

      // Invoices
      const invDiv = document.getElementById("invoicesList");
      invDiv.innerHTML = Object.values(data.invoices).map(i => `
        <div class="p-2.5 bg-slate-950/90 rounded-lg border border-slate-800 text-xs shadow-sm hover:border-slate-700 transition flex justify-between items-center">
          <div>
            <div class="font-bold text-slate-200 font-mono">${i.id} <span class="text-slate-500 font-normal">(${i.customer_id})</span></div>
            <div class="text-slate-300 font-bold font-mono text-[11px] mt-0.5">$${i.amount.toFixed(2)}</div>
          </div>
          <span class="text-[9px] uppercase font-bold px-2 py-0.5 rounded ${i.status === 'paid' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-red-950 text-red-400 border border-red-800'}">
            ${i.status}
          </span>
        </div>
      `).join("");
      document.getElementById("invCount").innerText = Object.keys(data.invoices).length + " records";

      // Tasks
      const taskDiv = document.getElementById("tasksList");
      const tasks = Object.values(data.tasks);
      taskDiv.innerHTML = tasks.length === 0 ? '<div class="text-slate-600 text-xs italic">No active tasks</div>' : tasks.map(t => `
        <div class="p-2.5 bg-slate-950/90 rounded-lg border border-slate-800 text-xs shadow-sm">
          <div class="font-medium text-slate-200">${t.title}</div>
          <div class="text-[10px] text-slate-400 mt-1 flex justify-between">
            <span>Status: <strong class="text-slate-300 font-mono">${t.status}</strong></span>
            <span>Priority: <strong class="text-amber-400 uppercase font-mono">${t.priority}</strong></span>
          </div>
        </div>
      `).join("");
      document.getElementById("taskCount").innerText = tasks.length + " records";

      document.getElementById("auditCount").innerText = data.audit_count || 0;
    }

    function logEvent(type, payload) {
      const container = document.getElementById("eventStream");
      const el = document.createElement("div");
      el.className = "p-2 bg-slate-900/90 rounded-lg border border-slate-800/90 shadow-sm";
      const ts = new Date().toLocaleTimeString();
      el.innerHTML = `
        <div class="flex justify-between items-center mb-1">
          <span class="text-indigo-400 font-bold text-[10px] tracking-wide"><i class="fa-solid fa-code mr-1 text-[8px]"></i>${type}</span>
          <span class="text-[9px] text-slate-500 font-mono">${ts}</span>
        </div>
        <pre class="text-[10px] text-slate-300 overflow-x-auto leading-tight custom-scrollbar">${JSON.stringify(payload, null, 2)}</pre>
      `;
      container.prepend(el);
    }

    function addChatMessage(role, content, isHtml = false) {
      const chatContainer = document.getElementById("chatContainer");
      const msgDiv = document.createElement("div");
      msgDiv.className = role === "user" ? "flex items-start justify-end space-x-2" : "flex items-start space-x-3";

      if (role === "user") {
        msgDiv.innerHTML = `
          <div class="bg-indigo-600 text-white rounded-2xl rounded-tr-none px-4 py-2.5 max-w-[85%] text-xs shadow-md">
            ${content}
          </div>
          <div class="w-7 h-7 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 text-xs text-slate-300">
            <i class="fa-solid fa-user"></i>
          </div>
        `;
      } else {
        msgDiv.innerHTML = `
          <div class="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0 text-xs text-white shadow">
            <i class="fa-solid fa-robot"></i>
          </div>
          <div class="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-none p-3.5 max-w-[90%] text-xs text-slate-200 shadow-sm space-y-2">
            ${isHtml ? content : `<p>${content}</p>`}
          </div>
        `;
      }

      chatContainer.appendChild(msgDiv);
      chatContainer.scrollTop = chatContainer.scrollHeight;
      return msgDiv;
    }

    function clearChat() {
      const chatContainer = document.getElementById("chatContainer");
      chatContainer.innerHTML = "";
      addChatMessage("assistant", "Chat history cleared. How can I help you?");
    }

    function sendQuickPrompt(promptText) {
      document.getElementById("chatInput").value = promptText;
      handleChatSubmit(new Event('submit'));
    }

    async function handleChatSubmit(e) {
      e.preventDefault();
      const input = document.getElementById("chatInput");
      const text = input.value.trim();
      if (!text) return;

      input.value = "";
      addChatMessage("user", text);

      // Log AG-UI RUN_STARTED
      logEvent("RUN_STARTED", { query: text, role: currentRole, protocol: "AG-UI" });

      // Add typing placeholder
      const loadingMsg = addChatMessage("assistant", '<i class="fa-solid fa-spinner fa-spin mr-2 text-indigo-400"></i> Reasoning with Alamia Core...', true);

      try {
        const res = await fetch("/api/copilot/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: text, role: currentRole })
        });
        const data = await res.json();
        loadingMsg.remove();

        // Log AG-UI RUN_FINISHED
        logEvent("RUN_FINISHED", data);

        // Render rich CopilotKit assistant response with Generative UI
        renderCopilotResponse(data);
        refreshState();
      } catch (err) {
        loadingMsg.remove();
        addChatMessage("assistant", `<span class="text-red-400"><i class="fa-solid fa-triangle-exclamation mr-1"></i> Error: ${err.message}</span>`, true);
      }
    }

    function renderCopilotResponse(data) {
      let htmlContent = `<div>${data.message || ''}</div>`;

      // 1. Render Generative Customer 360 Widget if output contains customer profile
      if (data.skill_id === "customer_360" && data.output && data.output.customer) {
        const c = data.output.customer;
        const invs = data.output.invoices || [];
        const overdueSum = invs.filter(i => i.status === 'overdue').reduce((s, i) => s + i.amount, 0);

        htmlContent += `
          <div class="mt-2.5 p-3.5 bg-slate-950 rounded-xl border border-slate-700/80 shadow-md">
            <div class="flex justify-between items-center pb-2 border-b border-slate-800">
              <div>
                <span class="font-bold text-white text-xs">${c.name}</span>
                <span class="text-[10px] text-slate-400 ml-1 font-mono">(${c.id})</span>
              </div>
              <span class="text-[9px] font-bold uppercase px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-700">${c.tier || 'Standard'}</span>
            </div>
            <div class="grid grid-cols-3 gap-2 py-2 text-center text-[10px]">
              <div class="bg-slate-900 p-1.5 rounded">
                <div class="text-slate-400">Total Invoices</div>
                <div class="font-bold text-white font-mono">${invs.length}</div>
              </div>
              <div class="bg-slate-900 p-1.5 rounded">
                <div class="text-slate-400">Overdue Total</div>
                <div class="font-bold text-red-400 font-mono">$${overdueSum.toFixed(2)}</div>
              </div>
              <div class="bg-slate-900 p-1.5 rounded">
                <div class="text-slate-400">Balance</div>
                <div class="font-bold text-emerald-400 font-mono">$${c.balance.toFixed(2)}</div>
              </div>
            </div>
          </div>
        `;
      }

      // 2. Render Overdue Invoices summary list
      if (data.skill_id === "invoice_query" && data.output && data.output.overdue_invoices) {
        const invList = data.output.overdue_invoices.map(i => `
          <div class="flex justify-between items-center py-1 border-b border-slate-800/60 last:border-0 font-mono text-[10px]">
            <span class="text-slate-300">${i.id} (${i.customer_id})</span>
            <span class="text-red-400 font-bold">$${i.amount.toFixed(2)}</span>
          </div>
        `).join("");

        htmlContent += `
          <div class="mt-2.5 p-3 bg-slate-950 rounded-xl border border-slate-700/80 shadow-md">
            <div class="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5 flex justify-between">
              <span>Overdue Invoices List</span>
              <span class="text-red-400">$${data.output.total_overdue.toFixed(2)} total</span>
            </div>
            ${invList}
          </div>
        `;
      }

      // 3. Render Human-in-the-Loop (HITL) Action Confirmation Modal if action proposed
      if (data.proposed_actions && data.proposed_actions.length > 0) {
        const actionsHtml = data.proposed_actions.map(act => `
          <div class="p-3.5 bg-amber-950/50 border-2 border-amber-500/60 rounded-xl space-y-2 mt-2.5 shadow-lg">
            <div class="flex justify-between items-center">
              <span class="text-[10px] font-bold uppercase text-amber-300 flex items-center">
                <i class="fa-solid fa-hand text-amber-400 mr-1.5 animate-bounce"></i> Human Confirmation Required
              </span>
              <span class="text-[9px] font-bold px-2 py-0.5 rounded bg-amber-900/80 text-amber-200 border border-amber-600 uppercase font-mono">
                ${act.risk_level} RISK
              </span>
            </div>
            <div class="text-slate-100 font-semibold text-xs">Action: <code class="text-amber-200 font-mono">${act.action_type}</code></div>
            <div class="text-slate-300 text-[11px]">${act.reason}</div>
            <div class="flex justify-end space-x-2 pt-2 border-t border-amber-900/60">
              <button onclick="resolveAction('${act.action_id}', 'reject', this)" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded-lg text-slate-300 font-semibold transition text-xs">
                Reject
              </button>
              <button onclick="resolveAction('${act.action_id}', 'confirm', this)" class="px-3.5 py-1 bg-amber-600 hover:bg-amber-500 rounded-lg text-white font-bold transition shadow-md text-xs flex items-center space-x-1">
                <i class="fa-solid fa-check text-[10px]"></i>
                <span>Confirm & Execute</span>
              </button>
            </div>
          </div>
        `).join("");

        htmlContent += actionsHtml;
      }

      // 4. Handle Security Rejection / Entity Not Found Notice
      if (!data.success && data.error) {
        const isSecurity = data.error.toLowerCase().includes("unauthorized") || data.error.toLowerCase().includes("not authorized") || data.error.toLowerCase().includes("permission");
        htmlContent = `
          <div class="p-3 ${isSecurity ? 'bg-red-950/60 border border-red-800/80' : 'bg-amber-950/60 border border-amber-800/80'} rounded-xl text-xs space-y-1">
            <div class="${isSecurity ? 'text-red-400' : 'text-amber-400'} font-bold flex items-center">
              <i class="fa-solid ${isSecurity ? 'fa-shield-halved' : 'fa-circle-exclamation'} mr-1.5"></i> ${isSecurity ? 'Security Policy Rejection' : 'Notice / Entity Not Found'}
            </div>
            <div class="text-slate-300">${data.error}</div>
          </div>
        `;
      }

      addChatMessage("assistant", htmlContent, true);
    }

    async function resolveAction(actionId, decision, btn) {
      const container = btn.closest(".bg-amber-950\\/50");
      container.innerHTML = `<div class="text-xs text-slate-400 italic py-1"><i class="fa-solid fa-spinner fa-spin mr-1.5"></i> Authoritatively executing ${decision}...</div>`;

      try {
        const res = await fetch(`/api/action/${decision}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action_id: actionId, role: currentRole })
        });
        const data = await res.json();
        
        container.className = decision === 'confirm' ? "p-3 bg-emerald-950/60 border border-emerald-800 rounded-xl text-xs" : "p-3 bg-slate-900 border border-slate-700 rounded-xl text-xs";
        container.innerHTML = decision === 'confirm' 
          ? `<div class="text-emerald-400 font-bold flex items-center"><i class="fa-solid fa-circle-check mr-1.5 text-base"></i> Action <code>${actionId}</code> Confirmed & Executed!</div><div class="text-slate-300 text-[11px] mt-1">Host application state updated successfully.</div>`
          : `<div class="text-slate-400 font-semibold"><i class="fa-solid fa-ban mr-1.5"></i> Action <code>${actionId}</code> Rejected by operator.</div>`;

        logEvent(decision === 'confirm' ? "ACTION_CONFIRMED_AND_EXECUTED" : "ACTION_REJECTED", data);
        refreshState();
      } catch (e) {
        container.innerHTML = `<span class="text-red-400 font-bold">Failed: ${e.message}</span>`;
      }
    }

    // Initial load
    refreshState();
  </script>
</body>
</html>
"""


class ReferenceAppHTTPHandler(BaseHTTPRequestHandler):
    """HTTP Request handler serving UI, CopilotKit chat, and AG-UI endpoints."""

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Accept, X-Requested-With")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Accept, X-Requested-With")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            html_bytes = HTML_DASHBOARD.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)
            return

        elif parsed.path in ("/api/state", "/api/dashboard"):
            state = {
                "customers": ADAPTER.customers,
                "invoices": ADAPTER.invoices,
                "tasks": ADAPTER.tasks,
                "audit_count": len(ADAPTER.audit_log),
            }
            self._send_json(state)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = json.loads(body) if body else {}

        # 1. Natural Language Conversational Copilot Chat Endpoint
        if parsed.path == "/api/copilot/chat":
            query = data.get("query", "") or data.get("message", "")
            role = data.get("role", "finance_assistant")
            res = process_natural_language_query(query, role)
            self._send_json(res)
            return

        # 2. AG-UI Server-Sent Events (SSE) Streaming Endpoint
        elif parsed.path == "/api/ag-ui":
            skill_id = data.get("skill_id", "")
            role = data.get("role", "finance_assistant")
            inputs = data.get("inputs", {})
            run_id = data.get("run_id", "run_ag_ui_1")

            role_perms = {
                "finance_assistant": ["customers.read", "invoices.read", "tasks.read", "tasks.create", "financial.write"],
                "executive_assistant": ["tasks.read"],
                "read_only_viewer": ["customers.read"],
            }
            context = EmployeeContext(
                user_id=f"user_{role}",
                role=role,
                permissions=role_perms.get(role, ["customers.read"]),
            )

            # Ensure payment_followup triggers interrupt for testing HITL flow
            if skill_id == "payment_followup":
                ENGINE.policies.confirmation_policy.always_require_confirmation_actions.add("create_followup")

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            try:
                for chunk in AG_UI_HANDLER.handle_agent_turn(skill_id=skill_id, context=context, inputs=inputs, run_id=run_id):
                    self.wfile.write(chunk.encode("utf-8"))
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        # 3. Direct Skill Execution Endpoint
        elif parsed.path == "/api/skill":
            skill_id = data.get("skill_id", "")
            role = data.get("role", "finance_assistant")
            inputs = data.get("inputs", {})

            role_perms = {
                "finance_assistant": ["customers.read", "invoices.read", "tasks.read", "tasks.create", "financial.write"],
                "executive_assistant": ["tasks.read"],
                "read_only_viewer": ["customers.read"],
            }
            context = EmployeeContext(
                user_id=f"user_{role}",
                role=role,
                permissions=role_perms.get(role, ["customers.read"]),
            )

            result = ENGINE.execute_skill(skill_id, context, **inputs)

            for prop in result.proposed_actions:
                prop_id = prop.get("action_id")
                if prop_id:
                    PENDING_ACTIONS[prop_id] = (ActionProposal.model_validate(prop), context)

            self._send_json(result.model_dump())
            return

        # 4. Action Confirmation (HITL Approval)
        elif parsed.path == "/api/action/confirm":
            action_id = data.get("action_id")
            if action_id in PENDING_ACTIONS:
                proposal, context = PENDING_ACTIONS.pop(action_id)
                ActionStateMachine.transition(proposal, ActionStatus.CONFIRMED)
                executed = ENGINE.execute_action(proposal, context)
                self._send_json({"status": "SUCCESS", "action": executed.model_dump()})
                return
            elif action_id in AG_UI_HANDLER._pending_interrupts:
                executed = AG_UI_HANDLER.resolve_interrupt(action_id, "Approve")
                self._send_json({"status": "SUCCESS", "action": executed.model_dump() if executed else None})
                return
            self._send_json({"error": "Action not found or already executed"}, status=404)
            return

        # 5. Action Rejection (HITL Rejection)
        elif parsed.path == "/api/action/reject":
            action_id = data.get("action_id")
            if action_id in PENDING_ACTIONS:
                proposal, _ = PENDING_ACTIONS.pop(action_id)
                ActionStateMachine.transition(proposal, ActionStatus.REJECTED)
                self._send_json({"status": "REJECTED", "action_id": action_id})
                return
            elif action_id in AG_UI_HANDLER._pending_interrupts:
                executed = AG_UI_HANDLER.resolve_interrupt(action_id, "Reject")
                self._send_json({"status": "REJECTED", "action": executed.model_dump() if executed else None})
                return
            self._send_json({"error": "Action not found"}, status=404)
            return

        self.send_response(404)
        self.end_headers()


def run_server(port: int = 8000) -> None:
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, ReferenceAppHTTPHandler)
    print("=" * 70)
    print(f"Alamia AI Copilot Interactive Web Server running at:")
    print(f"--> http://localhost:{port}")
    print("=" * 70)
    print("Press Ctrl+C to stop the server.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
        httpd.server_close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    run_server(port)
