# Sprint 5: ViT/Embedding Baseline & Geometric Relations (D21-D25)

## D21: CLIP (ViT-B/32) embedding baseline

`backend/app/modules/cv_pipeline/embeddings.py`, run over all 89 real
ground-truth component crops (`experiments/baselines/sprint5_embeddings_ocr.json`).

Real validation: average cosine similarity between same-`type` component
pairs (1,787 pairs) vs different-`type` pairs (2,129 pairs):

- Same-type: **0.6563**
- Different-type: **0.6444**

A small but real positive gap - CLIP (zero-shot, not fine-tuned on
architecture diagrams) carries *some* usable signal for distinguishing
component types, but it's weak. This matches expectations: CLIP was trained
on natural photos/web images, not on abstract labeled-box diagrams, so a
large separation wasn't expected. Worth revisiting with few-shot
fine-tuning or prompt-based CLIP zero-shot classification (the
`CLIPClassifier` already stubbed in `pipeline.py`) in a later sprint rather
than raw embedding similarity alone.

## D22: OCR text extraction

`backend/app/modules/cv_pipeline/ocr.py` (easyocr - no system Tesseract
binary available on this machine). Real result: OCR text matched the real
component label for **64/89 (71.9%)** of ground-truth crops - a genuinely
useful signal for future component naming/classification.

### Real failure categories (the 25 non-matches, inspected individually)

1. **Label text sits outside the annotated box, not inside it** (8 of 25 -
   `spring_cloud_brewery_overview`, `spring_cloud_brewery_dependency_graph`).
   These diagrams draw an icon with its label as separate text below/beside
   it; our bbox convention (drawn tightly around the icon) crops out the
   label entirely, so OCR correctly finds nothing. This is an annotation-
   convention mismatch, not an OCR failure - worth revisiting the bbox
   convention in a later annotation pass.
2. **OCR reads a real but different label inside the same box** (6 of 25 -
   `roman_bilyak_microservice_architecture`'s five services each have "API"
   printed as a sub-label alongside the real service name; one "pets-service"
   box's `<random port>` placeholder text beat out the component name).
   Not wrong, just a granularity mismatch between what's visually printed
   and what our manifest calls the component.
3. **OCR picks up a neighboring/overlapping label** (2 of 25 -
   `dotnet_eshop`'s "Order Service" box returned "PostareSQL", actually a
   nearby PostgreSQL icon's label bleeding into the crop).
4. **No text present in the crop at all** (OpenAI logo icon, Sock Shop's
   stick-figure "User" icon) - genuinely nothing to read; expected.
5. **Garbled low-confidence text on small/stylized crops** (`roman_bilyak`'s
   browser icon label, RabbitMQ icon) - real OCR limitation on small, busy,
   non-planar text regions.

## D23 + D24: Geometry-based relation candidates

`backend/app/modules/cv_pipeline/geometry_relations.py`: Hough line
detection on the Canny edge map, endpoints matched to the nearest component
box (within 40px). Matching against ground truth is **undirected**
(component-pair only) - a Hough line segment's two endpoints don't reliably
tell us which one is the arrowhead, so direction is out of scope for this
baseline (stated honestly rather than guessed).

Real result (`experiments/baselines/sprint5_geometry_relations.json`):

| diagram | GT edges | candidates | TP | FP | FN | P | R |
|---|---|---|---|---|---|---|---|
| gcp_microservices_demo | 16 | 13 | 11 | 2 | 5 | 0.846 | 0.688 |
| gcp_bank_of_anthos | 11 | 4 | 2 | 2 | 9 | 0.500 | 0.182 |
| dotnet_eshop | 14 | 14 | 5 | 9 | 9 | 0.357 | 0.357 |
| spring_petclinic_microservices | 22 | 12 | 10 | 2 | 12 | 0.833 | 0.455 |
| flask_microservice_demo | 4 | 3 | 3 | 0 | 1 | 1.000 | 0.750 |
| sock_shop | 9 | 4 | 3 | 1 | 6 | 0.750 | 0.333 |
| spring_cloud_brewery_overview | 8 | 2 | 2 | 0 | 6 | 1.000 | 0.250 |
| spring_cloud_brewery_dependency_graph | 4 | 0 | 0 | 0 | 4 | 0.000 | 0.000 |
| roman_bilyak_microservice_architecture | 17 | 16 | 13 | 3 | 4 | 0.812 | 0.765 |
| istio_bookinfo_derived | 3 | 3 | 3 | 0 | 0 | 1.000 | 1.000 |

**Aggregate: P=0.732, R=0.482, F1=0.581** - by far the strongest baseline in
the project so far (Sprint 3 detection F1=0.021, Sprint 4 segmentation
F1=0.220). This makes sense: connectors genuinely *are* straight/near-
straight lines, so a geometry-first approach is naturally well-matched to
this sub-problem in a way generic pretrained object detectors are not.

### Real relation failure categories

1. **Nested/grouped diagrams with long or occluded connectors**
   (`dotnet_eshop`, lowest precision at 0.357). Connectors cross container
   group boundaries (e.g. "Cloud Services" > "Aspire Orchestration") and get
   broken into multiple short Hough segments, or run parallel to a group
   border and get confused with it - 9 false positives, 9 false negatives.
2. **Sparse/simple diagrams with few real connectors catch real relations
   but not all of them** (`gcp_bank_of_anthos`, recall 0.182) - most edges
   run frontend-to-service in a fan-out pattern with long, thin lines that
   partially fall outside the 40px endpoint-matching tolerance at the
   frontend end (a wide box, so the geometric line terminus can land far
   from the box's matched point).
3. **No lines detected that survive filtering** (`spring_cloud_brewery_dependency_graph`,
   0 candidates despite 73 raw Hough lines) - this is the same small
   (924x154px) diagram flagged in Sprint 4's segmentation report; its tight
   ground-truth boxes and small connector arrows fall below reliable Hough
   detection at this scale.
4. **Clean, simple, self-derived diagrams score artificially well**
   (`istio_bookinfo_derived`, P=R=1.0) - this diagram was *rendered by us*
   (Sprint 1 D1, since Bookinfo ships no official diagram) with perfectly
   straight, unambiguous lines, so it's not representative of real-world
   diagram noise; it should not be read as "the method gets perfect
   results," only as a sanity check that the method works when conditions
   are ideal.
