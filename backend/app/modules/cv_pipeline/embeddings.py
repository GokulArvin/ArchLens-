"""
Sprint 5 / D21: an image-embedding baseline using pretrained weights.

Wraps CLIP's (ViT-B/32) pretrained image encoder to embed cropped component
regions. This is the "ViT or image-embedding baseline" the sprint asks for -
CLIP's vision tower *is* a ViT, so one model serves both roles (and matches
the ViT-B/32 already referenced in pipeline.py's CLIPClassifier).
"""

from __future__ import annotations

from pathlib import Path

try:
    import cv2
except ImportError:
    cv2 = None
import numpy as np

try:
    import torch
except ImportError:
    torch = None

from PIL import Image

DEFAULT_MODEL_NAME = "ViT-B/32"
DEFAULT_DOWNLOAD_ROOT = Path(__file__).resolve().parents[3] / "models" / "clip"


class ComponentEmbedder:
    """Pretrained CLIP image encoder, used as a fixed feature extractor."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, download_root: Path | str = DEFAULT_DOWNLOAD_ROOT):
        if torch is None:
            raise RuntimeError("torch is required to instantiate ComponentEmbedder.")
        import clip  # imported lazily - heavy, optional dependency

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, self.preprocess_fn = clip.load(model_name, device=self.device, download_root=str(download_root))
        self.model.eval()

    def embed_region(self, region_bgr: np.ndarray) -> list[float]:
        """Embed a cropped BGR region into CLIP's normalized embedding space."""
        if torch is None or cv2 is None:
            raise RuntimeError("torch and cv2 are required for embed_region.")
        pil_img = Image.fromarray(cv2.cvtColor(region_bgr, cv2.COLOR_BGR2RGB))
        image_input = self.preprocess_fn(pil_img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            features = self.model.encode_image(image_input)
            features = features / features.norm(dim=-1, keepdim=True)
        return features.squeeze(0).cpu().tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr, b_arr = np.array(a), np.array(b)
    denom = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    return float(np.dot(a_arr, b_arr) / denom) if denom else 0.0
