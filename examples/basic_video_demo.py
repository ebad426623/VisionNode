from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from visionnode import VisionNodeClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Basic VisionNode video-file demo")
    parser.add_argument("video_path", help="Path to a local video file")
    parser.add_argument("--source-id", type=int, default=1, help="Numeric source identifier")
    parser.add_argument("--library-path", help="Optional explicit path to libvisionnode.so")
    parser.add_argument("--loop-video", action="store_true", help="Restart the file at EOF")
    parser.add_argument("--poll-interval", type=float, default=0.25, help="Seconds between polls")
    parser.add_argument("--max-reads", type=int, default=20, help="Stop after this many successful frame reads")
    args = parser.parse_args()

    video_path = Path(args.video_path).expanduser().resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    with VisionNodeClient(library_path=args.library_path) as client:
        added = client.add_video_file_source(
            source_id=args.source_id,
            video_path=video_path,
            loop_video=args.loop_video,
        )
        if not added:
            raise RuntimeError("Failed to register video source")

        started = client.start()
        if not started:
            raise RuntimeError("Failed to start VisionNode manager")

        print(f"Polling source {args.source_id} from {video_path}")
        reads = 0
        while reads < args.max_reads:
            frame = client.get_latest_frame(args.source_id)
            if frame is not None:
                print(
                    f"sequence_id={frame.sequence_id} "
                    f"size={frame.width}x{frame.height} "
                    f"channels={frame.channels} "
                    f"bytes={frame.bytes_count}"
                )
                reads += 1
            time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()
