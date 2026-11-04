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

3. **Stylized/illustrated icons instead of plain boxes**
   (`spring_cloud_brewery_overview.png`). Components are drawn as 3D server
   icons and literal beer-brewing illustrations (boxes, barrels, bottles)
   rather than clean rectangles. This is a much harder detection case than
   the clean box-and-arrow diagrams and is a good "hard example" for Sprint 3.

4. **Numbered arrows with ambiguous semantics** (same Brewery diagram). Arrows
   are numbered 1-12 corresponding to a request sequence, not simple static
   dependencies; some numbers denote the same logical edge traversed twice
   (e.g. request out, response back). We annotated the underlying structural
   edges only, not the full numbered sequence - sequence-diagram-style
   numbering is a known class of diagram the relationship extractor won't
   handle without special-casing.

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
