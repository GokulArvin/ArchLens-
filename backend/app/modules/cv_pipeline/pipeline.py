
"""
ArchLens - Computer Vision Pipeline

Interim model-free architecture diagram analysis:
1. Image preprocessing
2. Canny edge detection
3. OpenCV contour-based component detection
4. CLIP zero-shot classification
5. Hough-line-based relationship candidates
6. Architecture graph generation
"""

import cv2
import numpy as np
import logging
import uuid

from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class CVPreprocessor:
    """Image loading, resizing and normalization."""

    def __init__(self, max_size: int = 1920):
        self.max_size = max_size

    def preprocess(self, image_path: str) -> np.ndarray:
        img = cv2.imread(image_path)

        if img is None:
            raise ValueError(f"Cannot load image: {image_path}")

        h, w = img.shape[:2]

        if max(h, w) > self.max_size:
            scale = self.max_size / max(h, w)
            img = cv2.resize(
                img,
                (int(w * scale), int(h * scale))
            )

        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8)
        )
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])

        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


class EdgeDetector:
    """Image edge detection."""

    def canny(self, img, low=50, high=150):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.Canny(gray, low, high)


class ComponentDetector:
    """
    Detect architecture component candidates.

    Uses YOLO when weights are provided.
    Otherwise uses OpenCV contour detection.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence: float = 0.5
    ):
        self.confidence = confidence
        self.model = None

        if model_path and Path(model_path).exists():
            self._load_model(model_path)

    def _load_model(self, model_path):
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            logger.info("YOLO model loaded: %s", model_path)
        except Exception as e:
            logger.warning("YOLO loading failed: %s", e)

    @staticmethod
    def _iou(box1, box2):
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        intersection = max(0, x2 - x1) * max(0, y2 - y1)

        area1 = (
            (box1[2] - box1[0]) *
            (box1[3] - box1[1])
        )
        area2 = (
            (box2[2] - box2[0]) *
            (box2[3] - box2[1])
        )

        union = area1 + area2 - intersection

        return intersection / union if union else 0

    def detect(self, img: np.ndarray) -> List[Dict[str, Any]]:

        # Use YOLO if a trained model is available.
        if self.model is not None:
            results = self.model(img, conf=self.confidence)
            detections = []

            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(
                        int, box.xyxy[0].tolist()
                    )

                    detections.append({
                        "bbox": [x1, y1, x2, y2],
                        "confidence": float(box.conf[0]),
                        "class_name": result.names[int(box.cls[0])]
                    })

            return detections

        # Fallback: OpenCV contour-based detection.
        logger.info(
            "YOLO weights unavailable. Using OpenCV detection."
        )

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(gray, 50, 150)

        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (3, 3)
        )

        closed = cv2.morphologyEx(
            edges, cv2.MORPH_CLOSE, kernel
        )

        contours, _ = cv2.findContours(
            closed,
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE
)

        image_area = img.shape[0] * img.shape[1]
        candidates = []

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h

            if area < image_area * 0.002:
                continue
            
            # Reject contours that cover too much of the diagram.
            if area > image_area * 0.15:
                continue

            if w < 35 or h < 25:
                continue

            if w / max(h, 1) > 8:
                continue

            if h / max(w, 1) > 8:
                continue

            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(
                contour, 0.03 * perimeter, True
            )

            # Keep reasonably simple closed shapes.
            if len(approx) < 4 or len(approx) > 10:
                continue

            candidates.append({
                "bbox": [x, y, x + w, y + h],
                "confidence": 0.5,
                "class_name": "architecture_component"
            })

        # Remove heavily overlapping detections.
        candidates.sort(
            key=lambda item: (
                (item["bbox"][2] - item["bbox"][0]) *
                (item["bbox"][3] - item["bbox"][1])
            ),
            reverse=True
        )

        filtered = []

        for candidate in candidates:
            if all(
                self._iou(candidate["bbox"], existing["bbox"]) < 0.65
                for existing in filtered
            ):
                filtered.append(candidate)

        return filtered


class CLIPClassifier:
    """CLIP zero-shot architecture component classification."""

    COMPONENT_PROMPTS = [
        "a database component in a software architecture diagram",
        "a backend service or microservice in a software architecture diagram",
        "a message queue or event bus in a software architecture diagram",
        "an API gateway in a software architecture diagram",
        "a frontend or user interface in a software architecture diagram",
        "a cache or memory store in a software architecture diagram",
        "an external system in a software architecture diagram",
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
        self.device = "cpu"
        self._load_clip()

    def _load_clip(self):
        try:
            import clip
            import torch

            self.device = (
                "cuda" if torch.cuda.is_available() else "cpu"
            )

            self.model, self.preprocess_fn = clip.load(
                "ViT-B/32",
                device=self.device
            )

            logger.info("CLIP loaded on %s", self.device)

        except Exception as e:
            logger.warning("CLIP unavailable: %s", e)

    def classify(self, region: np.ndarray) -> Dict[str, float]:

        if self.model is None:
            return {
                value: 0.0
                for value in self.COMPONENT_TYPE_MAP.values()
            }

        import clip
        import torch
        from PIL import Image

        if region.size == 0:
            return {
                value: 0.0
                for value in self.COMPONENT_TYPE_MAP.values()
            }

        pil_img = Image.fromarray(
            cv2.cvtColor(region, cv2.COLOR_BGR2RGB)
        )

        image_input = (
            self.preprocess_fn(pil_img)
            .unsqueeze(0)
            .to(self.device)
        )

        text_tokens = clip.tokenize(
            self.COMPONENT_PROMPTS
        ).to(self.device)

        with torch.no_grad():
            logits, _ = self.model(image_input, text_tokens)
            probabilities = (
                logits.softmax(dim=-1).cpu().numpy()[0]
            )

        return {
            self.COMPONENT_TYPE_MAP[i]: float(probabilities[i])
            for i in range(len(self.COMPONENT_PROMPTS))
        }


class CVPipeline:
    """Main architecture diagram analysis pipeline."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None
    ):
        self.config = config or {}

        self.preprocessor = CVPreprocessor(
            max_size=self.config.get("max_image_size", 1920)
        )

        self.edge_detector = EdgeDetector()

        self.component_detector = ComponentDetector(
            model_path=self.config.get("yolo_model_path"),
            confidence=self.config.get("confidence", 0.5)
        )

        self.clip_classifier = CLIPClassifier()
        
    
    @staticmethod
    def _point_rect_distance(point, bbox):
        x, y = point

        if isinstance(bbox, dict):
            x1 = bbox["x1"]
            y1 = bbox["y1"]
            x2 = bbox["x2"]
            y2 = bbox["y2"]
        else:
            x1, y1, x2, y2 = bbox

        dx = max(x1 - x, 0, x - x2)
        dy = max(y1 - y, 0, y - y2)

        return float(np.hypot(dx, dy))

    def _extract_relationships(self, components, edges):
        """Extract possible geometric connections between components."""

        if len(components) < 2:
            return []

        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=40,
            minLineLength=25,
            maxLineGap=15
        )

        if lines is None:
            return []

        relationships = []
        seen = set()

        for line in lines:
            x1, y1, x2, y2 = map(int, line[0])

            endpoint1 = (x1, y1)
            endpoint2 = (x2, y2)

            nearest1 = None
            nearest2 = None
            distance1 = float("inf")
            distance2 = float("inf")

            for component in components:
                bbox = component["bbox"]

                d1 = self._point_rect_distance(endpoint1, bbox)
                d2 = self._point_rect_distance(endpoint2, bbox)

                if d1 < distance1:
                    distance1 = d1
                    nearest1 = component

                if d2 < distance2:
                    distance2 = d2
                    nearest2 = component

            if (
                nearest1 is None
                or nearest2 is None
                or nearest1["id"] == nearest2["id"]
                or distance1 > 25
                or distance2 > 25
            ):
                continue

            pair = tuple(sorted((
                nearest1["id"],
                nearest2["id"]
            )))

            if pair in seen:
                continue

            seen.add(pair)

            relationships.append({
                "id": str(uuid.uuid4()),
                "source": nearest1["id"],
                "target": nearest2["id"],
                "type": "depends_on",
                "confidence": 0.3,
                "metadata": {
                    "extraction_method": "hough_line_candidate",
                    "direction_verified": False,
                    "note": "Possible connection; arrow direction is unverified."
                }
            })

        return relationships


    def analyze(self, image_path: str) -> Dict[str, Any]:

        logger.info("Starting diagram analysis: %s", image_path)

        # Stage 1: Preprocessing.
        img = self.preprocessor.preprocess(image_path)

        # Stage 2: Edge detection.
        edges = self.edge_detector.canny(img)

        # Stage 3: Component detection.
        detections = self.component_detector.detect(img)

        components = []

        for detection in detections:

            x1, y1, x2, y2 = map(
                int, detection["bbox"]
            )

            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(img.shape[1], x2)
            y2 = min(img.shape[0], y2)

            region = img[y1:y2, x1:x2]

            if region.size == 0:
                continue

            # Stage 4: CLIP classification.
            scores = self.clip_classifier.classify(region)

            if scores and max(scores.values()) > 0:
                component_type = max(
                    scores, key=scores.get
                )
                classification_confidence = scores[component_type]
            else:
                component_type = "unknown"
                classification_confidence = 0.0

            component_id = str(uuid.uuid4())

            components.append({
                "id": component_id,
                "name": detection.get(
                    "class_name", "unknown"
                ),
                "type": component_type,
                "bbox": {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2
                },
                "confidence": float(
                    detection.get("confidence", 0.0)
                ),
                "metadata": {
                    "classification_confidence":
                        float(classification_confidence),
                    "clip_scores": scores,
                    "detection_method": (
                        "yolo" if self.component_detector.model
                        else "opencv_contours"
                    )
                }
            })

        # Stage 5: Relationship candidates.
        relationships = self._extract_relationships(
            components, edges
        )

        # Stage 6: Build schema-compatible graph.
        result = {
            "id": str(uuid.uuid4()),
            "name": Path(image_path).stem,
            "graph_type": "intended",
            "source": image_path,
            "components": components,
            "relationships": relationships,
            "metadata": {
                "detection_method": (
                    "yolo" if self.component_detector.model
                    else "opencv_contours"
                ),
                "relationship_method": "hough_lines",
                "is_interim_detector": (
                    self.component_detector.model is None
                )
            }
        }

        logger.info(
            "Analysis complete: %d components, %d relationships",
            len(components),
            len(relationships)
        )

        return result

    
@staticmethod
def _point_rect_distance(point, bbox):
    x, y = point

    # Support dictionary and list bounding boxes.
    if isinstance(bbox, dict):
        x1 = bbox["x1"]
        y1 = bbox["y1"]
        x2 = bbox["x2"]
        y2 = bbox["y2"]
    else:
        x1, y1, x2, y2 = bbox

    dx = max(x1 - x, 0, x - x2)
    dy = max(y1 - y, 0, y - y2)

    return float(np.hypot(dx, dy))

def _extract_relationships(
        self,
        components: List[Dict[str, Any]],
        edges: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        Find possible connections between component regions.

        These are geometric candidates, not verified arrow directions.
        """

        if len(components) < 2:
            return []

        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=40,
            minLineLength=25,
            maxLineGap=15
        )

        if lines is None:
            return []

        relationships = []
        seen = set()

        for line in lines:
            x1, y1, x2, y2 = map(
                int, line[0]
            )

            endpoint1 = (x1, y1)
            endpoint2 = (x2, y2)

            nearest1 = None
            nearest2 = None
            distance1 = float("inf")
            distance2 = float("inf")

            for component in components:
                bbox = component["bbox"]

                d1 = self._point_rect_distance(
                    endpoint1, bbox
                )
                d2 = self._point_rect_distance(
                    endpoint2, bbox
                )

                if d1 < distance1:
                    distance1 = d1
                    nearest1 = component

                if d2 < distance2:
                    distance2 = d2
                    nearest2 = component

            # Require both endpoints to be near distinct components.
            if (
                nearest1 is None
                or nearest2 is None
                or nearest1["id"] == nearest2["id"]
                or distance1 > 25
                or distance2 > 25
            ):
                continue

            pair = tuple(sorted((
                nearest1["id"],
                nearest2["id"]
            )))

            if pair in seen:
                continue

            seen.add(pair)

            relationships.append({
                "id": str(uuid.uuid4()),
                "source": nearest1["id"],
                "target": nearest2["id"],
                "type": "depends_on",
                "confidence": 0.3,
                "metadata": {
                    "extraction_method": "hough_line_candidate",
                    "direction_verified": False,
                    "note": (
                        "Possible geometric connection; "
                        "arrow direction has not been verified."
                    )
                }
            })

        return relationships
