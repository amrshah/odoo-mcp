"""Role Registry.

Central registry for managing AI Employee roles.
"""

from typing import Dict, List, Optional
from core.roles.manifest import RoleManifest


class RoleRegistry:
    """Registry for AI Employee roles."""

    def __init__(self) -> None:
        self._roles: Dict[str, RoleManifest] = {}

    def register(self, role: RoleManifest) -> None:
        """Register a new role manifest."""
        self._roles[role.id] = role

    def get(self, role_id: str) -> Optional[RoleManifest]:
        """Retrieve a role manifest by ID."""
        return self._roles.get(role_id)

    def list(self) -> List[RoleManifest]:
        """List all registered role manifests."""
        return list(self._roles.values())

    def unregister(self, role_id: str) -> bool:
        """Remove a role manifest by ID."""
        if role_id in self._roles:
            del self._roles[role_id]
            return True
        return False
