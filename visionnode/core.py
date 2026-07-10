from __future__ import annotations

import ctypes
import platform
from ctypes import c_char_p
from ctypes import c_int
from ctypes import c_uint32
from ctypes import c_uint64
from ctypes import c_void_p
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path


class VisionNodeError(RuntimeError):
    pass


class PixelFormat(IntEnum):
    UNKNOWN = 0
    GRAY8 = 1
    BGR24 = 2
    BGRA32 = 3


class _VisionNodeFrameData(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("width", c_int),
        ("height", c_int),
        ("channels", c_int),
        ("opencv_type", c_int),
        ("pixel_format", c_uint32),
        ("source_id", c_uint32),
        ("sequence_id", c_uint64),
        ("stride_bytes", c_uint64),
        ("bytes", c_uint64),
    ]


@dataclass(slots=True)
class FrameSnapshot:
    data: bytes
    width: int
    height: int
    channels: int
    opencv_type: int
    pixel_format: PixelFormat
    source_id: int
    sequence_id: int
    stride_bytes: int
    bytes_count: int

    def as_numpy(self):
        try:
            import numpy as np
        except ImportError as exc:
            raise VisionNodeError("numpy is required for FrameSnapshot.as_numpy()") from exc

        if self.bytes_count != len(self.data):
            raise VisionNodeError("frame byte count does not match copied payload length")

        array = np.frombuffer(self.data, dtype=np.uint8)
        if self.channels <= 1:
            return array.reshape((self.height, self.width))
        return array.reshape((self.height, self.width, self.channels))


def default_library_path(repo_root: Path | None = None) -> Path:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "lib" / "libvisionnode.so"


def load_library(library_path: str | Path | None = None) -> ctypes.CDLL:
    resolved_path = Path(library_path) if library_path is not None else default_library_path()
    if not resolved_path.exists():
        raise FileNotFoundError(
            f"Shared library not found at {resolved_path}. Download a release asset or pass "
            "an explicit library_path."
        )

    if platform.system() == "Windows" and resolved_path.suffix == ".so":
        raise VisionNodeError(
            "Windows Python cannot load Linux libvisionnode.so. Run this through WSL/Linux "
            "or use a Windows visionnode.dll release when available."
        )

    library = ctypes.CDLL(str(resolved_path))
    _configure_api(library)
    return library


def _configure_api(library: ctypes.CDLL) -> None:
    library.visionnode_manager_create.restype = c_void_p

    library.visionnode_manager_destroy.argtypes = [c_void_p]
    library.visionnode_manager_destroy.restype = None

    library.visionnode_manager_add_camera_source.argtypes = [c_void_p, c_uint32, c_int]
    library.visionnode_manager_add_camera_source.restype = c_int

    library.visionnode_manager_add_video_file_source.argtypes = [c_void_p, c_uint32, c_char_p]
    library.visionnode_manager_add_video_file_source.restype = c_int

    library.visionnode_manager_add_video_file_source_ex.argtypes = [c_void_p, c_uint32, c_char_p, c_int]
    library.visionnode_manager_add_video_file_source_ex.restype = c_int

    library.visionnode_manager_has_source.argtypes = [c_void_p, c_uint32]
    library.visionnode_manager_has_source.restype = c_int

    library.visionnode_manager_start_all.argtypes = [c_void_p]
    library.visionnode_manager_start_all.restype = c_int

    library.visionnode_manager_stop_all.argtypes = [c_void_p]
    library.visionnode_manager_stop_all.restype = None

    library.visionnode_manager_get_latest_frame.argtypes = [
        c_void_p,
        c_uint32,
        ctypes.POINTER(_VisionNodeFrameData),
    ]
    library.visionnode_manager_get_latest_frame.restype = c_int

    library.visionnode_frame_data_release.argtypes = [ctypes.POINTER(_VisionNodeFrameData)]
    library.visionnode_frame_data_release.restype = None


class VisionNodeClient:
    def __init__(self, library_path: str | Path | None = None) -> None:
        self._library = load_library(library_path)
        self._manager = self._library.visionnode_manager_create()
        if not self._manager:
            raise VisionNodeError("visionnode_manager_create() returned null")
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._library.visionnode_manager_stop_all(self._manager)
        self._library.visionnode_manager_destroy(self._manager)
        self._closed = True

    def __enter__(self) -> "VisionNodeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def add_camera_source(self, source_id: int, camera_index: int = 0) -> bool:
        return bool(
            self._library.visionnode_manager_add_camera_source(
                self._manager,
                source_id,
                camera_index,
            )
        )

    def add_video_file_source(
        self,
        source_id: int,
        video_path: str | Path,
        loop_video: bool = False,
    ) -> bool:
        encoded_path = str(video_path).encode("utf-8")
        return bool(
            self._library.visionnode_manager_add_video_file_source_ex(
                self._manager,
                source_id,
                encoded_path,
                1 if loop_video else 0,
            )
        )

    def has_source(self, source_id: int) -> bool:
        return bool(self._library.visionnode_manager_has_source(self._manager, source_id))

    def start(self) -> bool:
        return bool(self._library.visionnode_manager_start_all(self._manager))

    def stop(self) -> None:
        self._library.visionnode_manager_stop_all(self._manager)

    def get_latest_frame(self, source_id: int) -> FrameSnapshot | None:
        raw_frame = _VisionNodeFrameData()
        got_frame = self._library.visionnode_manager_get_latest_frame(
            self._manager,
            source_id,
            ctypes.byref(raw_frame),
        )
        if not got_frame:
            self._library.visionnode_frame_data_release(ctypes.byref(raw_frame))
            return None

        try:
            copied_payload = ctypes.string_at(raw_frame.data, raw_frame.bytes)
            return FrameSnapshot(
                data=copied_payload,
                width=raw_frame.width,
                height=raw_frame.height,
                channels=raw_frame.channels,
                opencv_type=raw_frame.opencv_type,
                pixel_format=PixelFormat(raw_frame.pixel_format),
                source_id=raw_frame.source_id,
                sequence_id=raw_frame.sequence_id,
                stride_bytes=raw_frame.stride_bytes,
                bytes_count=raw_frame.bytes,
            )
        finally:
            self._library.visionnode_frame_data_release(ctypes.byref(raw_frame))
