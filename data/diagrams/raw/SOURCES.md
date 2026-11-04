# SOURCES.md

Provenance for every real diagram image in `data/diagrams/raw/`.
No synthetic/fabricated images are used; every file is downloaded as-is
from the real repository that owns it.

## gcp_microservices_demo.png
- diagram_id: `gcp_microservices_demo`
- source: https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/main/docs/img/architecture-diagram.png
- repository: https://github.com/GoogleCloudPlatform/microservices-demo
- commit: `c7cb6d5bfd6ea3aed768634ebbcb98cb7a523712`
- license: Apache-2.0
- description: Online Boutique - 11 real microservices (Go/C#/Node/Python/Java) over gRPC.

## gcp_bank_of_anthos.png
- diagram_id: `gcp_bank_of_anthos`
- source: https://raw.githubusercontent.com/GoogleCloudPlatform/bank-of-anthos/main/docs/img/architecture.png
- repository: https://github.com/GoogleCloudPlatform/bank-of-anthos
- commit: `db35fea9fd090150e2398106aadb475576f80d94`
- license: Apache-2.0
- description: Bank of Anthos - banking microservices demo (frontend, ledger, balance, transaction history, user service, contacts).

## dotnet_eshop.png
- diagram_id: `dotnet_eshop`
- source: https://raw.githubusercontent.com/dotnet/eShop/main/img/eshop_architecture.png
- repository: https://github.com/dotnet/eShop
- commit: `913acea66708a59595351174cee9b29f37179d29`
- license: MIT
- description: eShop (.NET Aspire) - successor to eShopOnContainers, DDD/CQRS multi-service .NET app.

## spring_petclinic_microservices.jpg
- diagram_id: `spring_petclinic_microservices`
- source: https://raw.githubusercontent.com/spring-petclinic/spring-petclinic-microservices/main/docs/microservices-architecture-diagram.jpg
- repository: https://github.com/spring-petclinic/spring-petclinic-microservices
- commit: `e8b747ab522721076cacb5cf688eb8a54ba8c5c9`
- license: Apache-2.0
- description: Spring PetClinic microservices - official Spring Cloud reference app (API gateway, discovery, config server, customers/vets/visits services).

## flask_microservice_demo.png
- diagram_id: `flask_microservice_demo`
- source: https://raw.githubusercontent.com/mblitherland/flask-microservice-demo/master/arch_diagram.png
- repository: https://github.com/mblitherland/flask-microservice-demo
- commit: `d98872fcde8ae00f9df3224c1d5d4f08eb312429`
- license: Apache-2.0
- description: Small Flask/Python microservice demo (aggregate, items, orders services).

## sock_shop.png
- diagram_id: `sock_shop`
- source: https://raw.githubusercontent.com/microservices-demo/microservices-demo.github.io/master/assets/Architecture.png
- repository: https://github.com/microservices-demo/microservices-demo
- commit: `1ae9f90384364b961fe6bfb6c796ddba328c6ad8`
- license: Apache-2.0
- description: Sock Shop (Weaveworks) - polyglot microservices demo; diagram hosted in the project's companion docs-site repo, describes the app repo's architecture.

## spring_cloud_brewery_overview.png
- diagram_id: `spring_cloud_brewery_overview`
- source: https://raw.githubusercontent.com/spring-cloud-samples/brewery/main/img/Brewery.png
- repository: https://github.com/spring-cloud-samples/brewery
- commit: `1bfe678944978dd28d620a177222b5faaa0bd278`
- license: Apache-2.0
- description: Spring Cloud Brewery sample - gateway -> brewing/ingredients/presenting/reporting services + Eureka + config-server. High-level overview diagram.

## spring_cloud_brewery_dependency_graph.png
- diagram_id: `spring_cloud_brewery_dependency_graph`
- source: https://raw.githubusercontent.com/spring-cloud-samples/brewery/main/img/Dependency_graph.png
- repository: https://github.com/spring-cloud-samples/brewery
- commit: `1bfe678944978dd28d620a177222b5faaa0bd278`
- license: Apache-2.0
- description: Same Brewery repo as above, but the project's own generated service-dependency-graph diagram (a distinct view of the same real system).

## roman_bilyak_microservice_architecture.png
- diagram_id: `roman_bilyak_microservice_architecture`
- source: https://raw.githubusercontent.com/roman-bilyak/Microservice.Architecture/main/images/diagram.png
- repository: https://github.com/roman-bilyak/Microservice.Architecture
- commit: `3a3413b40114b810def53960aeb92a8026a71dcb`
- license: MIT
- description: ASP.NET Core microservices behind NGINX Ingress - Identity/Movie/Payment/Review/Test services, each with its own MS SQL database, communicating via RabbitMQ.

## istio_bookinfo_derived.png
- diagram_id: `istio_bookinfo_derived`
- source: rendered by us (`backend/scripts/derive_bookinfo_diagram.py`) - no in-repo diagram exists for this sample
- repository: https://github.com/istio/istio (samples/bookinfo)
- commit: `399ef1bff5261a01708c13b73a93cdc20189b08a`
- license: Apache-2.0
- description: Bookinfo sample app. Diagram provenance is "derived", not "official" - every box/arrow is backed by real evidence citations (file + line) recorded in `data/annotations/manifest.json`, read directly from the real service source code.
