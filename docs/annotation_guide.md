# Annotation Guide (Sprint 1 / D3)

This guide defines how diagrams are annotated for the P1 CV dataset. It uses
the **real, shared schema already defined in `backend/app/schemas/models.py`**
(`ArchComponent`, `ArchRelationship`, `ArchGraph`) rather than a separate,
invented schema - this is the contract P2's semantic layer and P3's graph
layer consume too.

## Component boxes (`ArchComponent`)

| Field | Meaning | Notes |
|---|---|---|
| `id` | Stable slug, unique within the diagram | e.g. `"frontend"`, `"paymentservice"` |
| `name` | Human-readable label as shown in the diagram | Copied from the diagram text when legible |
| `type` | One of `ComponentType`: `service`, `database`, `queue`, `gateway`, `frontend`, `cache`, `external`, `unknown` | See mapping convention below |
| `bbox` | `{x1, y1, x2, y2}` in pixel coordinates of the source image | Top-left origin, axis-aligned box around the visual element |
| `confidence` | `1.0` for hand-annotated ground truth | Lower values are reserved for future automated-detector output |

**Type mapping convention**: user-facing UI -> `frontend`; API gateway/ingress/reverse
proxy -> `gateway`; message broker/queue -> `queue`; SQL/NoSQL/vector store ->
`database`; in-memory store (Redis etc.) -> `cache`; third-party/external system
(e.g. OpenAI, a human actor) -> `external`; anything else that's a deployable
service -> `service`.

**Granularity convention**: when a diagram groups a service with its own
small adjoining database icon (e.g. Sock Shop's per-service Mongo icons), we
annotate the service as one component and note the database in
`metadata` rather than creating a separate tiny box, *unless* the database is
drawn as a clearly separate, similarly-sized box (as in Bank of Anthos or
Spring PetClinic) - then it gets its own `ArchComponent`. This trade-off is
documented per-diagram in `data/annotations/manifest.json` and tracked as a
known source of inconsistency in `docs/cv_failure_cases.md`.

## Connector/arrow evidence (`ArchRelationship`)

| Field | Meaning | Notes |
|---|---|---|
| `id` | Stable slug, unique within the diagram | e.g. `"e1"`, `"e2"` |
| `source` / `target` | Component `id`s the arrow connects | Direction follows the arrowhead |
| `type` | One of `RelationshipType`: `depends_on`, `calls`, `inherits`, `implements`, `uses`, `contains`, `unknown` | See mapping convention below |
| `confidence` | `1.0` for hand-annotated ground truth | |

**Type mapping convention**: service-to-service arrows -> `calls`;
service-to-database/queue/cache arrows -> `uses`. (`inherits`/`implements`/
`contains` are reserved for static-analysis-derived edges in later sprints,
not diagram geometry.)

## Diagram-level pairing (`ArchGraph.metadata["source_repository"]`)

Every diagram entry must be paired with the real repository it describes.
`ArchGraph` already has a generic `metadata: Dict[str, Any]` field in the
shared schema, so we don't need to fork the schema - we just populate it:

```json
"metadata": {
  "source_repository": {
    "repo_url": "https://github.com/...",
    "commit": "<sha>",
    "license": "Apache-2.0",
    "diagram_provenance": "official",
    "evidence": ["<file>:<lines> (<what it shows>)", "..."]
  }
}
```

- `diagram_provenance` is `"official"` when the image comes straight from the
  repository (or its docs site), and `"derived"` when we rendered it
  ourselves from reading the real service code.
- `evidence` is **required** when `diagram_provenance` is `"derived"` - a list
  of real file/line citations backing each inferred relationship. It's
  optional metadata otherwise.

## Example (abridged, from `flask_microservice_demo`)

```json
{
  "id": "flask_microservice_demo",
  "graph_type": "intended",
  "source": "data/diagrams/raw/flask_microservice_demo.png",
  "components": [
    {"id": "backend", "name": "Backend", "type": "gateway", "bbox": {"x1": 68, "y1": 75, "x2": 470, "y2": 240}, "confidence": 1.0},
    {"id": "orders", "name": "Orders", "type": "service", "bbox": {"x1": 58, "y1": 580, "x2": 460, "y2": 805}, "confidence": 1.0}
  ],
  "relationships": [
    {"id": "e2", "source": "backend", "target": "orders", "type": "calls", "confidence": 1.0}
  ],
  "metadata": {"source_repository": {"repo_url": "https://github.com/mblitherland/flask-microservice-demo", "commit": "d98872f...", "license": "Apache-2.0", "diagram_provenance": "official"}}
}
```

See `backend/app/modules/cv_pipeline/dataset_manifest.py` for the loader/
validator that enforces this contract, and `backend/scripts/build_manifest.py`
for the full annotated set.
