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

try:
    import cv2
except ImportError:
    cv2 = None
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseComponentDetector(ABC):
    """Abstract base class for all component-detection backends.

    Subclasses must implement detect(). Returns [] on any failure — never raises.
    DetectionResult dict shape: {bbox: [x1,y1,x2,y2], confidence: float, class_id: int, class_name: str}
    """

    @abstractmethod
    def detect(self, img: np.ndarray) -> List[Dict[str, Any]]:
        """Detect architectural components in a BGR uint8 image.

        Returns a list of DetectionResult dicts, or [] on any failure.
        """


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
        max_val = np.abs(result).max()
        if max_val == 0:
            return np.zeros_like(gray, dtype=np.uint8)
        return np.uint8(np.abs(result) / max_val * 255)

    def dog(
        self, img: np.ndarray, sigma1: float = 1.0, sigma2: float = 2.0
    ) -> np.ndarray:
        """Difference of Gaussians edge detection."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        g1 = cv2.GaussianBlur(gray, (0, 0), sigma1)
        g2 = cv2.GaussianBlur(gray, (0, 0), sigma2)
        dog_result = np.abs(g1 - g2)
        max_val = dog_result.max()
        if max_val == 0:
            return np.zeros_like(gray, dtype=np.uint8)
        return np.uint8(dog_result / max_val * 255)


class ComponentDetector(BaseComponentDetector):
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


class FasterRCNNDetector(BaseComponentDetector):
    """Faster R-CNN component detector using torchvision pretrained COCO weights.

    Lazy initialisation: model loaded on first detect() call.
    Graceful degradation: returns [] if torch/torchvision unavailable or weights fail.
    """

    # Standard 91-class COCO label map (torchvision order)
    COCO_CLASSES: List[str] = [
        "__background__", "person", "bicycle", "car", "motorcycle", "airplane",
        "bus", "train", "truck", "boat", "traffic light", "fire hydrant",
        "N/A", "stop sign", "parking meter", "bench", "bird", "cat", "dog",
        "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "N/A",
        "backpack", "umbrella", "N/A", "N/A", "handbag", "tie", "suitcase",
        "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat",
        "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
        "N/A", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana",
        "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza",
        "donut", "cake", "chair", "couch", "potted plant", "bed", "N/A",
        "dining table", "N/A", "N/A", "toilet", "N/A", "tv", "laptop", "mouse",
        "remote", "keyboard", "cell phone", "microwave", "oven", "toaster",
        "sink", "refrigerator", "N/A", "book", "clock", "vase", "scissors",
        "teddy bear", "hair drier", "toothbrush",
    ]

    def __init__(self, confidence: float = 0.5) -> None:
        self.confidence = confidence
        self._model = None
        self._init_attempted = False

    def _get_model(self):
        """Lazy-initialise Faster R-CNN. Returns None on any failure."""
        if self._model is None and not self._init_attempted:
            self._init_attempted = True
            try:
                import torch
                import torchvision
                weights = torchvision.models.detection.FasterRCNN_ResNet50_FPN_Weights.DEFAULT
                model = torchvision.models.detection.fasterrcnn_resnet50_fpn(weights=weights)
                model.eval()
                self._model = model
                logger.info("FasterRCNNDetector: model loaded (COCO pretrained)")
            except Exception as e:
                logger.warning(f"FasterRCNNDetector: model unavailable — {e}")
        return self._model

    def detect(self, img: np.ndarray) -> List[Dict[str, Any]]:
        """Run Faster R-CNN inference on a BGR uint8 image."""
        model = self._get_model()
        if model is None:
            return []
        try:
            import torch
            rgb = img[:, :, ::-1].copy()              # BGR → RGB
            tensor = rgb.astype(np.float32) / 255.0   # normalise to [0, 1]
            chw = np.transpose(tensor, (2, 0, 1))      # HWC → CHW
            t = torch.from_numpy(chw)

            with torch.no_grad():
                preds = model([t])[0]

            boxes  = preds["boxes"].cpu().numpy()
            labels = preds["labels"].cpu().numpy()
            scores = preds["scores"].cpu().numpy()

            results = []
            for box, label, score in zip(boxes, labels, scores):
                if float(score) >= self.confidence:
                    class_id = int(label)
                    class_name = (
                        self.COCO_CLASSES[class_id]
                        if class_id < len(self.COCO_CLASSES)
                        else str(class_id)
                    )
                    results.append({
                        "bbox":       [float(v) for v in box],
                        "confidence": float(score),
                        "class_id":   class_id,
                        "class_name": class_name,
                    })
            return results

        except Exception as e:
            logger.warning(f"FasterRCNNDetector.detect failed: {e}")
            return []


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
