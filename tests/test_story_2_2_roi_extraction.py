import pytest

from lagent.agent.profile import ProfileValidationError, extract_roi_map, load_profile, validate_roi_positions


def _make_frame():
    frame = [[[0, 0, 0] for _ in range(400)] for _ in range(200)]
    for y in range(20, 40):
        for x in range(100, 300):
            frame[y][x] = [255, 255, 255]
    for y in range(45, 65):
        for x in range(100, 300):
            frame[y][x] = [128, 128, 128]
    return frame


def test_extract_roi_map_uses_agent_profile_coordinates():
    profile = load_profile("warlord")
    frame = _make_frame()

    rois = extract_roi_map(frame, profile)

    assert set(rois) >= {"health_bar", "mana_bar"}
    assert len(rois["health_bar"]) == 20
    assert len(rois["health_bar"][0]) == 200
    assert len(rois["mana_bar"]) == 20
    assert len(rois["mana_bar"][0]) == 200
    assert rois["health_bar"][0][0] == [255, 255, 255]
    assert rois["mana_bar"][0][0] == [128, 128, 128]


def test_validate_roi_positions_rejects_out_of_bounds_value():
    profile = load_profile("warlord")
    profile.roi_positions["mob_area"] = (350, 10, 500, 50)

    with pytest.raises(ProfileValidationError, match="mob_area"):
        validate_roi_positions(profile.roi_positions, width=400, height=200)


def test_extract_roi_map_raises_descriptive_error_for_invalid_profile():
    profile = load_profile("warlord")
    profile.roi_positions["health_bar"] = (-1, 0, 10, 20)

    with pytest.raises(ProfileValidationError, match="health_bar"):
        extract_roi_map(_make_frame(), profile)
