# Sprint 3 Detection Baseline (D15)

Model: yolov8n.pt (COCO-pretrained), confidence threshold 0.25, IoU threshold 0.5.

## Aggregate result (real, measured - not assumed)

- True positives: 1
- False positives: 4
- False negatives: 88
- Precision: 0.2000
- Recall: 0.0112
- F1: 0.0213

## Per-diagram results

| diagram | GT components | predicted | TP | FP | FN |
|---|---|---|---|---|---|
| gcp_microservices_demo | 12 | 0 | 0 | 0 | 12 |
| gcp_bank_of_anthos | 9 | 0 | 0 | 0 | 9 |
| dotnet_eshop | 11 | 0 | 0 | 0 | 11 |
| spring_petclinic_microservices | 14 | 0 | 0 | 0 | 14 |
| flask_microservice_demo | 4 | 0 | 0 | 0 | 4 |
| sock_shop | 10 | 0 | 0 | 0 | 10 |
| spring_cloud_brewery_overview | 8 | 5 | 1 | 4 | 7 |
| spring_cloud_brewery_dependency_graph | 5 | 0 | 0 | 0 | 5 |
| roman_bilyak_microservice_architecture | 12 | 0 | 0 | 0 | 12 |
| istio_bookinfo_derived | 4 | 0 | 0 | 0 | 4 |

## False positive inspection

- `spring_cloud_brewery_overview`: COCO class "umbrella" at confidence 0.54 - no matching real component at this location.
- `spring_cloud_brewery_overview`: COCO class "bottle" at confidence 0.47 - no matching real component at this location.
- `spring_cloud_brewery_overview`: COCO class "cake" at confidence 0.42 - no matching real component at this location.
- `spring_cloud_brewery_overview`: COCO class "sports ball" at confidence 0.29 - no matching real component at this location.

## True positive inspection (important caveat)

- `spring_cloud_brewery_overview`: COCO class "umbrella" (conf 0.25) spatially overlaps ground-truth component `maturing` at IoU>=0.5 - this is a coincidental spatial match, not a semantically meaningful detection ("umbrella" has nothing to do with the real component).

## False negative inspection (summary - every undetected component had a ground-truth box the detector never found)

88 of 89 real ground-truth components were missed entirely.

## Interpretation

This confirms the D11/D12 hypothesis: a COCO-pretrained detector finds
almost nothing in architecture diagrams, because diagram components
(labeled boxes, arrows) share no visual vocabulary with COCO's
photograph-object classes. The one diagram with real detections
(`spring_cloud_brewery_overview`) has illustrated 3D icons - a barrel,
bottles, boxes - that coincidentally resemble COCO objects, producing
false positives rather than useful detections. Even the single
true positive is a coincidental spatial overlap (see above), so the
effective, semantically-meaningful recall of this baseline is 0/89.

This is the honest Sprint 3 baseline, not a target to beat by tuning
thresholds on this same set (that would violate the plan's "do not
tune on the final test set" rule). It motivates Sprint 4/5's planned
work: segmentation/region-cropping and CLIP zero-shot classification,
which don't depend on COCO's label vocabulary matching diagram content.