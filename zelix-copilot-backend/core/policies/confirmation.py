"""
core/policies/confirmation.py
Confirmation Policy enforcing mandatory human review gates.
"""

from typing import Set


class ConfirmationPolicy:
    """Defines actions that strictly require human confirmation before execution."""

    def __init__(self) -> None:
        self.always_require_confirmation_actions: Set[str] = {
            "create_soap_encounter",
            "create_prescription",
            "write_prescription",
            "create_patient",
            "cancel_appointment",
        }

    def requires_confirmation(self, action_type: str) -> bool:
        return action_type in self.always_require_confirmation_actions
