/** @odoo-module **/

import { Component, useState, useRef, onPatched, onMounted, markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ActionCard } from "../action_card/action_card";

export function formatMarkdown(text) {
    if (!text) return "";

    const lines = text.split('\n');
    let inList = false;
    const output = [];

    for (let rawLine of lines) {
        let line = rawLine
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        const trimmed = line.trim();

        // Headings
        if (trimmed.startsWith('### ')) {
            if (inList) { output.push('</ul>'); inList = false; }
            output.push(`<div class="o_zelix_heading fw-bold text-dark fs-6 mt-2 mb-1 border-bottom pb-1">${trimmed.slice(4)}</div>`);
            continue;
        }
        if (trimmed.startsWith('## ')) {
            if (inList) { output.push('</ul>'); inList = false; }
            output.push(`<div class="o_zelix_heading fw-bold text-dark fs-6 mt-2 mb-1 border-bottom pb-1">${trimmed.slice(3)}</div>`);
            continue;
        }

        // Inline formatting
        line = line.replace(/\*\*(.*?)\*\*/g, '<strong class="fw-bold text-dark">$1</strong>');
        line = line.replace(/\*(.*?)\*/g, '<em class="text-secondary">$1</em>');
        line = line.replace(/`([^`]+)`/g, '<code class="bg-light text-primary px-1 py-0.5 rounded border border-light font-monospace small">$1</code>');

        const trimmedFormatted = line.trim();

        if (trimmedFormatted.startsWith('- ') || trimmedFormatted.startsWith('• ') || trimmedFormatted.startsWith('* ')) {
            const content = trimmedFormatted.replace(/^(?:- |• |\* )/, '');
            if (!inList) {
                output.push('<ul class="o_zelix_list mb-2 ps-3">');
                inList = true;
            }
            if (rawLine.startsWith('  ') || rawLine.startsWith('\t')) {
                output.push(`<li class="o_zelix_subitem ms-3 text-secondary">${content}</li>`);
            } else {
                output.push(`<li class="mb-1">${content}</li>`);
            }
        } else {
            if (inList) {
                output.push('</ul>');
                inList = false;
            }
            if (trimmedFormatted) {
                output.push(`<p class="mb-1">${trimmedFormatted}</p>`);
            }
        }
    }
    if (inList) {
        output.push('</ul>');
    }

    return output.join('');
}

export class CopilotSidebar extends Component {
    static template = "zelix_ai.CopilotSidebar";
    static components = { ActionCard };
    static props = {};

    setup() {
        this.copilot = useService("zelix_copilot");
        this.copilotState = useState(this.copilot.state);
        this.state = useState({
            inputValue: "",
        });
        this.chatEndRef = useRef("chatEnd");

        onMounted(() => {
            this.scrollToBottom();
        });

        onPatched(() => {
            this.scrollToBottom();
        });
    }

    renderFormatted(text) {
        return markup(formatMarkdown(text));
    }

    scrollToBottom() {
        if (this.chatEndRef.el) {
            this.chatEndRef.el.scrollIntoView({ behavior: "smooth" });
        }
    }

    onClose() {
        this.copilot.closeSidebar();
    }

    async onSend() {
        if (!this.state.inputValue || !this.state.inputValue.trim()) return;
        const msg = this.state.inputValue;
        this.state.inputValue = "";
        await this.copilot.sendMessage(msg);
    }

    onKeyDown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.onSend();
        }
    }

    onActionChipClick(prompt) {
        this.copilot.sendMessage(prompt);
    }
}
