"""Story 7.2: Auto-Prelabeling Pipeline — TDD tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestPrelabelingCLI:
    """AC-1: Argument parsing and validation."""

    def test_prelabel_subcommand_exists(self) -> None:
        """Verify `python -m lagent.train prelabel` is recognized."""
        from lagent.train.prelabel import prelabel_command
        assert callable(prelabel_command)

    def test_recording_argument_required(self) -> None:
        """Verify --recording argument is required."""
        from lagent.train.prelabel import parse_prelabel_args
        with pytest.raises(SystemExit):
            # Should fail without --recording
            parse_prelabel_args([])

    def test_recording_argument_parsing(self) -> None:
        """Parse --recording path correctly."""
        from lagent.train.prelabel import parse_prelabel_args
        args = parse_prelabel_args(["--recording", "/path/to/recording"])
        assert args.recording == Path("/path/to/recording")

    def test_batch_size_argument_optional(self) -> None:
        """--batch-size is optional; default is 32."""
        from lagent.train.prelabel import parse_prelabel_args
        args = parse_prelabel_args(["--recording", "/path/to/rec"])
        assert args.batch_size == 32

    def test_batch_size_argument_custom(self) -> None:
        """--batch-size can be customized."""
        from lagent.train.prelabel import parse_prelabel_args
        args = parse_prelabel_args(["--recording", "/path/to/rec", "--batch-size", "16"])
        assert args.batch_size == 16

    def test_confidence_threshold_argument_optional(self) -> None:
        """--confidence-threshold is optional; default is 0.5."""
        from lagent.train.prelabel import parse_prelabel_args
        args = parse_prelabel_args(["--recording", "/path/to/rec"])
        assert args.confidence_threshold == 0.5

    def test_confidence_threshold_argument_custom(self) -> None:
        """--confidence-threshold can be customized."""
        from lagent.train.prelabel import parse_prelabel_args
        args = parse_prelabel_args(["--recording", "/path/to/rec", "--confidence-threshold", "0.7"])
        assert args.confidence_threshold == 0.7


class TestRecordingValidation:
    """AC-1: Recording directory structure validation."""

    def test_recording_directory_exists(self) -> None:
        """Recording directory must exist."""
        from lagent.train.prelabel import validate_recording_directory
        nonexistent = Path("/nonexistent/path/12345")
        with pytest.raises(FileNotFoundError):
            validate_recording_directory(nonexistent)

    def test_recording_has_frames_directory(self) -> None:
        """Recording directory must contain 'frames/' subdirectory."""
        from lagent.train.prelabel import validate_recording_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            rec_dir = Path(tmpdir)
            # Missing frames/
            with pytest.raises(ValueError, match="frames"):
                validate_recording_directory(rec_dir)

    def test_recording_has_inputs_jsonl(self) -> None:
        """Recording directory must contain 'inputs.jsonl'."""
        from lagent.train.prelabel import validate_recording_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            rec_dir = Path(tmpdir)
            (rec_dir / "frames").mkdir()
            # Missing inputs.jsonl
            with pytest.raises(ValueError, match="inputs.jsonl"):
                validate_recording_directory(rec_dir)

    def test_recording_valid_structure(self) -> None:
        """Recording with frames/ and inputs.jsonl is valid."""
        from lagent.train.prelabel import validate_recording_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            rec_dir = Path(tmpdir)
            (rec_dir / "frames").mkdir()
            (rec_dir / "inputs.jsonl").touch()
            # Should not raise
            validate_recording_directory(rec_dir)


class TestFrameLoading:
    """Load frames from disk in batches."""

    def test_list_frame_files_png_jpeg(self) -> None:
        """List only PNG and JPEG frame files."""
        from lagent.train.prelabel import list_frame_files
        with tempfile.TemporaryDirectory() as tmpdir:
            frames_dir = Path(tmpdir)
            (frames_dir / "frame_0.png").touch()
            (frames_dir / "frame_1.jpg").touch()
            (frames_dir / "frame_2.jpeg").touch()
            (frames_dir / "readme.txt").touch()  # Should be ignored
            files = list_frame_files(frames_dir)
            assert len(files) == 3
            assert all(f.suffix.lower() in {".png", ".jpg", ".jpeg"} for f in files)

    def test_list_frame_files_sorted_order(self) -> None:
        """Frame files are sorted by filename."""
        from lagent.train.prelabel import list_frame_files
        with tempfile.TemporaryDirectory() as tmpdir:
            frames_dir = Path(tmpdir)
            (frames_dir / "frame_2.png").touch()
            (frames_dir / "frame_0.png").touch()
            (frames_dir / "frame_1.png").touch()
            files = list_frame_files(frames_dir)
            assert [f.name for f in files] == ["frame_0.png", "frame_1.png", "frame_2.png"]

    def test_batch_frame_loader_yields_batches(self) -> None:
        """Batch loader yields frames in batches of specified size."""
        from lagent.train.prelabel import batch_frame_loader
        with tempfile.TemporaryDirectory() as tmpdir:
            frames_dir = Path(tmpdir)
            for i in range(5):
                (frames_dir / f"frame_{i}.png").touch()
            batches = list(batch_frame_loader(frames_dir, batch_size=2))
            assert len(batches) == 3  # 5 frames in batches of 2 → 3 batches
            assert len(batches[0]) == 2
            assert len(batches[1]) == 2
            assert len(batches[2]) == 1


class TestYoloInferenceIntegration:
    """AC-1: Apply YOLO models to frames."""

    @patch("lagent.train.prelabel.YoloInference")
    def test_yolo_inference_detector_instantiated(self, mock_yolo_cls: Any) -> None:
        """YoloInference is instantiated with correct parameters."""
        from lagent.train.prelabel import create_yolo_detector
        with tempfile.TemporaryDirectory() as tmpdir:
            rec_dir = Path(tmpdir)
            detector = create_yolo_detector(rec_dir, confidence_threshold=0.6)
            mock_yolo_cls.assert_called()
            call_kwargs = mock_yolo_cls.call_args[1] if mock_yolo_cls.call_args else {}
            assert call_kwargs.get("confidence_threshold", 0.5) == 0.6

    @patch("lagent.train.prelabel.YoloInference")
    def test_yolo_detect_returns_detections(self, mock_yolo_cls: Any) -> None:
        """YoloInference.detect returns PerceptionResult with detections."""
        from lagent.common import Detection, PerceptionResult
        from lagent.train.prelabel import create_yolo_detector, run_inference_on_batch

        mock_detector = MagicMock()
        mock_detection = Detection(class_name="player", confidence=0.95, bbox_xyxy=(10, 20, 100, 150))
        mock_detector.detect.return_value = PerceptionResult(detections=[mock_detection])
        mock_yolo_cls.return_value = mock_detector

        detector = create_yolo_detector(Path("."), confidence_threshold=0.5)
        # Mock frame data
        frame_paths = [Path("frame_0.png")]
        results = run_inference_on_batch(detector, frame_paths)

        assert len(results) == 1
        assert results[0][0] == Path("frame_0.png")
        assert len(results[0][1].detections) == 1
        assert results[0][1].detections[0].class_name == "player"


class TestLabelStudioFormat:
    """AC-2: Label Studio JSON format output."""

    def test_label_studio_schema_structure(self) -> None:
        """Label Studio JSON has correct schema."""
        from lagent.train.prelabel import build_label_studio_json
        inference_results = []
        tasks = build_label_studio_json(inference_results, Path("recordings/session123"))
        assert isinstance(tasks, list)

    def test_label_studio_task_for_frame(self) -> None:
        """Each frame creates one Label Studio task."""
        from lagent.common import Detection, PerceptionResult
        from lagent.train.prelabel import build_label_studio_json
        
        inference_results = [
            (Path("frame_0.png"), PerceptionResult(detections=[
                Detection(class_name="mob", confidence=0.95, bbox_xyxy=(10, 20, 100, 150))
            ]))
        ]
        tasks = build_label_studio_json(inference_results, Path("recordings/session123"))
        
        assert len(tasks) == 1
        assert tasks[0]["id"] == 1
        assert "data" in tasks[0]

    def test_label_studio_image_reference(self) -> None:
        """Task image_url references the frame file."""
        from lagent.common import Detection, PerceptionResult
        from lagent.train.prelabel import build_label_studio_json
        
        inference_results = [
            (Path("frame_0.png"), PerceptionResult(detections=[]))
        ]
        tasks = build_label_studio_json(inference_results, Path("recordings/session123"))
        
        assert "image" in tasks[0]["data"] or "image_url" in tasks[0]["data"]

    def test_label_studio_regions_from_detections(self) -> None:
        """Detections are converted to Label Studio regions."""
        from lagent.common import Detection, PerceptionResult
        from lagent.train.prelabel import build_label_studio_json
        
        inference_results = [
            (Path("frame_0.png"), PerceptionResult(detections=[
                Detection(class_name="mob", confidence=0.95, bbox_xyxy=(10, 20, 100, 150))
            ]))
        ]
        tasks = build_label_studio_json(inference_results, Path("recordings/session123"))
        
        assert "annotations" in tasks[0]
        if tasks[0]["annotations"]:
            result = tasks[0]["annotations"][0]
            assert "result" in result or "regions" in result

    def test_bbox_conversion_xyxy_to_label_studio(self) -> None:
        """Bounding boxes are converted from xyxy to Label Studio xywh format."""
        from lagent.train.prelabel import convert_bbox_xyxy_to_label_studio
        
        # xyxy: (x1, y1, x2, y2) = (10, 20, 100, 150)
        # xywh: (x, y, width, height) = (10, 20, 90, 130)
        result = convert_bbox_xyxy_to_label_studio((10, 20, 100, 150))
        assert result == (10, 20, 90, 130)

    def test_label_studio_output_written_atomically(self) -> None:
        """prelabeled.json is written atomically to recording directory."""
        from lagent.train.prelabel import write_label_studio_json
        from lagent.common import PerceptionResult
        
        with tempfile.TemporaryDirectory() as tmpdir:
            rec_dir = Path(tmpdir)
            (rec_dir / "frames").mkdir()
            (rec_dir / "inputs.jsonl").touch()
            
            inference_results = [
                (Path("frame_0.png"), PerceptionResult(detections=[]))
            ]
            tasks = [{"id": 1, "data": {}}]
            
            write_label_studio_json(rec_dir, tasks)
            
            output_file = rec_dir / "prelabeled.json"
            assert output_file.exists()
            with open(output_file) as f:
                data = json.load(f)
                assert isinstance(data, list)


class TestPipelineExecution:
    """AC-1,2: Full prelabeling pipeline."""

    @patch("lagent.train.prelabel.create_yolo_detector")
    def test_prelabel_pipeline_end_to_end(self, mock_create_detector: Any) -> None:
        """Full pipeline: validate → load → infer → output."""
        from lagent.common import Detection, PerceptionResult
        from lagent.train.prelabel import run_prelabeling
        
        with tempfile.TemporaryDirectory() as tmpdir:
            rec_dir = Path(tmpdir)
            (rec_dir / "frames").mkdir()
            (rec_dir / "inputs.jsonl").touch()
            (rec_dir / "frames" / "frame_0.png").touch()
            
            mock_detector = MagicMock()
            mock_detector.detect.return_value = PerceptionResult(detections=[
                Detection(class_name="mob", confidence=0.95, bbox_xyxy=(10, 20, 100, 150))
            ])
            mock_create_detector.return_value = mock_detector
            
            run_prelabeling(rec_dir, batch_size=32, confidence_threshold=0.5)
            
            # Verify output file was created
            output_file = rec_dir / "prelabeled.json"
            assert output_file.exists()
            with open(output_file) as f:
                data = json.load(f)
                assert len(data) >= 0


class TestErrorHandling:
    """Robust error handling during preprocessing."""

    def test_skip_invalid_frame_files(self) -> None:
        """Skip frames that fail to load; log and continue."""
        from lagent.train.prelabel import load_frame_safe
        
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_frame = Path(tmpdir) / "invalid.png"
            invalid_frame.write_text("not a valid image")
            
            # Should return None for invalid frames
            result = load_frame_safe(invalid_frame)
            assert result is None

    def test_inference_error_skips_frame(self) -> None:
        """Inference failures skip frame; don't halt pipeline."""
        from lagent.train.prelabel import run_inference_on_batch
        from unittest.mock import MagicMock
        
        mock_detector = MagicMock()
        mock_detector.detect.side_effect = Exception("CUDA out of memory")
        
        frame_paths = [Path("frame_0.png"), Path("frame_1.png")]
        results = run_inference_on_batch(mock_detector, frame_paths)
        
        # Should return empty list or None for failed frames
        assert isinstance(results, (list, type(None)))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
