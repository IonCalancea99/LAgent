from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from lagent.train.ingest import ingest_video, parse_ingest_args, validate_video_url


def test_parse_ingest_args_requires_positive_fps_and_accepts_output_dir():
    args = parse_ingest_args(["--url", "https://youtu.be/video", "--fps", "5", "--output-dir", "data"])
    assert args.url == "https://youtu.be/video"
    assert args.fps == 5.0
    assert args.output_dir == Path("data")

    with pytest.raises(SystemExit):
        parse_ingest_args(["--url", "https://youtu.be/video", "--fps", "0"])


def test_validate_video_url_rejects_non_http_urls():
    validate_video_url("https://www.youtube.com/watch?v=video")
    with pytest.raises(ValueError, match="URL"):
        validate_video_url("video")


def test_ingest_downloads_extracts_and_writes_recording(tmp_path: Path):
    frames = [np.full((2, 3, 3), value, dtype=np.uint8) for value in range(3)]

    class FakeCapture:
        def __init__(self, path):
            self.path = path
            self.index = 0

        def isOpened(self):
            return True

        def get(self, prop):
            return {7: 3.0, 5: 3.0}.get(prop, 0.0)

        def set(self, prop, value):
            self.index = int(value)

        def read(self):
            if self.index >= len(frames):
                return False, None
            frame = frames[self.index]
            self.index += 1
            return True, frame

        def release(self):
            pass

    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def download(self, urls):
            Path(self.options["outtmpl"].replace("%(ext)s", "mp4")).write_bytes(b"video")
            return 0

    fake_cv2 = SimpleNamespace(
        VideoCapture=FakeCapture,
        CAP_PROP_FRAME_COUNT=7,
        CAP_PROP_FPS=5,
        CAP_PROP_POS_FRAMES=1,
        imwrite=lambda path, frame: Path(path).write_bytes(b"PNG" + bytes([frame[0, 0, 0]])),
    )
    fake_yt_dlp = SimpleNamespace(YoutubeDL=FakeYoutubeDL)

    with patch.dict("sys.modules", {"cv2": fake_cv2, "yt_dlp": fake_yt_dlp}):
        result = ingest_video("https://youtu.be/video", 3.0, output_dir=tmp_path)

    assert result.frame_count == 3
    assert len(list((result.recording_dir / "frames").glob("*.png"))) == 3
    assert (result.recording_dir / "inputs.jsonl").read_text() == ""
    metadata = json.loads((result.recording_dir / "metadata.json").read_text())
    assert metadata["source_url"] == "https://youtu.be/video"
    assert metadata["fps"] == 3.0
    assert not list(tmp_path.glob(".ingest-*"))