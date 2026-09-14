"""
core/roles/registry.py
Role Registry managing role definitions and capabilities.
"""

from typing import Dict, List, Optional
from core.roles.manifest import RoleManifest


class RoleRegistry:
    """Maintains role manifests and capability assignments."""

    def __init__(self) -> None:
        self._roles: Dict[str, RoleManifest] = {}

    def register(self, role: RoleManifest) -> None:
        self._roles[role.id] = role

    def get(self, role_id: str) -> Optional[RoleManifest]:
        return self._roles.get(role_id)

    def list_all(self) -> List[RoleManifest]:
        return list(self._roles.values())
