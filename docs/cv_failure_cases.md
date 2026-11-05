# CV Failure Cases to Track (Sprint 1 / D5)

Observed while hand-annotating the 10 real diagrams in `data/annotations/manifest.json`.
These are genuine issues found in real images, kept here so later sprints
(detection evaluation in Sprint 3, segmentation in Sprint 4, relationship
extraction in Sprint 5) know what to expect rather than being surprised.

1. **Nested/grouped components** (`dotnet_eshop.png`). Services are drawn
   inside labeled container boxes ("Cloud Services" > "Aspire Orchestration"
   > "Identity Service" > "Identity API" + "PostgreSQL"). We annotated at the
   service-group level only, not each inner API/DB sub-box, to keep Sprint 1
   tractable. A real detector will likely either merge these into one box or
   over-fragment them - worth an explicit evaluation category in Sprint 3.

2. **Service + adjoining database icon treated inconsistently**
   (`sock_shop.png` vs `gcp_bank_of_anthos.png`). When the DB is a small icon
   right next to the service box we folded it into the service; when it's a
   full separate box we gave it its own component. This inconsistency is a
   known annotation-convention gap (documented in `docs/annotation_guide.md`)
   that should be resolved with a firmer rule before Sprint 3 evaluation.

3. **Stylized/illustrated icons instead of plain boxes (resolved by dataset
   correction)**. The original Sprint 1 pick, `spring_cloud_brewery_overview.png`,
   drew components as 3D server icons and literal beer-brewing illustrations
   (boxes, barrels, bottles) rather than clean rectangles - confirmed in
   Sprint 3 to be the actual cause of the YOLO/COCO baseline's only
   coincidental "true positives" (the illustrated icons happened to resemble
   real COCO objects). Dropped post-Sprint-10 and replaced with
   `aws_retail_store_sample_app.png`/`azure_aks_store_demo.png`, both clean
   boxes-and-arrows diagrams - see `docs/dataset_candidates.md`.

4. **Curved (non-straight) connector lines** (`azure_aks_store_demo.png`).
   Several edges - `store-front` fanning out to `order-service`/
   `product-service`, and `order-service`/`makeline-service` both converging
   on the shared `Order Queue` - are drawn as smooth bezier curves rather
   than straight segments. Confirmed in Sprint 5 to defeat Hough-line-based
   relation extraction (recall dropped to 0.111 on this diagram, the
   dataset's worst): a curve only contributes short, fragmented Hough
   segments that rarely land near the correct component boxes. A real,
   non-straight-line failure mode the geometry baseline doesn't handle.

5. **Diagram hosted outside the application's own repository**
   (`sock_shop.png` - image lives in a companion `.github.io` docs-site repo,
   not the app-code repo itself). The manifest handles this by letting
   `source_repository.repo_url` point to the app repo while the image file
   itself came from elsewhere - documented via `SOURCES.md`, but any future
   automated dataset-expansion script must not assume "diagram repo == code
   repo".

6. **No in-repo diagram at all** (`istio/istio` Bookinfo sample). Required
   deriving the diagram from source code reading rather than image download.
   Confirms the plan's real-world expectation that not every target
   repository will have a ready-made diagram - P1's dataset-building
   workflow needs this path to stay cheap, since it won't be rare.

7. **Dark-background diagram among mostly light-background ones**
   (`dotnet_eshop.png`). All preprocessing (CLAHE, edge detection thresholds)
   tuned by eye on light backgrounds should be explicitly re-checked against
   this one in Sprint 2 rather than assumed to generalize.
