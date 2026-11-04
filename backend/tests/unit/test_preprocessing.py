"""Sprint 2 / D10: tests for unreadable files, aspect ratio, and output dimensions.

Uses the real diagrams already in data/diagrams/raw/ (no fabricated image
data) plus small deliberately-invalid fixtures to exercise error paths.
"""

import pytest

from app.modules.cv_pipeline.dataset_manifest import DIAGRAMS_DIR, load_manifest
from app.modules.cv_pipeline.pipeline import DEFAULT_MAX_SIZE, CVPreprocessor


@pytest.fixture(scope="module")
def sample_image_path():
    graphs = load_manifest()
    from pathlib import Path

    return str(DIAGRAMS_DIR / Path(graphs[0].source).name)


def test_load_rejects_unreadable_file(tmp_path):
    corrupt = tmp_path / "broken.png"
    corrupt.write_bytes(b"this is not a real png file")
    with pytest.raises(ValueError, match="Cannot load image"):
        CVPreprocessor().load(str(corrupt))


def test_load_rejects_missing_file():
    with pytest.raises(ValueError, match="Cannot load image"):
        CVPreprocessor().load("data/diagrams/raw/does_not_exist.png")


def test_load_rejects_unsupported_extension(tmp_path):
    bogus = tmp_path / "diagram.bmp"
    bogus.write_bytes(b"\x00" * 16)
    with pytest.raises(ValueError, match="Unsupported input format"):
        CVPreprocessor().load(str(bogus))


def test_resize_preserves_aspect_ratio(sample_image_path):
    pre = CVPreprocessor(max_size=500)  # force resizing on every real diagram
    img = pre.load(sample_image_path)
    h0, w0 = img.shape[:2]
    resized = pre._resize(img)
    h1, w1 = resized.shape[:2]
    assert abs((w0 / h0) - (w1 / h1)) < 0.01


def test_resize_only_shrinks_when_over_max_size(sample_image_path):
    pre = CVPreprocessor(max_size=10_000)  # larger than any real diagram
    img = pre.load(sample_image_path)
    resized = pre._resize(img)
    assert resized.shape == img.shape


def test_output_dimensions_respect_max_size_cap():
    pre = CVPreprocessor(max_size=800)
    for g in load_manifest():
        from pathlib import Path

        path = str(DIAGRAMS_DIR / Path(g.source).name)
        out = pre.preprocess(path)
        assert max(out.shape[:2]) <= 800


def test_default_max_size_is_documented_policy():
    assert CVPreprocessor().max_size == DEFAULT_MAX_SIZE


def test_grayscale_output_has_no_channel_dimension(sample_image_path):
    out = CVPreprocessor().preprocess(sample_image_path, color_mode="grayscale")
    assert out.ndim == 2


def test_rgb_and_bgr_outputs_have_swapped_channels(sample_image_path):
    pre = CVPreprocessor()
    bgr = pre.preprocess(sample_image_path, color_mode="bgr")
    rgb = pre.preprocess(sample_image_path, color_mode="rgb")
    assert bgr.shape == rgb.shape
    # same pixel data, red/blue channels swapped
    assert (bgr[..., 0] == rgb[..., 2]).all()
    assert (bgr[..., 2] == rgb[..., 0]).all()


def test_preprocess_rejects_unknown_color_mode(sample_image_path):
    with pytest.raises(ValueError, match="Unknown color_mode"):
        CVPreprocessor().preprocess(sample_image_path, color_mode="cmyk")
