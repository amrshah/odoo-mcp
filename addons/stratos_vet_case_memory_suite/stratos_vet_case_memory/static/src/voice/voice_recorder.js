/** @odoo-module **/
import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { _t } from "@web/core/l10n/translation";

const LANGS = [
    ["en-US", "English"],
    ["en-GB", "English (UK)"],
    ["ur-PK", "اردو Urdu"],
];

/**
 * Browser speech recognition. The transcript is saved as a voice note in the
 * case history; symptoms / vitals heard are only applied when the vet confirms.
 * Works on any model that exposes add_voice_note(transcript, lang, duration).
 */
export class VetVoiceRecorder extends Component {
    static template = "stratos_vet_case_memory.VetVoiceRecorder";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.langs = LANGS;
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.supported = Boolean(SR);
        this.SR = SR;
        this.state = useState({
            recording: false,
            saving: false,
            finalText: "",
            interim: "",
            lang: "en-US",
            seconds: 0,
        });
        onWillStart(async () => {
            try {
                const cfg = await this.orm.call("vet.cm.case", "get_voice_config", []);
                this.state.lang = cfg.lang || "en-US";
            } catch {
                // keep default
            }
        });
        onWillUnmount(() => this.stopEngine());
    }

    get text() {
        return (this.state.finalText + " " + this.state.interim).trim();
    }

    start() {
        if (!this.supported || this.state.recording) {
            return;
        }
        this.state.finalText = "";
        this.state.interim = "";
        this.state.seconds = 0;
        this.state.recording = true;
        this.started = Date.now();
        this.timer = setInterval(() => {
            this.state.seconds = Math.round((Date.now() - this.started) / 1000);
        }, 500);
        this.startEngine();
    }

    startEngine() {
        const rec = new this.SR();
        rec.lang = this.state.lang;
        rec.continuous = true;
        rec.interimResults = true;
        rec.onresult = (ev) => {
            let interim = "";
            for (let i = ev.resultIndex; i < ev.results.length; i++) {
                const res = ev.results[i];
                if (res.isFinal) {
                    this.state.finalText += (this.state.finalText ? " " : "") + res[0].transcript.trim();
                } else {
                    interim += res[0].transcript;
                }
            }
            this.state.interim = interim;
        };
        rec.onerror = (ev) => {
            if (ev.error === "not-allowed" || ev.error === "service-not-allowed") {
                this.notification.add(_t("Microphone access was blocked. Allow it in the browser."), {
                    type: "danger",
                });
                this.cancel();
            }
        };
        rec.onend = () => {
            // Chrome stops after silence: keep listening until the vet presses Stop.
            if (this.state.recording) {
                try {
                    rec.start();
                } catch {
                    // already started
                }
            }
        };
        this.recognition = rec;
        rec.start();
    }

    stopEngine() {
        clearInterval(this.timer);
        if (this.recognition) {
            this.recognition.onend = null;
            try {
                this.recognition.stop();
            } catch {
                // ignore
            }
            this.recognition = null;
        }
    }

    cancel() {
        this.state.recording = false;
        this.stopEngine();
        this.state.finalText = "";
        this.state.interim = "";
    }

    async stopAndSave() {
        this.state.recording = false;
        this.stopEngine();
        const text = this.text;
        this.state.interim = "";
        if (!text) {
            this.notification.add(_t("Nothing was heard. Try again closer to the microphone."), {
                type: "warning",
            });
            return;
        }
        await this.save(text);
    }

    async save(text) {
        const record = this.props.record;
        this.state.saving = true;
        try {
            if (record.isNew || record.dirty) {
                const ok = await record.save();
                if (!ok) {
                    return;
                }
            }
            await this.orm.call(record.resModel, "add_voice_note", [
                [record.resId],
                text,
                this.state.lang,
                this.state.seconds,
            ]);
            await record.load();
            record.model.notify();
            this.state.finalText = "";
            this.notification.add(
                _t("Voice note saved to the case history. Review and apply it from Voice History."),
                { type: "success" }
            );
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("view_widgets").add("vet_voice_recorder", { component: VetVoiceRecorder });
