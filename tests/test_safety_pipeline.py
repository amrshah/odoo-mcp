"""
Unit & Regression Test Suite for Zelix AI Safety Pipeline
Tests intent routing, schema parsing, clinical contradiction detection, and read-back validation.
"""

import sys
import os
import unittest

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "zelix-copilot-backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp-server"))

from router.intent_router import IntentRouter, TargetWorkflow
from schemas.clinical_schemas import PrescriptionProposalSchema
from schemas.parser import SchemaParser
from validators.clinical_validator import ClinicalValidator


class TestIntentRouting(unittest.TestCase):
    """Verifies deterministic intent routing rules."""

    def test_w04_explicit_soap_request(self):
        res = IntentRouter.classify("Generate today's SOAP note for Max")
        self.assertEqual(res.workflow, TargetWorkflow.W04_SCRIBE_SOAP)

    def test_w04_consult_transcript_with_medication_mention(self):
        """Crucial test: Consult dialogue mentioning 'prescribe' MUST route to W04, NOT W09."""
        transcript = (
            "Doctor: Hello Sarah, Max is vomiting yellow bile. "
            "Doctor: Abdomen soft, temp 101.4 F. Looks like gastroenteritis. "
            "Doctor: Let's prescribe Maropitant Cerenia 16mg once daily."
        )
        res = IntentRouter.classify(transcript)
        self.assertEqual(res.workflow, TargetWorkflow.W04_SCRIBE_SOAP)

    def test_w09_explicit_prescription_directive(self):
        res = IntentRouter.classify("Prescribe Amoxicillin-Clavulanate 250mg for Max, 1 tablet twice daily with food for 7 days.")
        self.assertEqual(res.workflow, TargetWorkflow.W09_PRESCRIPTION_ASSISTANT)

    def test_w02_pre_consult_brief(self):
        res = IntentRouter.classify("Prepare me for my next patient Max. What should I focus on?")
        self.assertEqual(res.workflow, TargetWorkflow.W02_PRE_CONSULT_BRIEF)

    def test_w01_patient_summary(self):
        res = IntentRouter.classify("Summarize case history of Max and past encounters.")
        self.assertEqual(res.workflow, TargetWorkflow.W01_PATIENT_SUMMARY)

    def test_ambiguous_intent_returns_clarification(self):
        res = IntentRouter.classify("Hello, how are you?")
        self.assertEqual(res.workflow, TargetWorkflow.ASK_CLARIFICATION)


class TestClinicalValidation(unittest.TestCase):
    """Verifies clinical consistency and contradiction checks."""

    def test_reject_bid_once_daily_contradiction(self):
        proposal = PrescriptionProposalSchema(
            medication_name="Maropitant Cerenia",
            medication_id=4,
            patient_id=3,
            dose="16mg",
            frequency="BID (once daily)",  # CONTRADICTION!
            duration="3 days",
            quantity=3.0,
            instructions="Administer once daily with food.",
            clinical_indication="Vomiting",
        )
        res = ClinicalValidator.validate_prescription(proposal)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("conflicts" in err.lower() for err in res.errors))

    def test_accept_valid_prescription(self):
        proposal = PrescriptionProposalSchema(
            medication_name="Amoxicillin-Clavulanate",
            medication_id=3,
            patient_id=3,
            dose="250mg",
            frequency="BID (Twice Daily)",
            duration="7 days",
            quantity=14.0,
            instructions="Administer 1 tablet twice daily with food.",
            clinical_indication="Bacterial skin infection",
        )
        res = ClinicalValidator.validate_prescription(proposal)
        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.errors), 0)

    def test_reject_missing_dosage(self):
        proposal = PrescriptionProposalSchema(
            medication_name="Amoxicillin",
            medication_id=3,
            patient_id=3,
            dose="",  # Missing dose
            frequency="BID",
            duration="7 days",
            quantity=14.0,
            instructions="Give with food",
            clinical_indication="Infection",
        )
        res = ClinicalValidator.validate_prescription(proposal)
        self.assertFalse(res.is_valid)


class TestSchemaParsing(unittest.TestCase):
    """Verifies parsing of LLM outputs into strict Pydantic schemas."""

    def test_parse_soap_note(self):
        raw = """
        Subjective: Owner reports Max has been vomiting yellow bile for 2 days.
        Objective: Temp 101.4 F, Heart Rate 90 bpm, Abdomen soft and non-painful.
        Assessment: Acute dietary gastroenteritis.
        Plan: Cerenia 16mg SID for 3 days. Follow up in 4 days.
        DIAGNOSIS: Acute dietary gastroenteritis
        MEDICATION: Cerenia 16mg SID
        FOLLOW_UP_DAYS: 4
        """
        soap = SchemaParser.parse_soap_note(raw)
        self.assertIn("vomiting", soap.subjective.lower())
        self.assertIn("101.4", soap.objective)
        self.assertIn("gastroenteritis", soap.assessment.lower())
        self.assertEqual(soap.extracted_entities.follow_up_days, 4)


if __name__ == "__main__":
    unittest.main()
