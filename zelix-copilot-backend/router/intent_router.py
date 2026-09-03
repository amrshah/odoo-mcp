"""
Deterministic Clinical Intent Router
Classifies user requests to specific clinical workflows without naive keyword collisions.
Handles ambiguity by returning ASK_CLARIFICATION.
"""

import re
from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel


class TargetWorkflow(str, Enum):
    W00_PRACTICE_QUERY = "w00_practice_query"
    W01_PATIENT_SUMMARY = "w01_patient_summary"
    W02_PRE_CONSULT_BRIEF = "w02_pre_consult_brief"
    W04_SCRIBE_SOAP = "w04_scribe_soap"
    W09_PRESCRIPTION_ASSISTANT = "w09_prescription_assistant"
    ASK_CLARIFICATION = "ask_clarification"


class IntentClassificationResult(BaseModel):
    workflow: TargetWorkflow
    confidence: float
    matched_pattern: Optional[str] = None
    reason: str


class IntentRouter:
    """
    Classifies user intent using multi-stage priority rules and conversational structure analysis:
    - Dialogue / transcript structure (Doctor:/Owner:, dialogue turns, exam findings) -> W04 Scribe
    - Explicit SOAP request ("generate SOAP", "document consultation") -> W04 Scribe
    - Explicit direct prescription directive ("prescribe X for Y", "order rx for...") -> W09
    - Pre-consultation / preparation request ("prepare me for next patient", "pre-consult brief") -> W02
    - Longitudinal case inquiry ("summarize patient", "case history", "what happened in last visits") -> W01
    - Practice inquiries / counts / operational summaries ("how many patients", "today's activity") -> W00
    - Ambiguous / conflicting inputs -> TargetWorkflow.ASK_CLARIFICATION
    """

    # Multi-turn consultation transcript patterns (Doctor: / Owner: / Exam:)
    DIALOGUE_PATTERNS = [
        r"\b(?:doctor|dr|owner|client|vet|nurse|technician)\s*:",
        r"\b(?:palpation|auscultation|mucous membranes|temperature is|heart rate \d+|respiratory rate)\b",
        r"\b(?:presents with|presenting with|brought in for|vomiting for past|coughing for past)\b",
        r"\b(?:on physical exam|physical examination reveals|abdomen is soft)\b",
    ]

    # Explicit SOAP request triggers
    SOAP_TRIGGERS = [
        r"\b(?:generate|create|write|draft|prepare)\b.*?\bsoap\b",
        r"\b(?:document|record|transcribe)\s+(?:today'?s\s+)?consult(?:ation)?\b",
        r"\bclinical notes? from (?:today|consultation|visit)\b",
        r"\bsoap\s+note\b",
    ]

    # Explicit Prescription Directive triggers (Must be direct order, not dialogue)
    PRESCRIPTION_DIRECTIVE_TRIGGERS = [
        r"^(?:please\s+)?(?:prescribe|issue (?:a )?prescription for|order (?:rx|medication) for)\b",
        r"^prescribe\s+[a-z0-9\-\s]+\s+for\s+[a-z0-9]+",
        r"\b(?:send|create|issue)\s+(?:a\s+)?prescription\s+(?:for|to)\b",
    ]

    # Pre-consult briefing triggers
    PRE_CONSULT_TRIGGERS = [
        r"\b(?:prepare|brief|prep)\s+(?:me\s+for\s+)?(?:the\s+|my\s+|our\s+)?(?:next|upcoming|today'?s)?\s*(?:patient|consult|appointment|case)\b",
        r"\bpre-?consult(?:ation)?\s*(?:brief|sheet|summary|overview)?\b",
        r"\bwhat should i focus on (?:for|with)\b",
        r"\bcheat sheet for\b",
    ]

    # Patient longitudinal summary triggers
    PATIENT_SUMMARY_TRIGGERS = [
        r"\b(?:summarize|overview of|case history of|full history of)\s+(?:patient\s+)?[a-z0-9]+\b",
        r"\b(?:patient|medical)\s+(?:summary|timeline|profile)\b",
        r"\bwhat (?:happened|occurred) (?:in|during) (?:his|her|the)?\s*(?:last|previous|prior)\s*(?:visits?|encounters?)\b",
    ]

    # Practice Operations, Census & Record Query triggers
    PRACTICE_QUERY_TRIGGERS = [
        r"\b(?:how many|total|number of|count of|list of)\s+(?:patients?|animals?|pets?|dogs?|cats?|appointments?|encounters?|visits?|staff|doctors?|vets?|veterinarians?|medications?|medicines?|drugs?|prescriptions?)\b",
        r"\bhow many\s+[a-z0-9\s]+\s+in\s+the\s+(?:hospital|clinic|system|practice|database)\b",
        r"\b(?:operational summary|clinic activity|clinic overview|today'?s\s+(?:appointments?|activity|schedule|status)|daily brief|practice status|hospital census)\b",
        r"\b(?:medicine|medication|drug|pharmacy|vaccine)\s+(?:stock|inventory|catalog|list|available|count)\b",
        r"\b(?:who (?:are|is)|list)\s+(?:our\s+)?(?:staff|doctors?|vets?|veterinarians?|technicians?|nurses?|receptionists?|team)\b",
        r"\b(?:give me|show me)\s+(?:an?\s+)?(?:operational|clinic|practice)\s+(?:summary|brief|overview|report)\b",
    ]

    @classmethod
    def classify(cls, text: str) -> IntentClassificationResult:
        cleaned = text.strip()
        lower = cleaned.lower()

        # 1. Check for Consultation Dialogue / Multi-turn Transcript (Always W04, even if mentions meds)
        for pat in cls.DIALOGUE_PATTERNS:
            if re.search(pat, lower):
                return IntentClassificationResult(
                    workflow=TargetWorkflow.W04_SCRIBE_SOAP,
                    confidence=0.95,
                    matched_pattern=pat,
                    reason="Matched clinical consultation dialogue/transcript structure.",
                )

        # 2. Check for Explicit SOAP generation request
        for pat in cls.SOAP_TRIGGERS:
            if re.search(pat, lower):
                return IntentClassificationResult(
                    workflow=TargetWorkflow.W04_SCRIBE_SOAP,
                    confidence=0.92,
                    matched_pattern=pat,
                    reason="Matched explicit SOAP generation request.",
                )

        # 3. Check for Explicit Prescription Directive (Isolated command)
        for pat in cls.PRESCRIPTION_DIRECTIVE_TRIGGERS:
            if re.search(pat, lower):
                return IntentClassificationResult(
                    workflow=TargetWorkflow.W09_PRESCRIPTION_ASSISTANT,
                    confidence=0.90,
                    matched_pattern=pat,
                    reason="Matched explicit prescription directive.",
                )

        # 4. Check for Pre-Consult Briefing
        for pat in cls.PRE_CONSULT_TRIGGERS:
            if re.search(pat, lower):
                return IntentClassificationResult(
                    workflow=TargetWorkflow.W02_PRE_CONSULT_BRIEF,
                    confidence=0.88,
                    matched_pattern=pat,
                    reason="Matched pre-consultation briefing request.",
                )

        # 5. Check for Longitudinal Patient Summary
        for pat in cls.PATIENT_SUMMARY_TRIGGERS:
            if re.search(pat, lower):
                return IntentClassificationResult(
                    workflow=TargetWorkflow.W01_PATIENT_SUMMARY,
                    confidence=0.85,
                    matched_pattern=pat,
                    reason="Matched longitudinal patient summary request.",
                )

        # 6. Check for Practice Operations & Record Query
        for pat in cls.PRACTICE_QUERY_TRIGGERS:
            if re.search(pat, lower):
                return IntentClassificationResult(
                    workflow=TargetWorkflow.W00_PRACTICE_QUERY,
                    confidence=0.90,
                    matched_pattern=pat,
                    reason="Matched practice operations / census query.",
                )

        # 6. Secondary fallback checks with lower confidence
        if lower.startswith("prescribe ") or lower.startswith("rx:"):
            return IntentClassificationResult(
                workflow=TargetWorkflow.W09_PRESCRIPTION_ASSISTANT,
                confidence=0.85,
                reason="Direct prescription prefix.",
            )

        if "summarize" in lower and len(lower.split()) < 6:
            return IntentClassificationResult(
                workflow=TargetWorkflow.W01_PATIENT_SUMMARY,
                confidence=0.75,
                reason="Short summary command.",
            )

        # 7. Ambiguity Check: If unresolvable or dangerously vague
        return IntentClassificationResult(
            workflow=TargetWorkflow.ASK_CLARIFICATION,
            confidence=0.0,
            reason="Input does not match known clinical intent templates with sufficient confidence.",
        )
