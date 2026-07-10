"""Lazy PEAR adapter boundary.

PEAR stays external and pinned by config; importing this module must not import
torch, OpenCV, or upstream PEAR.
"""

import importlib
import os
import sys
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from posecap_contracts import (
    NUM_BETAS,
    NUM_BODY_JOINTS,
    NUM_EXPRESSION,
    NUM_HAND_JOINTS,
    SCHEMA_VERSION,
    PoseFrame,
    PosePayload,
)

from .config import PEAR_MODELS_REVISION
from .errors import CaptureUnavailableError


@dataclass(frozen=True)
class PearLiveConfig:
    """Runtime settings for PEAR live inference."""

    pear_root: Path
    source: int | str
    width: int = 1280
    height: int = 720
    yolo_threshold: float = 0.3
    crop_ratio: float = 1.75


class _PearRuntime(Protocol):
    def infer(self, rgb_image: object) -> PosePayload | None: ...


class _LiveCapture(Protocol):
    exhausted: bool

    def read_rgb(self) -> object | None: ...

    def release(self) -> None: ...


RuntimeFactory = Callable[[PearLiveConfig], _PearRuntime]
CaptureFactory = Callable[[PearLiveConfig], _LiveCapture]
Clock = Callable[[], float]

_PEAR_MODEL_REPO_ID = "BestWJH/PEAR_models"
_PEAR_MODEL_FILENAME = "ehm_model_stage1.pt"
_PEAR_CONFIG_RELATIVE_PATH = Path("configs") / "infer.yaml"
_PEAR_YOLO_RELATIVE_PATH = Path("model_zoo") / "yolov8x.pt"
_PEAR_YOLO_MODEL_NAME = "yolov8x.pt"
_PATCH_SHAPE = (256, 256)
_CAMERA_READ_RETRY_SECONDS = 0.005
_DEFAULT_MAX_CAMERA_READ_FAILURES = 200


class PearFrameSource:
    """Frame source for the external PEAR checkout."""

    def __init__(
        self,
        pear_root: Path,
        *,
        source: int | str,
        width: int = 1280,
        height: int = 720,
        yolo_threshold: float = 0.3,
        crop_ratio: float = 1.75,
        runtime_factory: RuntimeFactory | None = None,
        capture_factory: CaptureFactory | None = None,
        clock: Clock = time.time,
        max_camera_read_failures: int = _DEFAULT_MAX_CAMERA_READ_FAILURES,
    ) -> None:
        if max_camera_read_failures <= 0:
            raise ValueError("max_camera_read_failures must be positive")
        self._config = PearLiveConfig(
            pear_root=pear_root,
            source=source,
            width=width,
            height=height,
            yolo_threshold=yolo_threshold,
            crop_ratio=crop_ratio,
        )
        self._runtime_factory = runtime_factory or _load_pear_runtime
        self._capture_factory = capture_factory or _open_live_capture
        self._clock = clock
        self._max_camera_read_failures = max_camera_read_failures

    def frames(self) -> Generator[PoseFrame, None, None]:
        _validate_external_checkout(self._config.pear_root)
        runtime = self._runtime_factory(self._config)
        capture = self._capture_factory(self._config)
        seq = 0
        failed_reads = 0
        try:
            while True:
                rgb_image = capture.read_rgb()
                if rgb_image is None:
                    if capture.exhausted:
                        return
                    failed_reads += 1
                    if failed_reads >= self._max_camera_read_failures:
                        raise CaptureUnavailableError(
                            "camera index "
                            f"{self._config.source} did not return frames after "
                            f"{failed_reads} consecutive reads"
                        )
                    time.sleep(_CAMERA_READ_RETRY_SECONDS)
                    continue

                failed_reads = 0
                captured_at = self._clock()
                pose = runtime.infer(rgb_image)
                if pose is None:
                    yield PoseFrame(SCHEMA_VERSION, seq, captured_at, "no_person", None)
                else:
                    yield PoseFrame(SCHEMA_VERSION, seq, captured_at, "ok", pose)
                seq += 1
        finally:
            capture.release()


@dataclass(frozen=True)
class _PearModules:
    torch: Any
    cv2: Any
    transforms: Any
    yolo_class: Any
    hf_hub_download: Any
    lightning: Any
    ehm_pipeline_class: Any
    config_dict_class: Any
    add_extra_cfgs: Any


class _OpenCvLiveCapture:
    def __init__(self, config: PearLiveConfig, cv2: Any) -> None:
        self._cv2 = cv2
        self.exhausted = False
        self._capture = cv2.VideoCapture(config.source)
        if not bool(self._capture.isOpened()):
            self._capture.release()
            raise CaptureUnavailableError(f"could not open camera index {config.source}")
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)

    def read_rgb(self) -> object | None:
        ok, frame = self._capture.read()
        if not bool(ok):
            return None
        return self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)

    def release(self) -> None:
        self._capture.release()


class _VideoFileCapture:
    """Finite frame source for a video file; EOF ends the stream instead of retrying."""

    def __init__(self, config: PearLiveConfig, cv2: Any) -> None:
        self._cv2 = cv2
        self.exhausted = False
        self._capture = cv2.VideoCapture(str(config.source))
        if not bool(self._capture.isOpened()):
            self._capture.release()
            raise CaptureUnavailableError(f"could not open video file {config.source}")

    def read_rgb(self) -> object | None:
        ok, frame = self._capture.read()
        if not bool(ok):
            self.exhausted = True
            return None
        return self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)

    def release(self) -> None:
        self._capture.release()


class _LivePearRuntime:
    def __init__(
        self, config: PearLiveConfig, modules: _PearModules, model: Any, detector: Any
    ) -> None:
        self._config = config
        self._modules = modules
        self._model = model
        self._detector = detector
        self._transform = modules.transforms.ToTensor()

    def infer(self, rgb_image: object) -> PosePayload | None:
        image = np.asarray(rgb_image)
        height, width = image.shape[:2]
        boxes = self._detect_boxes(image)
        if len(boxes) < 1:
            return None

        xywh = _xyxy_to_xywh(boxes[0])
        bbox = _process_bbox(
            xywh,
            img_width=width,
            img_height=height,
            input_img_shape=_PATCH_SHAPE,
            ratio=self._config.crop_ratio,
        )
        if bbox is None:
            return None

        patch = _generate_patch_image(self._modules.cv2, image, bbox, out_shape=_PATCH_SHAPE)
        patch_tensor = self._transform(patch.astype(np.float32)) / 255.0
        patch_tensor = patch_tensor.unsqueeze(0).cuda()

        with self._modules.torch.no_grad():
            outputs = self._model(patch_tensor)
        return _pose_payload_from_outputs(outputs, self._modules.cv2)

    def _detect_boxes(self, image: np.ndarray) -> np.ndarray:
        results = self._detector.predict(
            image,
            device="cuda",
            imgsz=640,
            classes=0,
            conf=self._config.yolo_threshold,
            verbose=False,
        )
        return np.asarray(results[0].boxes.xyxy.detach().cpu().numpy(), dtype=np.float32)


def _load_pear_runtime(config: PearLiveConfig) -> _LivePearRuntime:
    pear_root = config.pear_root.resolve()
    modules = _load_pear_modules(pear_root)
    _ensure_cuda_available(modules.torch)

    with _pear_working_directory(pear_root):
        if hasattr(modules.torch, "set_float32_matmul_precision"):
            modules.torch.set_float32_matmul_precision("high")
        modules.lightning.fabric.seed_everything(10)

        meta_cfg = modules.config_dict_class(
            model_config_path=str(pear_root / _PEAR_CONFIG_RELATIVE_PATH)
        )
        meta_cfg = modules.add_extra_cfgs(meta_cfg)

        weights_path = modules.hf_hub_download(
            repo_id=_PEAR_MODEL_REPO_ID,
            filename=_PEAR_MODEL_FILENAME,
            repo_type="model",
            revision=PEAR_MODELS_REVISION,
        )
        model = modules.ehm_pipeline_class(meta_cfg)
        state = modules.torch.load(weights_path, map_location="cpu", weights_only=True)
        model.backbone.load_state_dict(state["backbone"], strict=False)
        model.head.load_state_dict(state["head"], strict=False)
        model = model.cuda()
        model.eval()

        detector = modules.yolo_class(_resolve_yolo_model(pear_root))
    return _LivePearRuntime(config, modules, model, detector)


def _load_pear_modules(pear_root: Path) -> _PearModules:
    _prepend_sys_path(pear_root)
    torch = _import_optional("torch", "PyTorch")
    ultralytics = _import_optional("ultralytics", "Ultralytics")
    huggingface_hub = _import_optional("huggingface_hub", "Hugging Face Hub")
    pear_pipeline = _import_optional("models.pipeline.ehm_pipeline", "PEAR EHM pipeline")
    pear_utils = _import_optional("utils.general_utils", "PEAR general utils")
    return _PearModules(
        torch=torch,
        cv2=_import_optional("cv2", "OpenCV"),
        transforms=_import_optional("torchvision.transforms", "torchvision"),
        yolo_class=ultralytics.YOLO,
        hf_hub_download=huggingface_hub.hf_hub_download,
        lightning=_import_optional("lightning", "Lightning"),
        ehm_pipeline_class=pear_pipeline.Ehm_Pipeline,
        config_dict_class=pear_utils.ConfigDict,
        add_extra_cfgs=pear_utils.add_extra_cfgs,
    )


@contextmanager
def _pear_working_directory(pear_root: Path) -> Generator[None, None, None]:
    original_cwd = Path.cwd()
    os.chdir(pear_root)
    try:
        yield
    finally:
        os.chdir(original_cwd)


def _open_live_capture(config: PearLiveConfig) -> _OpenCvLiveCapture | _VideoFileCapture:
    cv2 = _import_optional("cv2", "OpenCV")
    if isinstance(config.source, str):
        return _VideoFileCapture(config, cv2)
    return _OpenCvLiveCapture(config, cv2)


def _resolve_yolo_model(pear_root: Path) -> str:
    local_model = pear_root / _PEAR_YOLO_RELATIVE_PATH
    if local_model.exists():
        return str(local_model)
    return _PEAR_YOLO_MODEL_NAME


def _import_optional(module_name: str, display_name: str) -> Any:
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise CaptureUnavailableError(
            f"{display_name} is not installed in the PEAR engine environment"
        ) from exc


def _prepend_sys_path(path: Path) -> None:
    resolved = str(path.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


def _ensure_cuda_available(torch: Any) -> None:
    try:
        available = bool(torch.cuda.is_available())
    except AttributeError as exc:
        raise CaptureUnavailableError("PyTorch CUDA runtime is not available") from exc
    if not available:
        raise CaptureUnavailableError("PEAR live inference requires CUDA, but PyTorch reports none")


def _xyxy_to_xywh(box: np.ndarray) -> np.ndarray:
    return np.asarray(
        [
            float(box[0]),
            float(box[1]),
            abs(float(box[2]) - float(box[0])),
            abs(float(box[3]) - float(box[1])),
        ],
        dtype=np.float32,
    )


def _process_bbox(
    bbox: np.ndarray,
    *,
    img_width: int,
    img_height: int,
    input_img_shape: tuple[int, int],
    ratio: float,
) -> np.ndarray | None:
    x, y, width, height = [float(value) for value in bbox]
    x1 = max(0.0, x)
    y1 = max(0.0, y)
    x2 = min(float(img_width - 1), x1 + max(0.0, width - 1.0))
    y2 = min(float(img_height - 1), y1 + max(0.0, height - 1.0))
    if width * height <= 0 or x2 <= x1 or y2 <= y1:
        return None

    width = x2 - x1
    height = y2 - y1
    center_x = x1 + width / 2.0
    center_y = y1 + height / 2.0
    aspect_ratio = input_img_shape[1] / input_img_shape[0]
    if width > aspect_ratio * height:
        height = width / aspect_ratio
    elif width < aspect_ratio * height:
        width = height * aspect_ratio

    width *= ratio
    height *= ratio
    return np.asarray([center_x - width / 2.0, center_y - height / 2.0, width, height]).astype(
        np.float32
    )


def _rotate_2d(point: np.ndarray, radians: float) -> np.ndarray:
    sin_value = np.sin(radians)
    cos_value = np.cos(radians)
    return np.asarray(
        [
            point[0] * cos_value - point[1] * sin_value,
            point[0] * sin_value + point[1] * cos_value,
        ],
        dtype=np.float32,
    )


def _patch_transform(
    cv2: Any,
    center_x: float,
    center_y: float,
    src_width: float,
    src_height: float,
    dst_width: int,
    dst_height: int,
) -> np.ndarray:
    source_center = np.asarray([center_x, center_y], dtype=np.float32)
    source_down = _rotate_2d(np.asarray([0.0, src_height * 0.5], dtype=np.float32), 0.0)
    source_right = _rotate_2d(np.asarray([src_width * 0.5, 0.0], dtype=np.float32), 0.0)
    destination_center = np.asarray([dst_width * 0.5, dst_height * 0.5], dtype=np.float32)
    destination_down = np.asarray([0.0, dst_height * 0.5], dtype=np.float32)
    destination_right = np.asarray([dst_width * 0.5, 0.0], dtype=np.float32)

    source = np.asarray(
        [source_center, source_center + source_down, source_center + source_right],
        dtype=np.float32,
    )
    destination = np.asarray(
        [
            destination_center,
            destination_center + destination_down,
            destination_center + destination_right,
        ],
        dtype=np.float32,
    )
    return cv2.getAffineTransform(source, destination).astype(np.float32)


def _generate_patch_image(
    cv2: Any, rgb_image: np.ndarray, bbox: np.ndarray, *, out_shape: tuple[int, int]
) -> np.ndarray:
    center_x = float(bbox[0] + 0.5 * bbox[2])
    center_y = float(bbox[1] + 0.5 * bbox[3])
    transform = _patch_transform(
        cv2,
        center_x,
        center_y,
        float(bbox[2]),
        float(bbox[3]),
        out_shape[1],
        out_shape[0],
    )
    patch = cv2.warpAffine(
        rgb_image.copy(),
        transform,
        (int(out_shape[1]), int(out_shape[0])),
        flags=cv2.INTER_LINEAR,
    )
    return patch.astype(np.float32)


def _pose_payload_from_outputs(outputs: Any, cv2: Any) -> PosePayload:
    body = outputs["body_param"]
    flame = outputs["flame_param"]
    return PosePayload(
        global_orient=_vec3(
            _matrix_stack_to_axis_angle(_squeeze_batch(body["global_pose"]), cv2)[0],
            "global_orient",
        ),
        body_pose=_vec3_rows(
            _matrix_stack_to_axis_angle(_squeeze_batch(body["body_pose"]), cv2),
            NUM_BODY_JOINTS,
            "body_pose",
        ),
        left_hand_pose=_vec3_rows(
            _matrix_stack_to_axis_angle(_squeeze_batch(body["left_hand_pose"]), cv2),
            NUM_HAND_JOINTS,
            "left_hand_pose",
        ),
        right_hand_pose=_vec3_rows(
            _matrix_stack_to_axis_angle(_squeeze_batch(body["right_hand_pose"]), cv2),
            NUM_HAND_JOINTS,
            "right_hand_pose",
        ),
        jaw_pose=_vec3(_to_numpy(flame["jaw_params"]).reshape(-1), "jaw_pose"),
        betas=_float_list(_to_numpy(body["shape"]).reshape(-1), NUM_BETAS, "betas"),
        expression=_float_list(_to_numpy(body["exp"]).reshape(-1), NUM_EXPRESSION, "expression"),
        transl=_vec3(_to_numpy(outputs["pd_cam"])[0, :3, 3], "transl"),
    )


def _squeeze_batch(value: Any) -> np.ndarray:
    array = _to_numpy(value)
    if len(array.shape) > 0 and array.shape[0] == 1:
        return np.squeeze(array, axis=0)
    return array


def _matrix_stack_to_axis_angle(matrices: np.ndarray, cv2: Any) -> np.ndarray:
    reshaped = np.asarray(matrices, dtype=np.float32).reshape(-1, 3, 3)
    return np.asarray([cv2.Rodrigues(matrix)[0].reshape(3) for matrix in reshaped])


def _to_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    return np.asarray(value, dtype=np.float32)


def _vec3(values: np.ndarray, name: str) -> list[float]:
    flattened = np.asarray(values, dtype=np.float32).reshape(-1)
    if flattened.size < 3:
        raise CaptureUnavailableError(f"PEAR output {name} must contain 3 floats")
    return [float(value) for value in flattened[:3]]


def _vec3_rows(values: np.ndarray, expected_rows: int, name: str) -> list[list[float]]:
    array = np.asarray(values, dtype=np.float32).reshape(-1, 3)
    if array.shape[0] != expected_rows:
        raise CaptureUnavailableError(
            f"PEAR output {name} must contain {expected_rows} vec3 rows, got {array.shape[0]}"
        )
    return [[float(value) for value in row] for row in array]


def _float_list(values: np.ndarray, expected_count: int, name: str) -> list[float]:
    flattened = np.asarray(values, dtype=np.float32).reshape(-1)
    if flattened.size < expected_count:
        raise CaptureUnavailableError(
            f"PEAR output {name} must contain at least {expected_count} floats"
        )
    return [float(value) for value in flattened[:expected_count]]


def _validate_external_checkout(pear_root: Path) -> None:
    if not pear_root.exists():
        raise CaptureUnavailableError(f"PEAR checkout not found: {pear_root}")
    if not pear_root.is_dir():
        raise CaptureUnavailableError(f"PEAR checkout is not a directory: {pear_root}")
    if not (pear_root / "models").exists():
        raise CaptureUnavailableError(
            f"PEAR checkout missing expected models package: {pear_root / 'models'}"
        )
    if not (pear_root / "utils").exists():
        raise CaptureUnavailableError(
            f"PEAR checkout missing expected utils package: {pear_root / 'utils'}"
        )
    if not (pear_root / _PEAR_CONFIG_RELATIVE_PATH).exists():
        raise CaptureUnavailableError(
            f"PEAR checkout missing expected infer config: {pear_root / _PEAR_CONFIG_RELATIVE_PATH}"
        )
