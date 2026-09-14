"""UI Action Output Adapter."""

from typing import Any, Dict
from pydantic import BaseModel


class UIAction(BaseModel):
    """Encapsulates a rich client-side UI command (e.g. redirect, open modal, render widget)."""

    action_name: str
    component: str
    props: Dict[str, Any] = {}
    session_id: str
    metadata: Dict[str, Any] = {}
