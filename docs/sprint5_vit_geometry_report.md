# Sprint 5: ViT/Embedding Baseline & Geometric Relations (D21-D25)

> Re-run after two diagrams (`spring_cloud_brewery_overview`,
> `spring_cloud_brewery_dependency_graph`) were replaced with
> `aws_retail_store_sample_app` and `azure_aks_store_demo` - see
> `docs/dataset_candidates.md`. Every number below was re-measured.

## D21: CLIP (ViT-B/32) embedding baseline

`backend/app/modules/cv_pipeline/embeddings.py`, run over all 95 real
ground-truth component crops (`experiments/baselines/sprint5_embeddings_ocr.json`).

Real validation: average cosine similarity between same-`type` component
pairs (1,770 pairs) vs different-`type` pairs (2,695 pairs):

- Same-type: **0.6469**
- Different-type: **0.6122**

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
component label for **79/95 (83.2%)** of ground-truth crops - a genuinely
useful signal for future component naming/classification.

### Real failure categories (the 16 non-matches, inspected individually)

1. **OCR reads a real but different label inside the same box** (8 of 16 -
   `roman_bilyak_microservice_architecture`'s five services each have "API"
   printed as a sub-label alongside the real service name; `spring_petclinic`'s
   gateway/pets-service boxes show a live `<port 8080>`/`<random port>`
   placeholder instead of the service name; `dotnet_eshop`'s "Webhooks
   Service" box returned "Webhook Client", a related but distinct label
   drawn nearby in the same diagram). Not wrong, just a granularity mismatch
   between what's visually printed and what our manifest calls the component.
2. **No text present in the crop at all** (2 of 16 - `dotnet_eshop`'s OpenAI
   logo icon, Sock Shop's stick-figure "User" icon) - genuinely nothing to
   read; expected.
3. **Short label text too small to read reliably** (1 of 16 -
   `aws_retail_store_sample_app`'s "UI" node - a 2-character label inside a
   76px circle on a 524x543 image falls below easyocr's reliable detection
   size, even though the text is genuinely present).
4. **OCR picks up a neighboring/overlapping label** (1 of 16 -
   `dotnet_eshop`'s "Order Service" box returned "PostareSQL", actually a
   nearby PostgreSQL icon's label bleeding into the crop).
5. **Garbled low-confidence text on small/stylized crops** (4 of 16 -
   `azure_aks_store_demo`'s "Customers" actor read as "Cuctome" and
   "makeline-service" read as a stray "0" from its Go-gopher icon;
   `roman_bilyak`'s browser icon label read as "nips Mlocalnost", RabbitMQ
   icon read as "]") - real OCR limitation on small, busy, non-planar text
   or icon regions.

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
| aws_retail_store_sample_app | 10 | 8 | 6 | 2 | 4 | 0.750 | 0.600 |
| azure_aks_store_demo | 9 | 1 | 1 | 0 | 8 | 1.000 | 0.111 |
| roman_bilyak_microservice_architecture | 17 | 16 | 13 | 3 | 4 | 0.812 | 0.765 |
| istio_bookinfo_derived | 3 | 3 | 3 | 0 | 0 | 1.000 | 1.000 |

**Aggregate: P=0.731, R=0.496, F1=0.591** - by far the strongest baseline in
the project so far (Sprint 3 detection F1=0.000, Sprint 4 segmentation
F1=0.324). This makes sense: connectors genuinely *are* straight/near-
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
3. **Curved connectors defeat straight-line Hough detection**
   (`azure_aks_store_demo`, recall 0.111 - only 1 of 9 real edges recovered).
   This diagram's connectors are drawn as smooth bezier curves rather than
   straight segments (e.g. the curved lines from `store-front` fanning out
   to `order-service`/`product-service`, and from `order-service`/
   `makeline-service` into the shared `Order Queue`); `cv2.HoughLinesP`
   is built to find straight lines, so a curve only contributes short,
   fragmented segments that rarely both land within 40px of the correct
   component boxes. This is a genuine, honest limitation of a Hough-line-
   based approach, not a tuning issue.
4. **Clean, simple, self-derived diagrams score artificially well**
   (`istio_bookinfo_derived`, P=R=1.0) - this diagram was *rendered by us*
   (Sprint 1 D1, since Bookinfo ships no official diagram) with perfectly
   straight, unambiguous lines, so it's not representative of real-world
   diagram noise; it should not be read as "the method gets perfect
   results," only as a sanity check that the method works when conditions
   are ideal.
