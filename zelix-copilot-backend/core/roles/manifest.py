"""
core/roles/manifest.py
Role Manifest definition for RBAC policies.
"""

from typing import List
from pydantic import BaseModel, Field


class RoleManifest(BaseModel):
    id: str
    name: str
    skills: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
