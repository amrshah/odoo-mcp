"""Architectural Negative Tests.

Static analysis and negative unit tests proving that architectural boundaries cannot be violated:
- Core contains zero imports of application frameworks (Odoo, Laravel, FastAPI, Django, Flask, SQLAlchemy, CopilotKit).
- Skills do not import application ORMs or adapters.
- LLM cannot override backend confirmation requirements or forge permissions.
"""

import ast
import os
from pathlib import Path
from typing import List, Tuple
import pytest
from core.actions.proposal import ActionProposal, ActionStatus
from core.policies.engine import PolicyEngine
from core.sessions.context import EmployeeContext

FORBIDDEN_CORE_IMPORTS = {
    "odoo",
    "laravel",
    "fastapi",
    "django",
    "flask",
    "sqlalchemy",
    "tortoise",
    "peewee",
    "prisma",
    "copilotkit",
    "langchain",
    "openai",
    "anthropic",
    "google.generativeai",
}


def find_all_imports_in_directory(directory_path: Path) -> List[tuple[str, str]]:
    """Parse all Python files in directory and extract imported module names."""
    imported_modules: List[tuple[str, str]] = []
    
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read(), filename=str(file_path))
                    except Exception as e:
                        pytest.fail(f"Failed to parse AST for {file_path}: {e}")

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imported_modules.append((alias.name, str(file_path)))
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imported_modules.append((node.module, str(file_path)))

    return imported_modules


def test_core_has_zero_forbidden_framework_imports():
    """Verify core/ package never imports external application frameworks or specific LLMs."""
    project_root = Path(__file__).parent.parent
    core_path = project_root / "core"
    assert core_path.exists(), "core/ directory must exist"

    imports = find_all_imports_in_directory(core_path)

    for mod_name, file_path in imports:
        top_level_mod = mod_name.split(".")[0].lower()
        assert (
            top_level_mod not in FORBIDDEN_CORE_IMPORTS
        ), f"Architectural violation: Forbidden import '{mod_name}' detected in {file_path}."


def test_skills_have_zero_forbidden_imports():
    """Verify skills/ package does not directly import application ORMs or specific adapters."""
    project_root = Path(__file__).parent.parent
    skills_path = project_root / "skills"
    assert skills_path.exists(), "skills/ directory must exist"

    imports = find_all_imports_in_directory(skills_path)

    for mod_name, file_path in imports:
        top_level_mod = mod_name.split(".")[0].lower()
        assert (
            top_level_mod not in FORBIDDEN_CORE_IMPORTS
        ), f"Architectural violation: Forbidden import '{mod_name}' detected in skill file {file_path}."


def test_llm_cannot_disable_confirmation_on_high_risk_actions():
    """Verify backend PolicyEngine forces requires_confirmation=True even if LLM proposals set it to False."""
    policy_engine = PolicyEngine()
    context = EmployeeContext(
        user_id="usr_1",
        role="finance_assistant",
        permissions=["financial.write"],
    )

    # Malicious proposal attempting to sneak a high-risk deletion past confirmation
    malicious_proposal = ActionProposal(
        action_id="act_sneak_1",
        action_type="delete",
        idempotency_key="sneak_key_1",
        target={"type": "invoice", "id": "inv_99"},
        reason="LLM claims confirmation is bypassed",
        risk_level="LOW",  # Lie by LLM
        requires_confirmation=False,  # LLM explicitly set false
        required_permission="financial.write",
        created_by="usr_1",
    )

    evaluated = policy_engine.evaluate_proposal(context, malicious_proposal)

    # Backend authority must override
    assert evaluated.risk_level in ("HIGH", "CRITICAL")
    assert evaluated.requires_confirmation is True
    assert evaluated.status == ActionStatus.AWAITING_CONFIRMATION


def test_llm_cannot_forge_permissions():
    """Verify backend PolicyEngine rejects actions when context lacks permission, ignoring LLM claims."""
    policy_engine = PolicyEngine()
    unprivileged_context = EmployeeContext(
        user_id="usr_unprivileged",
        role="viewer",
        permissions=["read_only"],
    )

    forged_proposal = ActionProposal(
        action_id="act_forge_1",
        action_type="mark_paid",
        idempotency_key="forge_key_1",
        target={"type": "invoice", "id": "inv_123"},
        reason="Claiming authorized execution",
        required_permission="financial.write",
        created_by="usr_unprivileged",
    )

    evaluated = policy_engine.evaluate_proposal(unprivileged_context, forged_proposal)

    assert evaluated.status == ActionStatus.REJECTED
    assert "Unauthorized" in evaluated.error
