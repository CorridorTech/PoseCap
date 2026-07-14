import json
from collections.abc import Callable
from typing import Any

import pytest
from posecap_contracts import BackendManifestDecodeError, decode_pose_backend_manifest


def _valid_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "id": "pear",
        "display_name": "PEAR",
        "command": ["C:/PoseCap/posecap-engine.exe", "live"],
        "protocol_versions": [1],
        "capabilities": ["body"],
        "compatibility": {
            "operating_systems": ["windows"],
            "accelerators": ["nvidia-cuda"],
            "account": "MPI account required",
            "license": "MPI model terms apply",
        },
    }


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda document: document.update(id=""), "id"),
        (lambda document: document.update(display_name=3), "display_name"),
        (lambda document: document.update(command=[]), "command"),
        (lambda document: document.update(protocol_versions=[True]), "protocol_versions"),
        (lambda document: document.update(capabilities=["body", "body"]), "capabilities"),
        (
            lambda document: document["compatibility"].update(operating_systems=[]),
            "operating_systems",
        ),
        (lambda document: document["compatibility"].update(account=""), "account"),
        (lambda document: document["compatibility"].update(license=""), "license"),
    ],
)
def test_decoder_rejects_structurally_invalid_manifest(
    mutate: Callable[[dict[str, Any]], object], message: str
) -> None:
    document = _valid_document()
    mutate(document)

    with pytest.raises(BackendManifestDecodeError, match=message):
        decode_pose_backend_manifest(json.dumps(document))


def test_decoder_exposes_backend_capture_policy_with_safe_pear_defaults() -> None:
    document = _valid_document()
    document["requires_body_models"] = False
    document["apply_orientation_fix"] = False

    mediapipe = decode_pose_backend_manifest(json.dumps(document))
    pear = decode_pose_backend_manifest(json.dumps(_valid_document()))

    assert not mediapipe.requires_body_models
    assert not mediapipe.apply_orientation_fix
    assert pear.requires_body_models
    assert pear.apply_orientation_fix
