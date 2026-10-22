import cv2
import numpy as np
import pytest

from app.demo.camera import CameraRegistration
from app.demo.football import (
    JerseyGroups,
    adjust_visible_length,
    detection_classes,
    field_region,
    heatmap,
    on_field,
    role_classes,
    shirt_feature,
    visible_pitch_points,
)
from app.demo.metrics import Calibration, ground_point, summarize_track


def test_visible_pitch_quad_follows_grass_surface():
    frame = np.zeros((400, 640, 3), dtype=np.uint8)
    frame[80:300, 40:600] = (40, 170, 40)
    points = visible_pitch_points(frame)
    assert points is not None and len(points) == 4
    xs, ys = zip(*points, strict=True)
    assert min(xs) < 0.12 and max(xs) > 0.88
    assert min(ys) < 0.3 and max(ys) > 0.65


def test_cropped_tactical_view_does_not_keep_full_pitch_length():
    cal = Calibration(
        points=[(0.02, 0.72), (0.98, 0.71), (0.97, 0.28), (0.04, 0.30)],
        length_m=108,
        width_m=68,
        fixed_camera=True,
    )
    assert adjust_visible_length(cal).length_m == 60
    full = Calibration(
        points=[(0.05, 0.9), (0.95, 0.9), (0.95, 0.1), (0.05, 0.1)],
        length_m=105,
        width_m=68,
        fixed_camera=True,
    )
    assert adjust_visible_length(full).length_m == 105


def test_empty_points_wait_for_automatic_detection():
    cal = Calibration(points=[], length_m=60, width_m=68, fixed_camera=True)
    assert cal.points == []


def test_class_mapping_supports_coco_and_football_models():
    assert detection_classes({0: "person", 32: "sports ball"}) == ([0], [32])
    assert detection_classes({0: "ball", 1: "goalkeeper", 2: "player", 3: "referee"}) == (
        [1, 2],
        [0],
    )
    assert role_classes({0: "ball", 1: "goalkeeper", 2: "player", 3: "referee"}) == (
        [1, 2],
        [3],
        [0],
    )
    with pytest.raises(ValueError):
        detection_classes({0: "cat"})


def test_jerseys_keep_white_and_green_and_reject_tiny_crops():
    white = np.full((100, 60, 3), 245, np.uint8)
    green = np.full((100, 60, 3), (60, 200, 70), np.uint8)
    a = shirt_feature(white, [0, 0, 60, 100])
    b = shirt_feature(green, [0, 0, 60, 100])
    assert a is not None and b is not None
    assert np.linalg.norm(a - b) > 30
    assert shirt_feature(white, [0, 0, 2, 3]) is None
    groups = JerseyGroups()
    for identity in range(8):
        for _ in range(4):
            groups.observe(identity, a if identity < 4 else b)
    assert groups.fit()
    assert groups.team(0) in (1, 2)
    assert groups.team(0) != groups.team(4)
    for _ in range(5):
        groups.observe(99, np.array([0, 128, 128], dtype=np.float32))
    assert groups.team(99) is None


def test_single_kit_cannot_be_forced_into_two_teams():
    groups = JerseyGroups()
    for identity in range(8):
        for _ in range(4):
            groups.observe(identity, np.array([150, 110, 100], dtype=np.float32))
    assert not groups.fit()
    assert groups.team(1) is None


def test_grass_filter_excludes_people_in_stands_and_falls_back_without_grass():
    frame = np.zeros((400, 640, 3), dtype=np.uint8)
    frame[120:350, :] = (50, 160, 50)
    region = field_region(frame)
    assert region is not None
    assert on_field([200, 150, 230, 250], region)
    assert not on_field([200, 10, 230, 60], region)
    assert field_region(np.zeros_like(frame)) is None
    assert on_field([200, 10, 230, 60], None)


def test_heatmap_ignores_uncalibrated_samples_in_metric_mode():
    empty = heatmap([], 40, 20)
    unknown = heatmap([{"samples": [{"ground": None, "x": 0.5, "y": 0.5}]}], 40, 20)
    assert np.array_equal(empty, unknown)
    measured = heatmap([{"samples": [{"ground": [20, 10], "x": 0.5, "y": 0.5}]}], 40, 20)
    assert not np.array_equal(empty, measured)


def texture():
    rng = np.random.default_rng(42)
    return cv2.GaussianBlur(rng.integers(0, 256, (360, 640, 3), dtype=np.uint8), (3, 3), 0)


def test_camera_pan_is_removed_before_distance_measurement():
    first = texture()
    camera = CameraRegistration()
    assert camera.update(first, [])
    cal = Calibration(
        points=[(0, 0), (1, 0), (1, 1), (0, 1)],
        length_m=40,
        width_m=20,
        fixed_camera=False,
        compensate_camera=True,
    )
    samples = []
    for index, displacement in enumerate((0, 4, 8)):
        if index:
            moved = cv2.warpAffine(first, np.float32([[1, 0, displacement], [0, 1, 0]]), (640, 360))
            assert camera.update(moved, [])
        reference = camera.reference_point(0.5 + displacement / 640, 0.5)
        assert np.allclose(reference, (0.5, 0.5), atol=0.003)
        position = ground_point(*reference, cal, cal.matrix())
        samples.append({"t": index * 0.4, "ground": position, "confidence": 1, "segment": 0})
    summary = summarize_track(1, samples, 3, 25, True)
    assert summary["distance_m"] < 0.1


def test_camera_zoom_registration():
    frame = texture()
    camera = CameraRegistration()
    assert camera.update(frame, [])
    matrix = cv2.getRotationMatrix2D((320, 180), 0, 1.025)
    moved = cv2.warpAffine(frame, matrix, (640, 360))
    assert camera.update(moved, [])
    pixel = matrix @ np.array([200, 120, 1.0])
    assert np.allclose(
        camera.reference_point(pixel[0] / 640, pixel[1] / 360), (200 / 640, 120 / 360), atol=0.003
    )


def test_camera_loss_stays_invalid_instead_of_reusing_last_transform():
    frame = texture()
    camera = CameraRegistration()
    assert camera.update(frame, [])
    assert not camera.update(np.zeros_like(frame), [])
    assert camera.reference_point(0.5, 0.5) is None
    assert not camera.update(frame, [])
    assert camera.reason is not None


def test_pitch_keypoints_recover_metres_on_the_template():
    from app.demo.pitch import homography_from_keypoints, pitch_vertices

    vertices = pitch_vertices()
    image = np.column_stack([vertices[:, 0] * 8 + 40, vertices[:, 1] * 6 + 30]).astype(np.float32)
    matrix = homography_from_keypoints(image)
    assert matrix is not None
    pixel = np.array([40 + 8 * 52.5, 30 + 6 * 34.0, 1.0])
    projected = matrix @ pixel
    east, north = projected[0] / projected[2], projected[1] / projected[2]
    assert np.allclose((east, north), (52.5, 34.0), atol=0.2)


def test_keypoint_homography_projects_normalized_feet():
    from app.demo.pitch import pitch_vertices

    vertices = pitch_vertices()
    image = np.column_stack([vertices[:, 0] * 8 + 40, vertices[:, 1] * 6 + 30]).astype(np.float32)
    width, height = 1920.0, 1080.0
    matrix = np.array(
        cv2.findHomography(image, vertices)[0],
        dtype=np.float64,
    )
    cal = Calibration(
        points=[],
        length_m=105,
        width_m=68,
        fixed_camera=True,
        homography=matrix.tolist(),
        frame_width=int(width),
        frame_height=int(height),
        source="pitch-keypoints",
    )
    centre = image[13]  # halfway-line / near sideline is 14th? index 13 is (length/2, 0)
    ground = ground_point(float(centre[0] / width), float(centre[1] / height), cal, cal.matrix())
    assert ground is not None
    assert np.allclose(ground, vertices[13], atol=0.5)
