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

        # Remove duplicate and strongly nested detections.
        # Larger boxes are considered first so that small contours
        # created by text/icons inside a component can be suppressed.
        candidates.sort(
            key=lambda item: (
                (item["bbox"][2] - item["bbox"][0]) *
                (item["bbox"][3] - item["bbox"][1])
            ),
            reverse=True
        )

        filtered = []

        for candidate in candidates:
            x1, y1, x2, y2 = candidate["bbox"]
            candidate_area = max(0, x2 - x1) * max(0, y2 - y1)

            is_duplicate = False

            for existing in filtered:
                ex1, ey1, ex2, ey2 = existing["bbox"]
                existing_area = (
                    max(0, ex2 - ex1) *
                    max(0, ey2 - ey1)
                )

                intersection_width = max(
                    0, min(x2, ex2) - max(x1, ex1)
                )

                intersection_height = max(
                    0, min(y2, ey2) - max(y1, ey1)
                )

                intersection = (
                    intersection_width * intersection_height
                )

                smaller_area = min(
                    candidate_area, existing_area
                )

                larger_area = max(
                    candidate_area, existing_area
                )

                overlap_over_smaller = (
                    intersection / smaller_area
                    if smaller_area > 0 else 0.0
                )

                iou = self._iou(
                    candidate["bbox"],
                    existing["bbox"]
                )

                # Suppress near-identical boxes or much smaller
                # boxes almost completely contained in larger boxes.
                strongly_nested = (
                    overlap_over_smaller >= 0.92
                    and larger_area > 0
                    and smaller_area / larger_area < 0.55
                )

                if iou >= 0.65 or strongly_nested:
                    is_duplicate = True
                    break

            if not is_duplicate:
                filtered.append(candidate)

        logger.info(
            "OpenCV contour detection: %d candidates, %d after filtering",
            len(candidates),
            len(filtered)
        )

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

class EasyOCRLabelReader:
    """Extract text labels and associate them with components."""

    def __init__(self, enabled=True, languages=None, gpu=False):
        self.enabled = enabled
        self.reader = None
        self.available = False

        if not enabled:
            logger.info("EasyOCR disabled")
            return

        try:
            import easyocr

            self.reader = easyocr.Reader(
                languages or ["en"],
                gpu=gpu
            )

            self.available = True
            logger.info("EasyOCR initialized successfully")

        except Exception as exc:
            logger.exception(
                "EasyOCR initialization failed: %s", exc
            )

    @staticmethod
    def _text_box_bounds(points):
        points = np.asarray(
            points, dtype=np.float32
        ).reshape(-1, 2)

        return [
            float(np.min(points[:, 0])),
            float(np.min(points[:, 1])),
            float(np.max(points[:, 0])),
            float(np.max(points[:, 1]))
        ]

    @staticmethod
    def _box_distance(box_a, box_b):
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b

        dx = max(bx1 - ax2, 0, ax1 - bx2)
        dy = max(by1 - ay2, 0, ay1 - by2)

        return float(np.hypot(dx, dy))

    def extract_and_assign(
        self,
        image,
        components,
        min_confidence=0.25,
        max_distance=45.0
    ):
        """Extract text and associate it with component bounding boxes."""

        if not self.available or not components:
            return {}

        try:
            rgb_image = cv2.cvtColor(
                image, cv2.COLOR_BGR2RGB
            )

            results = self.reader.readtext(
                rgb_image,
                detail=1,
                paragraph=False
            )

        except Exception as exc:
            logger.exception(
                "EasyOCR inference failed: %s", exc
            )
            return {}

        assigned = {
            component["id"]: []
            for component in components
        }

        for result in results:

            if len(result) < 3:
                continue

            polygon = result[0]
            text = str(result[1]).strip()
            confidence = float(result[2])

            if not text or confidence < min_confidence:
                continue

            text_box = self._text_box_bounds(polygon)

            tx = (text_box[0] + text_box[2]) / 2
            ty = (text_box[1] + text_box[3]) / 2

            containing = []

            # First, find components containing the text center.
            for component in components:

                bbox = component["bbox"]

                if (
                    bbox["x1"] <= tx <= bbox["x2"]
                    and bbox["y1"] <= ty <= bbox["y2"]
                ):
                    area = (
                        (bbox["x2"] - bbox["x1"])
                        * (bbox["y2"] - bbox["y1"])
                    )

                    containing.append(
                        (area, component)
                    )

            if containing:

                # Prefer the smallest containing component.
                target = min(
                    containing,
                    key=lambda item: item[0]
                )[1]

            else:

                # Otherwise, find the nearest component.
                distances = []

                for component in components:

                    bbox = component["bbox"]

                    distance = self._box_distance(
                        text_box,
                        [
                            bbox["x1"],
                            bbox["y1"],
                            bbox["x2"],
                            bbox["y2"]
                        ]
                    )

                    distances.append(
                        (distance, component)
                    )

                distance, target = min(
                    distances,
                    key=lambda item: item[0]
                )

                if distance > max_distance:
                    continue

            assigned[target["id"]].append({
                "text": text,
                "confidence": confidence,
                "bbox": [
                    round(value, 2)
                    for value in text_box
                ]
            })

        return {
            component_id: labels
            for component_id, labels in assigned.items()
            if labels
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
        
        # Initialize EasyOCR
        self.ocr_reader = EasyOCRLabelReader(
            enabled=self.config.get("enable_ocr", True),
            languages=self.config.get("ocr_languages", ["en"]),
            gpu=self.config.get("ocr_gpu", False)
        )  

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
            line_coordinates = np.asarray(line).reshape(-1)
            
            if line_coordinates.size != 4:
                continue
            
            x1, y1, x2, y2 = map(int, line_coordinates)

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
                    "note": (
                        "Possible connection; "
                        "arrow direction is unverified."
                    )
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

        # Stage 5: OCR label extraction and component naming.

        
        ocr_assignments = self.ocr_reader.extract_and_assign(
            img,
            components,
            min_confidence=self.config.get(
                "ocr_min_confidence", 0.25
            ),
            max_distance=self.config.get(
                "ocr_max_label_distance", 45.0
            )
        )

        for component in components:
            labels = ocr_assignments.get(
            component["id"], []
 )

            if labels:

            # Sort labels from top to bottom, then left to right.
                labels.sort(
                    key=lambda item: (
                        item["bbox"][1],
                        item["bbox"][0]
                    )
             )

                component["name"] = " ".join(
                    label["text"] for label in labels
            )

                component["metadata"]["ocr_labels"] = labels

                component["metadata"]["ocr_confidence"] = float(
                    sum(
                        label["confidence"]
                        for label in labels
            ) / len(labels)
        )

                component["metadata"]["name_source"] = "easyocr"

            else:

                component["metadata"]["name_source"] = (
                    "detector_fallback"
                )


        # Stage 6: Relationship candidates.

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
                "ocr_method": (
                    "easyocr"
                    if self.ocr_reader.available
                    else "unavailable"
                ),
                "ocr_enabled": self.ocr_reader.enabled,
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