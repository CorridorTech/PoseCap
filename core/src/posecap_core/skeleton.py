"""SMPL-X joint-order mapping — index is the wire contract, not the name.

The wire format (contracts) carries unnamed arrays in SMPL-X joint order:
position 0 is the pelvis (driven by global_orient), body joints occupy
positions 1..21, and the hands are the trailing 2 x 15 names, left block
first. Ported verbatim from the POC's model spec.
"""

from posecap_contracts import NUM_BODY_JOINTS, NUM_HAND_JOINTS

PELVIS = "pelvis"

SMPLX_JOINT_NAMES: tuple[str, ...] = (
    "pelvis",
    "left_hip",
    "right_hip",
    "spine1",
    "left_knee",
    "right_knee",
    "spine2",
    "left_ankle",
    "right_ankle",
    "spine3",
    "left_foot",
    "right_foot",
    "neck",
    "left_collar",
    "right_collar",
    "head",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "jaw",
    "left_eye_smplhf",
    "right_eye_smplhf",
    "left_index1",
    "left_index2",
    "left_index3",
    "left_middle1",
    "left_middle2",
    "left_middle3",
    "left_pinky1",
    "left_pinky2",
    "left_pinky3",
    "left_ring1",
    "left_ring2",
    "left_ring3",
    "left_thumb1",
    "left_thumb2",
    "left_thumb3",
    "right_index1",
    "right_index2",
    "right_index3",
    "right_middle1",
    "right_middle2",
    "right_middle3",
    "right_pinky1",
    "right_pinky2",
    "right_pinky3",
    "right_ring1",
    "right_ring2",
    "right_ring3",
    "right_thumb1",
    "right_thumb2",
    "right_thumb3",
)

_HAND_START = len(SMPLX_JOINT_NAMES) - 2 * NUM_HAND_JOINTS

BODY_JOINT_NAMES: tuple[str, ...] = SMPLX_JOINT_NAMES[1 : 1 + NUM_BODY_JOINTS]
LEFT_HAND_JOINT_NAMES: tuple[str, ...] = SMPLX_JOINT_NAMES[
    _HAND_START : _HAND_START + NUM_HAND_JOINTS
]
RIGHT_HAND_JOINT_NAMES: tuple[str, ...] = SMPLX_JOINT_NAMES[
    _HAND_START + NUM_HAND_JOINTS : _HAND_START + 2 * NUM_HAND_JOINTS
]
