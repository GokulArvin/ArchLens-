"""
Sprint 1 / D1: download the real, official architecture diagrams for the
diagram<->repository pairs selected for the P1 CV dataset.

Each entry pairs a diagram image with the exact real open-source repository
and commit it depicts, so later sprints can compare the diagram's intended
structure against that same repository's actual code / Git history.

No synthetic or fabricated images are used here - every file below is
downloaded as-is from the project's own repository.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import requests

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "diagrams" / "raw"


@dataclass
class ReadyMadeDiagram:
    diagram_id: str
    raw_url: str
    filename: str
    repo_url: str
    commit: str
    license: str
    description: str


READY_MADE: list[ReadyMadeDiagram] = [
    ReadyMadeDiagram(
        diagram_id="gcp_microservices_demo",
        raw_url="https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/main/docs/img/architecture-diagram.png",
        filename="gcp_microservices_demo.png",
        repo_url="https://github.com/GoogleCloudPlatform/microservices-demo",
        commit="c7cb6d5bfd6ea3aed768634ebbcb98cb7a523712",
        license="Apache-2.0",
        description="Online Boutique - 11 real microservices (Go/C#/Node/Python/Java) over gRPC.",
    ),
    ReadyMadeDiagram(
        diagram_id="gcp_bank_of_anthos",
        raw_url="https://raw.githubusercontent.com/GoogleCloudPlatform/bank-of-anthos/main/docs/img/architecture.png",
        filename="gcp_bank_of_anthos.png",
        repo_url="https://github.com/GoogleCloudPlatform/bank-of-anthos",
        commit="db35fea9fd090150e2398106aadb475576f80d94",
        license="Apache-2.0",
        description="Bank of Anthos - banking microservices demo (frontend, ledger, balance, transaction history, user service, contacts).",
    ),
    ReadyMadeDiagram(
        diagram_id="dotnet_eshop",
        raw_url="https://raw.githubusercontent.com/dotnet/eShop/main/img/eshop_architecture.png",
        filename="dotnet_eshop.png",
        repo_url="https://github.com/dotnet/eShop",
        commit="913acea66708a59595351174cee9b29f37179d29",
        license="MIT",
        description="eShop (.NET Aspire) - successor to eShopOnContainers, DDD/CQRS multi-service .NET app.",
    ),
    ReadyMadeDiagram(
        diagram_id="spring_petclinic_microservices",
        raw_url="https://raw.githubusercontent.com/spring-petclinic/spring-petclinic-microservices/main/docs/microservices-architecture-diagram.jpg",
        filename="spring_petclinic_microservices.jpg",
        repo_url="https://github.com/spring-petclinic/spring-petclinic-microservices",
        commit="e8b747ab522721076cacb5cf688eb8a54ba8c5c9",
        license="Apache-2.0",
        description="Spring PetClinic microservices - official Spring Cloud reference app (API gateway, discovery, config server, customers/vets/visits services).",
    ),
    ReadyMadeDiagram(
        diagram_id="flask_microservice_demo",
        raw_url="https://raw.githubusercontent.com/mblitherland/flask-microservice-demo/master/arch_diagram.png",
        filename="flask_microservice_demo.png",
        repo_url="https://github.com/mblitherland/flask-microservice-demo",
        commit="d98872fcde8ae00f9df3224c1d5d4f08eb312429",
        license="Apache-2.0",
        description="Small Flask/Python microservice demo (aggregate, items, orders services).",
    ),
    ReadyMadeDiagram(
        diagram_id="sock_shop",
        raw_url="https://raw.githubusercontent.com/microservices-demo/microservices-demo.github.io/master/assets/Architecture.png",
        filename="sock_shop.png",
        repo_url="https://github.com/microservices-demo/microservices-demo",
        commit="1ae9f90384364b961fe6bfb6c796ddba328c6ad8",  # commit of the .github.io diagram source
        license="Apache-2.0",
        description="Sock Shop (Weaveworks) - polyglot microservices demo; diagram hosted in the project's companion docs-site repo, describes the app repo's architecture.",
    ),
    ReadyMadeDiagram(
        diagram_id="aws_retail_store_sample_app",
        raw_url="https://raw.githubusercontent.com/aws-containers/retail-store-sample-app/main/docs/images/architecture.png",
        filename="aws_retail_store_sample_app.png",
        repo_url="https://github.com/aws-containers/retail-store-sample-app",
        commit="d7a380b843e0759e58754f74188ea18252a51415",
        license="MIT-0",
        description="AWS retail-store-sample-app - UI service calling Orders/Checkout/Cart/Catalog microservices, each with its own persistence (PostgreSQL/Redis/DynamoDB/MySQL) plus an SQS/RabbitMQ queue.",
    ),
    ReadyMadeDiagram(
        diagram_id="azure_aks_store_demo",
        raw_url="https://raw.githubusercontent.com/Azure-Samples/aks-store-demo/main/assets/demo-arch.png",
        filename="azure_aks_store_demo.png",
        repo_url="https://github.com/Azure-Samples/aks-store-demo",
        commit="1d61b202d1e6dc9a78389c15e4bb9d529e5499d3",
        license="MIT",
        description="Azure Kubernetes Store demo - polyglot microservices (Vue store-front/store-admin, Node order-service, Rust product-service, Go makeline-service) around a RabbitMQ order queue and MongoDB order database.",
    ),
    ReadyMadeDiagram(
        diagram_id="roman_bilyak_microservice_architecture",
        raw_url="https://raw.githubusercontent.com/roman-bilyak/Microservice.Architecture/main/images/diagram.png",
        filename="roman_bilyak_microservice_architecture.png",
        repo_url="https://github.com/roman-bilyak/Microservice.Architecture",
        commit="3a3413b40114b810def53960aeb92a8026a71dcb",
        license="MIT",
        description="ASP.NET Core microservices behind NGINX Ingress - Identity/Movie/Payment/Review/Test services, each with its own MS SQL database, communicating via RabbitMQ.",
    ),
]

# Note: the 10th diagram (istio_bookinfo_derived) is not downloaded - it has
# no in-repo diagram and is rendered from real source-code evidence instead.
# Run derive_bookinfo_diagram.py separately to produce it.


def fetch_all() -> list[dict]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fetched = []
    for item in READY_MADE:
        dest = RAW_DIR / item.filename
        resp = requests.get(item.raw_url, timeout=30)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        print(f"downloaded {item.diagram_id} -> {dest} ({len(resp.content)} bytes)")
        fetched.append(asdict(item))
    return fetched


def write_sources_md(fetched: list[dict]) -> None:
    lines = [
        "# SOURCES.md",
        "",
        "Provenance for every real diagram image in `data/diagrams/raw/`.",
        "No synthetic/fabricated images are used; every file is downloaded as-is",
        "from the real repository that owns it.",
        "",
    ]
    for item in fetched:
        lines += [
            f"## {item['filename']}",
            f"- diagram_id: `{item['diagram_id']}`",
            f"- source: {item['raw_url']}",
            f"- repository: {item['repo_url']}",
            f"- commit: `{item['commit']}`",
            f"- license: {item['license']}",
            f"- description: {item['description']}",
            "",
        ]
    (RAW_DIR / "SOURCES.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    fetched = fetch_all()
    write_sources_md(fetched)
    print(f"\nFetched {len(fetched)} real diagrams. SOURCES.md written to {RAW_DIR}.")
