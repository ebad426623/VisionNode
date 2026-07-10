# VisionNode

VisionNode is the public distribution and Python integration layer for a
low-latency native video ingestion engine designed for real-time ML pipelines.

It exists for workloads where Python inference should consume the freshest frame
available instead of getting stuck behind stale buffered capture work.

## What This Repo Contains

- the public Python `ctypes` wrapper in `visionnode/`
- a basic demo in `examples/basic_video_demo.py`
- release-oriented documentation for loading the native library

This repository contains the public wrapper, example usage, and release-facing
distribution layout.

## What Problem VisionNode Solves

VisionNode separates raw video capture from downstream inference so Python apps
can stay focused on model execution, business logic, and result handling.

The runtime model is latest-frame oriented:

- one capture worker runs per source
- the native side keeps ingesting frames continuously
- older frames can be overwritten
- Python pulls the freshest currently available frame

That tradeoff is intentional for real-time applications such as:

- warehouse safety monitoring
- factory-floor vision systems
- robotics and autonomy
- self-driving and ADAS prototyping

## Distribution Model

This repository provides the public Python wrapper, example usage, and release
binaries for VisionNode.

The native shared library is distributed through GitHub Releases and loaded by
the Python wrapper at runtime.

## Getting The Native Library

This repository is intended to distribute prebuilt binaries through GitHub
Releases.

Expected release assets include:

- `libvisionnode.so` for Linux and WSL
- later `visionnode.dll` for Windows

Place the downloaded library at:

```text
lib/libvisionnode.so
```

Or pass an explicit path when constructing the client.

## Python Wrapper Usage

```python
from visionnode import VisionNodeClient

with VisionNodeClient(library_path="lib/libvisionnode.so") as client:
    client.add_video_file_source(source_id=1, video_path="sample.mp4", loop_video=True)
    client.start()

    frame = client.get_latest_frame(1)
    if frame is not None:
        image = frame.as_numpy()
        print(frame.sequence_id, image.shape)
```

`FrameSnapshot` includes:

- raw copied frame bytes
- width and height
- channel count
- OpenCV type
- pixel format
- source id
- sequence id
- stride in bytes

## Public Python API

Import from the public package like this:

```python
from visionnode import FrameSnapshot
from visionnode import PixelFormat
from visionnode import VisionNodeClient
from visionnode import VisionNodeError
from visionnode import default_library_path
from visionnode import load_library
```

### `VisionNodeClient`

Main Python entry point for working with the native `libvisionnode.so` library.
It creates a native manager, exposes source registration methods, starts native
capture, and lets Python pull the freshest frame currently available.

#### `VisionNodeClient(library_path=None)`

Creates a client and loads the native shared library.

- purpose: open the `.so` and create the native manager instance
- use when: starting a VisionNode session from Python
- `library_path`: optional explicit path to the shared library; if omitted, the
  wrapper looks for `lib/libvisionnode.so`

#### `close()`

Stops native capture and destroys the native manager safely.

- purpose: release native resources
- use when: shutting down the client explicitly

#### `add_camera_source(source_id, camera_index=0)`

Registers a live camera source with the native engine.

- purpose: attach a camera device to the manager
- use when: ingesting frames from a webcam or camera index
- returns: `True` on success, `False` on failure

#### `add_video_file_source(source_id, video_path, loop_video=False)`

Registers a video file source with optional loop mode.

- purpose: attach a file-backed source to the manager
- use when: testing with recorded clips or running repeatable demos
- `loop_video=True`: restart from frame `0` at end-of-file
- returns: `True` on success, `False` on failure

#### `has_source(source_id)`

Checks whether a source id is already registered.

- purpose: confirm manager state before starting or polling
- returns: `True` if the source exists, otherwise `False`

#### `start()`

Starts all registered native capture workers.

- purpose: begin native frame ingestion
- use when: all desired sources have been added
- returns: `True` on success, `False` on failure

#### `stop()`

Stops all registered native capture workers.

- purpose: halt ingestion without destroying the Python client object

#### `get_latest_frame(source_id)`

Fetches the freshest available frame for one source.

- purpose: pull the current latest frame from the native latest-frame buffer
- returns: a `FrameSnapshot` when a frame is available, otherwise `None`
- behavior: older frames may be skipped by design if Python polls slower than
  the native capture thread

### `FrameSnapshot`

Python-side immutable snapshot of one frame returned from the native library.

- `data`: copied raw frame bytes
- `width`: frame width in pixels
- `height`: frame height in pixels
- `channels`: number of channels
- `opencv_type`: original OpenCV matrix type from the native side
- `pixel_format`: one of the `PixelFormat` enum values
- `source_id`: source identifier for the frame
- `sequence_id`: monotonically increasing frame sequence number
- `stride_bytes`: row stride in bytes
- `bytes_count`: total copied payload size in bytes

#### `FrameSnapshot.as_numpy()`

Converts the copied payload into a NumPy array.

- purpose: make the frame convenient to use in Python CV and ML code
- returns: a `(height, width)` grayscale array or `(height, width, channels)`
  image array
- requires: `numpy`

### `PixelFormat`

Enum describing the native pixel format of the returned frame.

- `PixelFormat.UNKNOWN`
- `PixelFormat.GRAY8`
- `PixelFormat.BGR24`
- `PixelFormat.BGRA32`

### `VisionNodeError`

Custom runtime exception raised by the Python wrapper.

- purpose: report VisionNode-specific wrapper/runtime problems clearly

### `default_library_path(repo_root=None)`

Returns the default expected path to the VisionNode shared library.

- purpose: resolve the conventional release layout automatically
- default result: `lib/libvisionnode.so`

### `load_library(library_path=None)`

Loads the native shared library and configures the `ctypes` function bindings.

- purpose: open the `.so` manually when needed
- use when: you want direct access to the `ctypes.CDLL` handle
- returns: a configured `ctypes.CDLL`

## Demo

Run the example with a local video file:

```bash
python3 examples/basic_video_demo.py /path/to/video.mp4 --library-path lib/libvisionnode.so --loop-video
```

The demo registers one video source, starts the native manager, and prints
fresh frame metadata as frames arrive.

## Platform Note

Windows Python cannot load Linux `libvisionnode.so`.

If you are using WSL, run the Python example from WSL. When a Windows native
build becomes available, this repo can also distribute a `visionnode.dll`
release asset for Windows Python consumers.
