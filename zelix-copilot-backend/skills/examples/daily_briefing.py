"""Daily Briefing Skill.

Aggregates active tasks, urgent items, and daily metrics.
"""

from typing import Any, Dict, Optional
from core.sessions.context import EmployeeContext
from core.skills.base import BaseSkill, SkillResult
from core.skills.definition import SkillDefinition


class DailyBriefingSkill(BaseSkill):
    """Provides a daily executive/operational briefing."""

    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            id="daily_briefing",
            name="Daily Operational Briefing",
            description="Summarizes active tasks, urgent issues, and daily workload.",
            objectives=["Provide daily operational briefing"],
            required_tools=["get_work_items"],
            input_schema={},
            output_schema={"type": "object"},
            risk_level="LOW",
            allowed_roles=["executive_assistant", "operations_assistant", "admin"],
        )

    def execute(
        self,
        context: EmployeeContext,
        tools: Dict[str, Any],
        ai_provider: Optional[Any] = None,
        **kwargs: Any
    ) -> SkillResult:
        get_items_tool = tools.get("get_work_items")
        tasks = get_items_tool.execute(context) if get_items_tool else []

        pending_tasks = [t for t in tasks if t.get("status") != "completed"]
        high_priority = [t for t in pending_tasks if t.get("priority") == "high"]

        summary = {
            "total_active_tasks": len(pending_tasks),
            "urgent_tasks_count": len(high_priority),
            "urgent_tasks": high_priority,
            "briefing_text": f"You have {len(pending_tasks)} active tasks ({len(high_priority)} high priority).",
        }

        return SkillResult(
            success=True,
            skill_id=self.definition.id,
            output=summary,
        )
