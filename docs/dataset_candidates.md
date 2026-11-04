# Dataset Candidates (Sprint 1 / D1)

## Why a diagram needs a paired repository

ArchLens compares an architecture diagram's *intended* structure against a real
repository's *actual* code/Git history to find conformance violations (e.g. a
`Controller` calling `Reviewer` directly instead of going through `Manager`).
A diagram with no corresponding real codebase is unusable for this project,
no matter how polished it looks. Every entry below is a diagram of a real,
specific open-source repository's own architecture.

## Public datasets named in the source 50-day plan (section 17)

These were evaluated first, since they're the plan's own suggested sources:

| Dataset | Verdict | Why |
|---|---|---|
| UML-in-the-Wild (Zenodo) | Not used for Sprint 1 | PlantUML diagrams mined from GitHub repos - mostly class/sequence diagrams, not architecture-level component diagrams. Candidate for a later sprint. |
| Kaggle "UML class diagram dataset (bounded box)" | Not used for Sprint 1 | Real images + bboxes, but UML class diagrams, not service/component architecture diagrams. |
| Architecture-diagram-connectivity dataset (Zenodo, from "Evaluating Software Architecture Diagram Connectivity with VLMs") | Not used for Sprint 1 | Only ships a CSV of model predictions + image URLs, not a curated image set with structural annotations. Possible future source for scale. |
| ArchEval | Not found as a public, obviously-licensed, downloadable dataset under that name. | — |

## Sourcing strategy actually used

1. **Prefer real OSS reference/demo apps that publish their own official
   architecture diagram.** Found via targeted search for well-known
   multi-service demo/reference applications.
2. **Where no diagram exists in the repo, derive one from reading the real
   service code** (HTTP/gRPC calls between services), citing file/line
   evidence - done for Istio Bookinfo.

## Repos considered and the decision for each

| Repo | Diagram found? | License | Included? | Notes |
|---|---|---|---|---|
| GoogleCloudPlatform/microservices-demo | Yes, `docs/img/architecture-diagram.png` | Apache-2.0 | **Yes** | 11 real microservices (Go/C#/Node/Python/Java), gRPC. |
| GoogleCloudPlatform/bank-of-anthos | Yes, `docs/img/architecture.png` | Apache-2.0 | **Yes** | Banking demo, Go/Python/Java. |
| dotnet/eShop | Yes, `img/eshop_architecture.png` | MIT | **Yes** | Successor to the now-code-stripped `dotnet-architecture/eShopOnContainers`. |
| spring-petclinic/spring-petclinic-microservices | Yes, `docs/microservices-architecture-diagram.jpg` | Apache-2.0 | **Yes** | Official Spring Cloud reference app. |
| mblitherland/flask-microservice-demo | Yes, `arch_diagram.png` | Apache-2.0 | **Yes** | Small, simple 4-box case. |
| microservices-demo/microservices-demo (Sock Shop) | Yes, but hosted in the companion `microservices-demo.github.io` docs-site repo (`assets/Architecture.png`) | Apache-2.0 (both repos) | **Yes** | Diagram repo and app-code repo are two real repos from the same project; we pair the diagram with the app-code repo. |
| spring-cloud-samples/brewery | Yes, `img/Brewery.png` **and** `img/Dependency_graph.png` (a second, distinct auto-generated view) | Apache-2.0 | **Yes (both images, 2 manifest entries)** | gateway -> brewing/ingredients/presenting/reporting + Eureka + config-server. |
| roman-bilyak/Microservice.Architecture | Yes, `images/diagram.png` | MIT | **Yes** | ASP.NET Core + Ocelot/NGINX Ingress + RabbitMQ, 5 backend services. |
| istio/istio (Bookinfo sample) | No diagram in-repo | Apache-2.0 | **Yes, derived** | Diagram rendered by us from reading `samples/bookinfo/src/productpage/productpage.py` and `.../reviews/.../LibertyRestEndpoint.java` - see evidence citations in `data/annotations/manifest.json`. |
| dotnet-architecture/eShopOnContainers | — | MIT | No | Archived; GitHub default branch now only contains a redirect README, no real code left to pair with. |
| Istio Bookinfo via istio.io docs page | diagram exists on the docs *website*, not in the repo | — | No (used code-derivation instead) | Avoids depending on an external website for the image; deriving from source code is more rigorous anyway. |
| matjazbravc/Microservice.Architecture.Demo | No diagram | None found | No | No LICENSE file - skipped for licensing clarity. |
| vmudigal/microservices-sample | No diagram | None found | No | Same reason. |
| zachgoll/microservices-architecture-example | No diagram | None found | No | Same reason. |
| spring-cloud-samples/customers-stores | No diagram | None found (org default doesn't propagate) | No | Same reason. |
| piomin/sample-spring-microservices-new | No diagram | None found | No | Same reason, despite being a good real example otherwise. |
| TeaStore (DescartesResearch/TeaStore) | Diagram only appears in the academic paper figure, not the repo | Apache-2.0 | No (for Sprint 1) | Candidate for a later sprint if we want an academic-benchmark example. |

## Final Sprint 1 set (10 diagrams, all real, all paired with a real repository)

See `data/annotations/manifest.json` for the full annotated list and
`data/diagrams/raw/SOURCES.md` for per-file provenance (URL, commit, license).
