from app.calibration.homography import PitchMapper
from app.calibration.zones import PitchZones
from app.core.config import AppConfig, PitchConfig


def test_four_point_homography_maps_corners() -> None:
    config = AppConfig(pitch=PitchConfig(length_m=40, width_m=20))
    mapper = PitchMapper.from_points(
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        config,
        frame_width=100,
        frame_height=50,
    )
    near_left = mapper.to_world(0, 0)
    near_right = mapper.to_world(100, 0)
    far_right = mapper.to_world(100, 50)
    assert near_left is not None and abs(near_left[0]) < 0.2 and abs(near_left[1]) < 0.2
    assert near_right is not None and abs(near_right[0] - 40) < 0.2
    assert far_right is not None and abs(far_right[1] - 20) < 0.2


def test_zones_split_defense_mid_attack() -> None:
    zones = PitchZones(40, 20, 3, 3, 4, 6)
    assert zones.band(3, 10, attacking_home=True) == "defense"
    assert zones.band(20, 10, attacking_home=True) == "midfield"
    assert zones.band(36, 10, attacking_home=True) == "attack"
    assert zones.cell(2, 2) == "grid-0-0"
    assert zones.in_goal(-0.1, 10, 3.0, left=True)
