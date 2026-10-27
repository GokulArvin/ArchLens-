"""
Module B: Computer Vision Pipeline
Converts architecture diagrams → structured architectural intent (G_I)

Stages:
1. Preprocessing (resize, normalize, denoise)
2. Edge detection (Canny/LoG/DoG baselines)
3. Component detection (YOLO)
4. Segmentation (U-Net)
5. ViT semantic understanding
6. CLIP zero-shot classification
7. Few-shot adaptation
8. Relationship extraction
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CVPreprocessor:
    """Stage 1: Image preprocessing pipeline."""

    def __init__(self, max_size: int = 1920):
        self.max_size = max_size

    def preprocess(self, image_path: str) -> np.ndarray:
        """Load and preprocess an architecture diagram image."""
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot load image: {image_path}")

        # Resize maintaining aspect ratio
        img = self._resize(img)
        # Normalize
        img = self._normalize(img)
        logger.info(f"Preprocessed image: {image_path} → shape {img.shape}")
        return img

    def _resize(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        if max(h, w) > self.max_size:
            scale = self.max_size / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        return img

    def _normalize(self, img: np.ndarray) -> np.ndarray:
        # CLAHE for contrast enhancement
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def denoise(self, img: np.ndarray) -> np.ndarray:
        return cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)


class EdgeDetector:
    """Stage 2: Edge detection baselines (Canny, LoG, DoG)."""

    def canny(self, img: np.ndarray, low: int = 50, high: int = 150) -> np.ndarray:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.Canny(gray, low, high)

    def log(self, img: np.ndarray, sigma: float = 1.0) -> np.ndarray:
        """Laplacian of Gaussian edge detection."""
        from scipy.ndimage import gaussian_laplace
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        result = gaussian_laplace(gray, sigma=sigma)
        return np.uint8(np.abs(result) / np.abs(result).max() * 255)

    def dog(
        self, img: np.ndarray, sigma1: float = 1.0, sigma2: float = 2.0
    ) -> np.ndarray:
        """Difference of Gaussians edge detection."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        g1 = cv2.GaussianBlur(gray, (0, 0), sigma1)
        g2 = cv2.GaussianBlur(gray, (0, 0), sigma2)
        dog = np.abs(g1 - g2)
        return np.uint8(dog / dog.max() * 255)


class ComponentDetector:
    """Stage 3: YOLO-based component detection."""

    def __init__(self, model_path: Optional[str] = None, confidence: float = 0.5):
        self.confidence = confidence
        self.model = None
        if model_path:
            self._load_model(model_path)

    def _load_model(self, model_path: str):
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            logger.info(f"YOLO model loaded from {model_path}")
        except Exception as e:
            logger.warning(f"Could not load YOLO model: {e}. Using placeholder.")

    def detect(self, img: np.ndarray) -> List[Dict[str, Any]]:
        """Detect architectural components in the image."""
        if self.model is None:
            logger.warning("No YOLO model loaded — returning empty detections.")
            return []

        results = self.model(img, conf=self.confidence)
        detections = []
        for r in results:
            for box in r.boxes:
                detections.append({
                    "bbox": box.xyxy[0].tolist(),
                    "confidence": float(box.conf[0]),
                    "class_id": int(box.cls[0]),
                    "class_name": r.names[int(box.cls[0])],
                })
        return detections


class CLIPClassifier:
    """Stage 6: CLIP zero-shot component classification."""

    COMPONENT_PROMPTS = [
        "a database component",
        "a web service or microservice",
        "a message queue or event bus",
        "an API gateway",
        "a frontend or user interface",
        "a cache or memory store",
        "an external system or third-party",
    ]

    COMPONENT_TYPE_MAP = {
        0: "database",
        1: "service",
        2: "queue",
        3: "gateway",
        4: "frontend",
        5: "cache",
        6: "external",
    }

    def __init__(self):
        self.model = None
        self.preprocess_fn = None
        self._load_clip()

    def _load_clip(self):
        try:
            import clip
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model, self.preprocess_fn = clip.load("ViT-B/32", device=device)
            self.device = device
            logger.info("CLIP model loaded successfully")
        except Exception as e:
            logger.warning(f"CLIP not available: {e}")

    def classify(self, region: np.ndarray) -> Dict[str, float]:
        """Classify a component region using CLIP zero-shot."""
        if self.model is None:
            return {t: 0.0 for t in self.COMPONENT_TYPE_MAP.values()}

        import clip
        import torch
        from PIL import Image

        pil_img = Image.fromarray(cv2.cvtColor(region, cv2.COLOR_BGR2RGB))
        image_input = self.preprocess_fn(pil_img).unsqueeze(0).to(self.device)
        text_tokens = clip.tokenize(self.COMPONENT_PROMPTS).to(self.device)

        with torch.no_grad():
            logits_per_image, _ = self.model(image_input, text_tokens)
            probs = logits_per_image.softmax(dim=-1).cpu().numpy()[0]

        return {
            self.COMPONENT_TYPE_MAP[i]: float(probs[i])
            for i in range(len(self.COMPONENT_PROMPTS))
        }


class CVPipeline:
    """
    Main CV pipeline orchestrator.
    Converts architecture diagram → G_I (intended architecture graph).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.preprocessor = CVPreprocessor()
        self.edge_detector = EdgeDetector()
        self.component_detector = ComponentDetector(
            model_path=self.config.get("yolo_model_path"),
            confidence=self.config.get("confidence", 0.5),
        )
        self.clip_classifier = CLIPClassifier()

    def analyze(self, image_path: str) -> Dict[str, Any]:
        """
        Full pipeline: image → components + relationships dict.
        Returns data matching the ArchGraph schema.
        """
        logger.info(f"Starting CV pipeline for: {image_path}")

        # Stage 1: Preprocess
        img = self.preprocessor.preprocess(image_path)

        # Stage 2: Edge detection
        edges = self.edge_detector.canny(img)

        # Stage 3: Component detection
        raw_detections = self.component_detector.detect(img)

        # Stage 6: CLIP classification on each detected region
        components = []
        for det in raw_detections:
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            region = img[y1:y2, x1:x2]
            clip_scores = self.clip_classifier.classify(region)
            comp_type = max(clip_scores, key=clip_scores.get)

            components.append({
                "name": det.get("class_name", "unknown"),
                "type": comp_type,
                "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                "confidence": det["confidence"],
                "clip_scores": clip_scores,
            })

        # Stage 8: Relationship extraction (geometry-based placeholder)
        relationships = self._extract_relationships(components, edges)

        result = {
            "graph_type": "intended",
            "source": image_path,
            "components": components,
            "relationships": relationships,
        }
        logger.info(
            f"CV pipeline complete: {len(components)} components, "
            f"{len(relationships)} relationships"
        )
        return result

    def _extract_relationships(
        self,
        components: List[Dict],
        edges: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """
        Placeholder: geometry-based relationship extraction.
        Full implementation in Sprint 5.
        """
        # TODO: use Hough lines + component proximity + VLM to extract arrows
        return []
