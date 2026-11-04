"""
Sprint 5 / D22: OCR text extraction for cropped component regions.

Uses easyocr (pure Python/PyTorch, no system Tesseract binary required -
this machine has none installed) rather than pytesseract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

DEFAULT_MODEL_STORAGE_DIRECTORY = Path(__file__).resolve().parents[3] / "models" / "easyocr"


@dataclass
class OCRResult:
    text: str
    confidence: float
    bbox: list[list[float]]  # polygon, in the cropped region's local coordinates

    def to_dict(self) -> dict:
        return {"text": self.text, "confidence": self.confidence, "bbox": self.bbox}


class RegionOCR:
    def __init__(self, languages: list[str] | None = None, model_storage_directory: Path | str = DEFAULT_MODEL_STORAGE_DIRECTORY):
        import easyocr  # imported lazily - heavy, optional dependency

        self.reader = easyocr.Reader(
            languages or ["en"], gpu=False, model_storage_directory=str(model_storage_directory), verbose=False
        )

    def read_text(self, region_bgr: np.ndarray) -> list[OCRResult]:
        rgb = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2RGB)
        raw_results = self.reader.readtext(rgb)
        return [
            OCRResult(text=text, confidence=float(conf), bbox=[[float(x), float(y)] for x, y in box])
            for box, text, conf in raw_results
        ]

    def read_best_text(self, region_bgr: np.ndarray) -> OCRResult | None:
        results = self.read_text(region_bgr)
        if not results:
            return None
        return max(results, key=lambda r: r.confidence)
