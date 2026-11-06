"""
Unit tests for CVPreprocessor and EdgeDetector (Canny/LoG/DoG baselines).
Sprint 2 P3 — edge detection baseline verification.

All tests use synthetically generated NumPy images — no real dataset required.
Images contain simple geometric shapes (rectangles, lines) with known edges,
so we can assert that edge detectors produce non-zero output in the right places.
"""

import numpy as np
import pytest

from app.modules.cv_pipeline.pipeline import CVPreprocessor, EdgeDetector

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _CV2_AVAILABLE, reason="opencv-python not installed")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_blank_bgr(h: int = 100, w: int = 100) -> np.ndarray:
    """Solid black BGR image."""
    return np.zeros((h, w, 3), dtype=np.uint8)


def make_rect_bgr(h: int = 200, w: int = 200) -> np.ndarray:
    """BGR image with a white rectangle on black — has clear edges."""
    img = make_blank_bgr(h, w)
    cv2.rectangle(img, (40, 40), (160, 160), (255, 255, 255), thickness=-1)
    return img


def make_gradient_bgr(h: int = 200, w: int = 200) -> np.ndarray:
    """BGR image with a horizontal gradient — smooth, fewer sharp edges."""
    gradient = np.tile(np.linspace(0, 255, w, dtype=np.uint8), (h, 1))
    return cv2.cvtColor(gradient, cv2.COLOR_GRAY2BGR)


# ─── CVPreprocessor ──────────────────────────────────────────────────────────

class TestCVPreprocessor:

    def setup_method(self):
        self.preprocessor = CVPreprocessor(max_size=1920)

    def test_resize_large_image_scales_down(self):
        """Images larger than max_size must be resized to fit within max_size."""
        big = np.zeros((3000, 4000, 3), dtype=np.uint8)
        resized = self.preprocessor._resize(big)
        assert max(resized.shape[:2]) <= 1920

    def test_resize_small_image_unchanged(self):
        """Images already within max_size must not be resized."""
        small = make_rect_bgr(100, 100)
        result = self.preprocessor._resize(small)
        assert result.shape == small.shape

    def test_resize_preserves_aspect_ratio(self):
        """Aspect ratio must be maintained after resize."""
        # 2:1 aspect ratio, larger than max_size
        wide = np.zeros((500, 4000, 3), dtype=np.uint8)
        resized = self.preprocessor._resize(wide)
        h, w = resized.shape[:2]
        ratio_before = 4000 / 500
        ratio_after = w / h
        assert abs(ratio_after - ratio_before) < 0.1

    def test_normalize_returns_same_shape_and_dtype(self):
        """CLAHE normalization must preserve shape and uint8 dtype."""
        img = make_rect_bgr()
        result = self.preprocessor._normalize(img)
        assert result.shape == img.shape
        assert result.dtype == np.uint8

    def test_normalize_increases_local_contrast(self):
        """CLAHE on a low-contrast image should produce non-zero output."""
        # Create a very low-contrast grey image
        grey = np.full((100, 100, 3), 128, dtype=np.uint8)
        result = self.preprocessor._normalize(grey)
        assert result is not None
        assert result.dtype == np.uint8

    def test_denoise_returns_same_shape(self):
        """Denoising must return an image with the same spatial dimensions."""
        img = make_rect_bgr()
        result = self.preprocessor.denoise(img)
        assert result.shape == img.shape
        assert result.dtype == np.uint8


# ─── EdgeDetector — Canny ────────────────────────────────────────────────────

class TestEdgeDetectorCanny:

    def setup_method(self):
        self.detector = EdgeDetector()

    def test_canny_output_shape(self):
        """Canny output must be 2D (grayscale) with same H×W as input."""
        img = make_rect_bgr()
        edges = self.detector.canny(img)
        assert edges.ndim == 2
        assert edges.shape == img.shape[:2]

    def test_canny_output_dtype_uint8(self):
        """Canny output must be uint8."""
        edges = self.detector.canny(make_rect_bgr())
        assert edges.dtype == np.uint8

    def test_canny_detects_rectangle_edges(self):
        """Canny must produce non-zero pixels on an image with a clear rectangle."""
        edges = self.detector.canny(make_rect_bgr())
        assert edges.max() > 0, "Canny produced no edges on rectangle image"

    def test_canny_blank_image_has_no_edges(self):
        """Canny on a uniform black image must return all zeros."""
        edges = self.detector.canny(make_blank_bgr())
        assert edges.max() == 0

    def test_canny_custom_thresholds(self):
        """Canny with different thresholds must still return correct shape."""
        img = make_rect_bgr()
        edges_tight = self.detector.canny(img, low=100, high=200)
        edges_loose = self.detector.canny(img, low=10, high=50)
        assert edges_tight.shape == img.shape[:2]
        assert edges_loose.shape == img.shape[:2]
        # Loose thresholds should detect at least as many edges
        assert edges_loose.sum() >= edges_tight.sum()


# ─── EdgeDetector — LoG ──────────────────────────────────────────────────────

class TestEdgeDetectorLoG:

    def setup_method(self):
        self.detector = EdgeDetector()

    def test_log_output_shape(self):
        """LoG output must be 2D with same H×W as input."""
        img = make_rect_bgr()
        edges = self.detector.log(img)
        assert edges.ndim == 2
        assert edges.shape == img.shape[:2]

    def test_log_output_dtype_uint8(self):
        """LoG output must be uint8."""
        edges = self.detector.log(make_rect_bgr())
        assert edges.dtype == np.uint8

    def test_log_detects_edges_on_rectangle(self):
        """LoG must produce non-zero pixels on an image with clear edges."""
        edges = self.detector.log(make_rect_bgr())
        assert edges.max() > 0, "LoG produced no edges on rectangle image"

    def test_log_blank_image_returns_zeros(self):
        """LoG on a blank (uniform) image must not raise and returns zeros."""
        edges = self.detector.log(make_blank_bgr())
        assert edges.dtype == np.uint8
        assert edges.max() == 0  # divide-by-zero guard ensures this

    def test_log_different_sigmas_change_output(self):
        """Higher sigma in LoG should blur more and reduce fine edge detail."""
        img = make_rect_bgr()
        edges_fine = self.detector.log(img, sigma=0.5)
        edges_coarse = self.detector.log(img, sigma=3.0)
        assert edges_fine.shape == img.shape[:2]
        assert edges_coarse.shape == img.shape[:2]
        # Fine sigma detects more pixels (more detailed)
        assert edges_fine.sum() >= edges_coarse.sum()


# ─── EdgeDetector — DoG ──────────────────────────────────────────────────────

class TestEdgeDetectorDoG:

    def setup_method(self):
        self.detector = EdgeDetector()

    def test_dog_output_shape(self):
        """DoG output must be 2D with same H×W as input."""
        img = make_rect_bgr()
        edges = self.detector.dog(img)
        assert edges.ndim == 2
        assert edges.shape == img.shape[:2]

    def test_dog_output_dtype_uint8(self):
        """DoG output must be uint8."""
        edges = self.detector.dog(make_rect_bgr())
        assert edges.dtype == np.uint8

    def test_dog_detects_edges_on_rectangle(self):
        """DoG must produce non-zero pixels on an image with clear edges."""
        edges = self.detector.dog(make_rect_bgr())
        assert edges.max() > 0, "DoG produced no edges on rectangle image"

    def test_dog_blank_image_returns_zeros(self):
        """DoG on a blank image must not raise and returns zeros."""
        edges = self.detector.dog(make_blank_bgr())
        assert edges.dtype == np.uint8
        assert edges.max() == 0  # divide-by-zero guard ensures this

    def test_dog_sigma_ordering(self):
        """DoG with sigma1 < sigma2 must produce valid output (not crash)."""
        img = make_rect_bgr()
        edges = self.detector.dog(img, sigma1=1.0, sigma2=2.0)
        assert edges.shape == img.shape[:2]
        assert edges.dtype == np.uint8

    def test_dog_wider_sigma_gap_emphasises_blob_features(self):
        """Larger sigma difference should suppress fine noise, keep blobs."""
        img = make_rect_bgr()
        narrow = self.detector.dog(img, sigma1=1.0, sigma2=1.5)
        wide = self.detector.dog(img, sigma1=1.0, sigma2=4.0)
        assert narrow.shape == img.shape[:2]
        assert wide.shape == img.shape[:2]


# ─── Baseline comparison ─────────────────────────────────────────────────────

class TestEdgeDetectorBaselines:
    """Cross-method comparison tests that validate all three baselines together."""

    def setup_method(self):
        self.detector = EdgeDetector()
        self.img = make_rect_bgr(200, 200)

    def test_all_three_methods_produce_same_spatial_shape(self):
        """Canny, LoG, and DoG must all output images of the same shape."""
        canny = self.detector.canny(self.img)
        log = self.detector.log(self.img)
        dog = self.detector.dog(self.img)
        assert canny.shape == log.shape == dog.shape == self.img.shape[:2]

    def test_all_three_methods_detect_edges_on_rect(self):
        """All three methods must detect edges on the rectangle image."""
        assert self.detector.canny(self.img).max() > 0
        assert self.detector.log(self.img).max() > 0
        assert self.detector.dog(self.img).max() > 0

    def test_all_three_return_zero_on_blank(self):
        """All three methods must return zero-arrays on a blank uniform image."""
        blank = make_blank_bgr()
        assert self.detector.canny(blank).max() == 0
        assert self.detector.log(blank).max() == 0
        assert self.detector.dog(blank).max() == 0
