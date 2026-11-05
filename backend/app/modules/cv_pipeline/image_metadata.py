"""Sprint 2 / D7: image-quality metadata for preprocessing input/output.

Computed on real images only - used by the batch preprocessing script and
the preprocessing comparison notebook to record genuine before/after
measurements (no fabricated numbers).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Optional

import cv2
import numpy as np


@dataclass
class ImageQualityMetadata:
    width: int
    height: int
    channels: int
    aspect_ratio: float
    mean_brightness: float
    blur_score: float  # variance of the Laplacian; higher = sharper/more detail
    file_size_bytes: Optional[int] = None
    file_format: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def compute_metadata(
    img: np.ndarray,
    image_path: Optional[str] = None,
    channel_order: Literal["bgr", "rgb", "gray"] = "bgr",
) -> ImageQualityMetadata:
    """Compute real quality metrics for an already-loaded image array."""
    if img.ndim == 2:
        gray = img
        channels = 1
    else:
        channels = img.shape[2]
        if channel_order == "bgr":
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        elif channel_order == "rgb":
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            raise ValueError(f"channel_order must be bgr/rgb for a multi-channel image, got {channel_order}")

    h, w = img.shape[:2]
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean_brightness = float(gray.mean())

    file_size_bytes = None
    file_format = None
    if image_path is not None:
        p = Path(image_path)
        if p.exists():
            file_size_bytes = p.stat().st_size
        file_format = p.suffix.lstrip(".").upper() or None

    return ImageQualityMetadata(
        width=w,
        height=h,
        channels=channels,
        aspect_ratio=round(w / h, 4),
        mean_brightness=round(mean_brightness, 2),
        blur_score=round(blur_score, 2),
        file_size_bytes=file_size_bytes,
        file_format=file_format,
    )
