/** @odoo-module **/
/*
 * Scribe field — "the conversation is the record".
 * A text field with a microphone. Uses the browser's Web Speech API (Chrome / Edge) so no audio
 * leaves the workstation except to the browser vendor's recogniser. Interim words render live;
 * final phrases are appended to the field. Works for any Text/Char field: transcript, HPI, plan,
 * SBAR, nurse notes, operative note.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillUnmount } from "@odoo/owl";

export class ScribeField extends Component {
    static template = "stratos_hms.ScribeField";
    static props = {
        ...standardFieldProps,
        placeholder: { type: String, optional: true },
        lang: { type: String, optional: true },
        rows: { type: Number, optional: true },
    };
    static defaultProps = { rows: 6 };

    setup() {
        this.notification = useService("notification");
        this.state = useState({ listening: false, interim: "", supported: !!this.SpeechRecognition });
        this.recognition = null;
        onWillUnmount(() => this.stop());
    }

    get SpeechRecognition() {
        return window.SpeechRecognition || window.webkitSpeechRecognition || null;
    }

    get value() {
        return this.props.record.data[this.props.name] || "";
    }

    get lang() {
        const rec = this.props.record.data;
        return this.props.lang || rec.transcript_lang || rec.speech_lang || "en-PK";
    }

    get langLabel() {
        return { "ur-PK": "اردو", "en-PK": "EN", "en-US": "EN-US" }[this.lang] || this.lang;
    }

    onInput(ev) {
        this.props.record.update({ [this.props.name]: ev.target.value });
    }

    append(text) {
        if (!text) return;
        const current = this.value;
        const sep = current && !current.endsWith("\n") && !current.endsWith(" ") ? " " : "";
        this.props.record.update({ [this.props.name]: current + sep + text.trim() });
    }

    toggle() {
        if (this.state.listening) {
            this.stop();
        } else {
            this.start();
        }
    }

    start() {
        if (!this.SpeechRecognition) {
            this.notification.add(_t("Speech recognition is not available in this browser. Use Chrome or Edge, or type."), { type: "warning" });
            return;
        }
        if (this.props.readonly) return;
        const rec = new this.SpeechRecognition();
        rec.lang = this.lang;
        rec.continuous = true;
        rec.interimResults = true;
        rec.maxAlternatives = 1;
        rec.onresult = (ev) => {
            let interim = "";
            for (let i = ev.resultIndex; i < ev.results.length; i++) {
                const r = ev.results[i];
                if (r.isFinal) {
                    this.append(r[0].transcript);
                } else {
                    interim += r[0].transcript;
                }
            }
            this.state.interim = interim;
        };
        rec.onerror = (ev) => {
            if (ev.error === "not-allowed") {
                this.notification.add(_t("Microphone access was denied. Allow the microphone for this site and try again."), { type: "danger" });
                this.stop();
            } else if (ev.error !== "no-speech" && ev.error !== "aborted") {
                this.notification.add(_t("Speech recognition error: ") + ev.error, { type: "warning" });
            }
        };
        rec.onend = () => {
            // Chrome stops after silence; keep recording until the user presses stop.
            if (this.state.listening && this.recognition === rec) {
                try {
                    rec.start();
                } catch (e) {
                    this.state.listening = false;
                }
            }
        };
        this.recognition = rec;
        this.state.listening = true;
        this.state.interim = "";
        try {
            rec.start();
        } catch (e) {
            this.state.listening = false;
            this.notification.add(_t("Could not start the microphone."), { type: "danger" });
        }
    }

    stop() {
        this.state.listening = false;
        this.state.interim = "";
        if (this.recognition) {
            const rec = this.recognition;
            this.recognition = null;
            try {
                rec.onend = null;
                rec.stop();
            } catch (e) {
                /* ignore */
            }
        }
    }

    clear() {
        if (this.props.readonly) return;
        this.props.record.update({ [this.props.name]: "" });
    }
}

export const scribeField = {
    component: ScribeField,
    displayName: _t("Scribe (speech to text)"),
    supportedTypes: ["text", "char", "html"],
    supportedOptions: [
        { label: _t("Language"), name: "lang", type: "string" },
        { label: _t("Rows"), name: "rows", type: "number" },
    ],
    extractProps: ({ attrs, options, placeholder }) => ({
        placeholder,
        lang: options.lang,
        rows: options.rows,
    }),
};

registry.category("fields").add("hms_scribe", scribeField);
