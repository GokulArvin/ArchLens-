# Sprint 3 Detection Baseline (D15)

Model: yolov8n.pt (COCO-pretrained), confidence threshold 0.25, IoU threshold 0.5.

## Aggregate result (real, measured - not assumed)

- True positives: 0
- False positives: 0
- False negatives: 95
- Precision: 0.0000
- Recall: 0.0000
- F1: 0.0000

## Per-diagram results

| diagram | GT components | predicted | TP | FP | FN |
|---|---|---|---|---|---|
| gcp_microservices_demo | 12 | 0 | 0 | 0 | 12 |
| gcp_bank_of_anthos | 9 | 0 | 0 | 0 | 9 |
| dotnet_eshop | 11 | 0 | 0 | 0 | 11 |
| spring_petclinic_microservices | 14 | 0 | 0 | 0 | 14 |
| flask_microservice_demo | 4 | 0 | 0 | 0 | 4 |
| sock_shop | 10 | 0 | 0 | 0 | 10 |
| aws_retail_store_sample_app | 10 | 0 | 0 | 0 | 10 |
| azure_aks_store_demo | 9 | 0 | 0 | 0 | 9 |
| roman_bilyak_microservice_architecture | 12 | 0 | 0 | 0 | 12 |
| istio_bookinfo_derived | 4 | 0 | 0 | 0 | 4 |

## False positive inspection

None - the detector produced zero false positives (it mostly produced zero detections at all).

## True positive inspection (important caveat)

None.

## False negative inspection (summary - every undetected component had a ground-truth box the detector never found)

95 of 95 real ground-truth components were missed entirely.

## Interpretation

This confirms the D11/D12 hypothesis: a COCO-pretrained detector finds
almost nothing in architecture diagrams, because diagram components
(labeled boxes, arrows) share no visual vocabulary with COCO's
photograph-object classes.
No diagram in this dataset produced even a coincidental true positive.
The effective, semantically-meaningful recall of this baseline is 0/95.

This is the honest Sprint 3 baseline, not a target to beat by tuning
thresholds on this same set (that would violate the plan's "do not
tune on the final test set" rule). It motivates Sprint 4/5's planned
work: segmentation/region-cropping and CLIP zero-shot classification,
which don't depend on COCO's label vocabulary matching diagram content.