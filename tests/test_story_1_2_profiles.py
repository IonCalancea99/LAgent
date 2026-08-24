"""Acceptance tests for Story 1.2: YAML profile loading and validation."""

import subprocess
import sys
from pathlib import Path

import pytest

from lagent.agent.profile import ProfileValidationError, load_profile


def test_both_stub_profiles_load():
    assert load_profile("warlord").name == "warlord"
    assert load_profile("prophet").name == "prophet"


def test_missing_required_field_reports_field_path(tmp_path: Path):
    profile = Path("profiles/warlord.yaml").read_text()
    tmp_path.joinpath("warlord.yaml").write_text(profile.replace("roi_positions:\n", ""))

    with pytest.raises(ProfileValidationError, match="roi_positions"):
        load_profile("warlord", tmp_path)


def test_invalid_nested_value_reports_field_path(tmp_path: Path):
    tmp_path.joinpath("warlord.yaml").write_text(
        Path("profiles/warlord.yaml").read_text().replace("default: 0.6", "default: 1.5")
    )

    with pytest.raises(ProfileValidationError, match="confidence_thresholds.default"):
        load_profile("warlord", tmp_path)


def test_profile_is_reread_after_file_change(tmp_path: Path):
    profile_path = tmp_path / "warlord.yaml"
    profile_path.write_text(Path("profiles/warlord.yaml").read_text())
    assert load_profile("warlord", tmp_path).skill_key_bindings["attack"] == "1"

    profile_path.write_text(profile_path.read_text().replace('attack: "1"', 'attack: "9"'))
    assert load_profile("warlord", tmp_path).skill_key_bindings["attack"] == "9"


@pytest.mark.parametrize("profile_class", ["warlord", "prophet"])
def test_cli_logs_loaded_profile(profile_class: str):
    result = subprocess.run(
        [sys.executable, "-m", "lagent.agent", "--class", profile_class],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert f"Profile loaded: {profile_class}" in result.stderr