/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export const zelixCopilotService = {
    dependencies: ["notification", "action", "orm"],
    start(env, { notification, action, orm }) {
        const state = reactive({
            isOpen: false,
            isLoading: false,
            activeModel: null,
            activeRecordId: null,
            activeContext: {},
            userRole: "practice_manager",
            userRoleTitle: "Practice Administrator",
            userName: "Administrator",
            quickActions: [
                { label: "📊 Clinic Activity", prompt: "Give me an operational summary of today's appointments and clinic activity." },
                { label: "📜 Case Summary", prompt: "Summarize patient history and past encounters." },
                { label: "📋 Pre-Consult Brief", prompt: "Prepare me for my next patient. What should I focus on?" },
                { label: "🩺 Generate SOAP", prompt: "Generate today SOAP note from physical exam and consultation history." },
            ],
            messages: [
                {
                    id: "msg_welcome",
                    sender: "assistant",
                    text: "Hello Administrator! I am your Zelix AI Practice Copilot, powered by local BitNet SLM. How can I assist with clinic operations, case summaries, or appointments today?",
                    actionCards: [],
                    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                },
            ],
        });

        // Initialize user session & dynamic role
        loadSessionInfo();

        async function loadSessionInfo() {
            try {
                const info = await rpc("/zelix_ai/session_info");
                if (info && info.role) {
                    state.userRole = info.role;
                    state.userRoleTitle = info.role_title;
                    state.userName = info.name;
                    state.quickActions = info.quick_actions || state.quickActions;

                    // Update initial greeting with tailored text
                    if (state.messages.length === 1 && state.messages[0].id === "msg_welcome") {
                        state.messages[0].text = info.greeting;
                    }
                }
            } catch (e) {
                console.warn("Could not fetch Zelix AI session info:", e);
            }
        }

        function toggleSidebar() {
            state.isOpen = !state.isOpen;
            if (state.isOpen) {
                refreshContext();
            }
        }

        function openSidebar() {
            state.isOpen = true;
            refreshContext();
        }

        function closeSidebar() {
            state.isOpen = false;
        }

        function refreshContext() {
            const currentController = env.services.action?.currentController;
            if (currentController) {
                state.activeModel = currentController.props?.resModel || null;
                state.activeRecordId = currentController.props?.resId || null;
            }

            state.activeContext = {
                model: state.activeModel,
                record_id: state.activeRecordId,
                role: state.userRole,
            };

            if (state.activeModel === "vet.patient" && state.activeRecordId) {
                state.activeContext.patient_id = state.activeRecordId;
            }
        }

        async function sendMessage(text) {
            if (!text || !text.trim()) return;

            refreshContext();

            const userMsgId = "msg_" + Date.now();
            state.messages.push({
                id: userMsgId,
                sender: "user",
                text: text.trim(),
                actionCards: [],
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            });

            state.isLoading = true;

            try {
                const response = await rpc("/zelix_ai/chat", {
                    message: text.trim(),
                    context: state.activeContext,
                });

                if (response.error) {
                    notification.add(response.message || "Failed to contact Zelix AI backend.", {
                        type: "danger",
                    });
                    state.messages.push({
                        id: "msg_err_" + Date.now(),
                        sender: "assistant",
                        text: `Error: ${response.message || "Could not reach Copilot backend service."}`,
                        actionCards: [],
                        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    });
                } else {
                    state.messages.push({
                        id: "msg_" + (response.request_id || Date.now()),
                        sender: "assistant",
                        text: response.response,
                        workflowId: response.workflow_id,
                        actionCards: response.action_cards || [],
                        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    });
                }
            } catch (err) {
                console.error("Zelix Copilot chat error:", err);
                notification.add("Failed to communicate with AI Copilot service.", { type: "danger" });
            } finally {
                state.isLoading = false;
            }
        }

        async function approveAction(actionId) {
            state.isLoading = true;
            try {
                const result = await rpc("/zelix_ai/action/approve", { action_id: actionId });
                if (result.success) {
                    notification.add(result.message || "Action executed successfully into Odoo!", {
                        type: "success",
                    });
                    for (const msg of state.messages) {
                        for (const card of msg.actionCards) {
                            if (card.action_id === actionId) {
                                card.status = "executed";
                            }
                        }
                    }
                    env.services.action?.reload();
                } else {
                    notification.add(result.error || "Action execution failed.", { type: "danger" });
                }
                return result;
            } catch (err) {
                console.error("Action approval error:", err);
                notification.add("Failed to execute action approval.", { type: "danger" });
            } finally {
                state.isLoading = false;
            }
        }

        async function rejectAction(actionId, reason = "User rejected.") {
            try {
                await rpc("/zelix_ai/action/reject", { action_id: actionId, reason });
                for (const msg of state.messages) {
                    for (const card of msg.actionCards) {
                        if (card.action_id === actionId) {
                            card.status = "rejected";
                        }
                    }
                }
                notification.add("Action proposal dismissed.", { type: "info" });
            } catch (err) {
                console.error("Action reject error:", err);
            }
        }

        return {
            state,
            toggleSidebar,
            openSidebar,
            closeSidebar,
            refreshContext,
            sendMessage,
            approveAction,
            rejectAction,
            loadSessionInfo,
        };
    },
};

registry.category("services").add("zelix_copilot", zelixCopilotService);
