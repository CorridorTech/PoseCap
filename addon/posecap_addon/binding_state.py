"""Persistent, removable storage for a non-destructive pose binding."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from posecap_core import BoundBone, PoseBinding

_BINDING_PROPERTY = "_posecap_binding_v1"


def store_binding(armature: Any, binding: PoseBinding) -> None:
    """Persist a binding on the armature until the user explicitly unbinds it."""
    armature[_BINDING_PROPERTY] = json.dumps(
        {
            source_name: {
                "target": bone.target_bone_name,
                "compensation": bone.compensation_quaternion.tolist(),
                "neutral": bone.neutral_quaternion.tolist(),
            }
            for source_name, bone in binding.bones.items()
        },
        separators=(",", ":"),
    )


def load_binding(armature: Any) -> PoseBinding | None:
    """Restore a valid binding, cleaning a stale PoseCap value on failure."""
    get = getattr(armature, "get", None)
    if not callable(get):
        return None
    raw = get(_BINDING_PROPERTY)
    if not isinstance(raw, str):
        return None
    try:
        decoded = json.loads(raw)
        if not isinstance(decoded, dict):
            raise ValueError("binding payload must be an object")
        return PoseBinding(
            {
                str(source_name): BoundBone(
                    target_bone_name=str(value["target"]),
                    compensation_quaternion=np.asarray(value["compensation"]),
                    neutral_quaternion=np.asarray(value["neutral"]),
                )
                for source_name, value in decoded.items()
            }
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        clear_binding(armature)
        return None


def clear_binding(armature: Any) -> None:
    """Remove only PoseCap's reversible binding state from an armature."""
    if _BINDING_PROPERTY in armature:
        del armature[_BINDING_PROPERTY]


def is_bound_armature(armature: Any) -> bool:
    """Whether an armature carries a valid PoseCap binding."""
    return load_binding(armature) is not None
