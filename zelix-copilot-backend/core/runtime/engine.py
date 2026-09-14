"""Copilot Engine.

Coordinates the AI Employee runtime, dispatching skills, executing tools, evaluating security policies,
and communicating with application adapters without framework coupling.
"""

from typing import Any, Dict, List, Optional
from core.actions.executor import ActionExecutor
from core.actions.proposal import ActionProposal, ActionStatus
from core.audit.entry import AuditEntry
from core.audit.logger import AuditLogger, InMemoryAuditLogger
from core.events.bus import EventBus
from core.memory.interface import InMemoryMemoryStore, MemoryInterface
from core.policies.engine import PolicyEngine
from core.roles.registry import RoleRegistry
from core.runtime.context import RuntimeConfig
from core.runtime.result import ExecutionResult, StepResult
from core.sessions.context import EmployeeContext
from core.skills.registry import SkillRegistry
from core.tools.registry import ToolRegistry


class CopilotEngine:
    """Central runtime engine orchestrating AI Employee interactions."""

    def __init__(
        self,
        config: Optional[RuntimeConfig] = None,
        skill_registry: Optional[SkillRegistry] = None,
        tool_registry: Optional[ToolRegistry] = None,
        role_registry: Optional[RoleRegistry] = None,
        policy_engine: Optional[PolicyEngine] = None,
        action_executor: Optional[ActionExecutor] = None,
        audit_logger: Optional[AuditLogger] = None,
        event_bus: Optional[EventBus] = None,
        memory: Optional[MemoryInterface] = None,
        ai_router: Optional[Any] = None,
        application_adapter: Optional[Any] = None,
    ) -> None:
        self.config = config or RuntimeConfig()
        self.skills = skill_registry or SkillRegistry()
        self.tools = tool_registry or ToolRegistry()
        self.roles = role_registry or RoleRegistry()
        self.policies = policy_engine or PolicyEngine()
        self.actions = action_executor or ActionExecutor()
        self.audit = audit_logger or InMemoryAuditLogger()
        self.events = event_bus or EventBus()
        self.memory = memory or InMemoryMemoryStore()
        self.ai_router = ai_router
        self.adapter = application_adapter

    def set_application_adapter(self, adapter: Any) -> None:
        """Bind an application adapter."""
        self.adapter = adapter

    def execute_skill(
        self,
        skill_id: str,
        context: EmployeeContext,
        **inputs: Any,
    ) -> ExecutionResult:
        """Execute a business skill within the given employee context."""
        skill = self.skills.get(skill_id)
        if not skill:
            err_msg = f"Skill '{skill_id}' not found in registry."
            self.audit.log(
                AuditEntry(
                    audit_id=f"audit_err_{skill_id}",
                    event_type="SKILL_EXECUTION",
                    user_id=context.user_id,
                    role=context.role,
                    skill_id=skill_id,
                    status="FAILURE",
                    details={"error": err_msg},
                )
            )
            return ExecutionResult(success=False, skill_id=skill_id, error=err_msg)

        # 1. Role capability check
        permissible_skills = self.skills.find_for_role(context.role)
        if skill not in permissible_skills:
            err_msg = f"Role '{context.role}' is not authorized to execute skill '{skill_id}'."
            self.audit.log(
                AuditEntry(
                    audit_id=f"audit_unauth_{skill_id}",
                    event_type="SECURITY_DECISION",
                    user_id=context.user_id,
                    role=context.role,
                    skill_id=skill_id,
                    status="REJECTED",
                    details={"reason": err_msg},
                )
            )
            return ExecutionResult(success=False, skill_id=skill_id, error=err_msg)

        # 2. Gather available tools for the skill
        available_tools: Dict[str, Any] = {}
        for tool_name in skill.definition.required_tools:
            tool_obj = self.tools.get(tool_name)
            if tool_obj:
                available_tools[tool_name] = tool_obj

        # 3. Select AI Provider if available
        ai_provider = None
        if self.ai_router:
            provider, _ = self.ai_router.select()
            ai_provider = provider

        # 4. Execute the skill workflow
        try:
            skill_res = skill.execute(
                context=context,
                tools=available_tools,
                ai_provider=ai_provider,
                **inputs,
            )

            # 5. Process any proposed actions through policy engine
            evaluated_proposals: List[Dict[str, Any]] = []
            for raw_proposal in skill_res.proposed_actions:
                if isinstance(raw_proposal, dict):
                    proposal = ActionProposal(**raw_proposal)
                else:
                    proposal = raw_proposal

                # Backend authoritative evaluation
                evaluated = self.policies.evaluate_proposal(context, proposal)
                evaluated_proposals.append(evaluated.model_dump())

            self.audit.log(
                AuditEntry(
                    audit_id=f"audit_exec_{skill_id}",
                    event_type="SKILL_EXECUTION",
                    user_id=context.user_id,
                    role=context.role,
                    skill_id=skill_id,
                    status="SUCCESS" if skill_res.success else "FAILURE",
                    details={"output": skill_res.output, "actions_count": len(evaluated_proposals)},
                )
            )

            return ExecutionResult(
                success=skill_res.success,
                skill_id=skill_id,
                output=skill_res.output,
                proposed_actions=evaluated_proposals,
                error=skill_res.error,
                metadata=skill_res.metadata,
            )
        except Exception as ex:
            self.audit.log(
                AuditEntry(
                    audit_id=f"audit_exc_{skill_id}",
                    event_type="SKILL_EXECUTION",
                    user_id=context.user_id,
                    role=context.role,
                    skill_id=skill_id,
                    status="FAILURE",
                    details={"exception": str(ex)},
                )
            )
            return ExecutionResult(
                success=False,
                skill_id=skill_id,
                error=str(ex),
            )

    def execute_action(
        self,
        proposal: ActionProposal,
        context: EmployeeContext,
    ) -> ActionProposal:
        """Execute a confirmed ActionProposal against the bound application adapter."""
        if not self.adapter:
            raise RuntimeError("No ApplicationAdapter is bound to CopilotEngine.")

        # Authoritative backend policy validation before execution
        evaluated = self.policies.evaluate_proposal(context, proposal)
        if evaluated.status == ActionStatus.REJECTED:
            self.audit.log(
                AuditEntry(
                    audit_id=f"audit_act_unauth_{proposal.action_id}",
                    event_type="ACTION_EXECUTION",
                    user_id=context.user_id,
                    role=context.role,
                    action_id=proposal.action_id,
                    status="REJECTED",
                    details={"error": evaluated.error},
                )
            )
            return evaluated

        # Execute via ActionExecutor
        executed = self.actions.execute(proposal=evaluated, adapter=self.adapter)

        self.audit.log(
            AuditEntry(
                audit_id=f"audit_act_{proposal.action_id}",
                event_type="ACTION_EXECUTION",
                user_id=context.user_id,
                role=context.role,
                action_id=proposal.action_id,
                status=executed.status.value,
                details={"result": executed.result, "error": executed.error},
            )
        )
        return executed
