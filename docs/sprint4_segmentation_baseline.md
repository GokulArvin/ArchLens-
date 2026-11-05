# Sprint 4: Segmentation Approach Decision (D16-D20)

> Re-run after two diagrams (`spring_cloud_brewery_overview`,
> `spring_cloud_brewery_dependency_graph`) were replaced with
> `aws_retail_store_sample_app` and `azure_aks_store_demo` - see
> `docs/dataset_candidates.md`. Every number below was re-measured.

## D16: Is pretrained segmentation viable?

Tested torchvision's Mask R-CNN (ResNet50-FPN, COCO-pretrained) against all
10 real diagrams (`experiments/baselines/sprint4_maskrcnn_feasibility.json`).
Result: **4 detections total across all 10 diagrams** (most diagrams: 0),
the same COCO-vocabulary mismatch documented for YOLOv8n in
`docs/yolo_classes.md` (Sprint 3) - Mask R-CNN shares the identical 80-class
COCO backbone/vocabulary. **Not viable.**

## D17 + D19: Region-cropping fallback, edge-assisted

Retained fallback: `RegionProposalSegmenter`
(`backend/app/modules/cv_pipeline/segmentation.py`) - classical,
pretrained-model-free:

1. Grayscale conversion.
2. Canny edge detection (**the edge map is an input feature that feeds
   region proposal, per D19 - it is never returned as the final output**).
3. Morphological closing to connect edge fragments into closed boundaries.
4. `cv2.findContours` + area-fraction filtering (drops near-zero-area noise
   and near-whole-image contours).
5. Returns bounding boxes + real contour polygons (an actual mask, not just
   a box) per proposal.

## D18: Comparison against ground truth (small subset)

Evaluated on 3 diagrams chosen for diversity (simplest, smallest-image, and
densest): `istio_bookinfo_derived`, `aws_retail_store_sample_app`,
`gcp_microservices_demo`. Real, measured result
(`experiments/baselines/sprint4_segmentation_baseline.json`), IoU threshold 0.5:

| diagram | GT | proposals | TP | FP | FN | precision | recall |
|---|---|---|---|---|---|---|---|
| istio_bookinfo_derived | 4 | 15 | 4 | 11 | 0 | 0.267 | 1.000 |
| aws_retail_store_sample_app | 10 | 32 | 10 | 22 | 0 | 0.312 | 1.000 |
| gcp_microservices_demo | 12 | 69 | 9 | 60 | 3 | 0.130 | 0.750 |

**Aggregate: P=0.198, R=0.885, F1=0.324** — far better than the
pretrained-detector baseline (YOLOv8n F1=0.000, Mask R-CNN not even
evaluated for P/R since it found almost nothing).

Honest failure case: `gcp_microservices_demo` has the subset's lowest
recall (0.750, missing 3 of 12 real components) despite also having by far
the most proposals (69) - its denser, more tightly-packed layout means some
real component boxes never get a single contour proposal at IoU>=0.5, even
though the method over-produces proposals elsewhere on the same image. This
is a genuine known limitation, not a bug - logged for Sprint 9's error
categorization (D44).

## D20: MVP decision

- **Dropped**: pretrained segmentation (Mask R-CNN) - empirically not
  viable, same root cause as Sprint 3's detector finding.
- **Retained**: `RegionProposalSegmenter` (edge-assisted contour region
  proposals) as the Sprint 4 MVP segmentation approach. It's a real
  improvement over both pretrained baselines, is lightweight (no model
  download, runs in milliseconds), and its over-segmentation (high recall,
  low precision) is a known, documented, honest trade-off rather than a
  hidden flaw - precision can be improved in later sprints (e.g. by
  cross-referencing with CLIP-based semantic filtering in Sprint 5).
