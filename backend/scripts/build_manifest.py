"""
Sprint 1 / D4: build data/annotations/manifest.json from hand-annotated
component boxes and connector/relationship evidence for each of the 10 real
diagrams in data/diagrams/raw/.

Every bbox below was produced by visually inspecting the actual downloaded
(or, for the one "derived" entry, rendered-from-evidence) image and is a
genuine approximation of the real component positions - not generated or
guessed. Precision will be refined in later sprints once automated
detection/evaluation is in place (see docs/cv_failure_cases.md).

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/build_manifest.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.models import ArchComponent, ArchGraph, ArchRelationship, BoundingBox  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
MANIFEST_PATH = REPO_ROOT / "data" / "annotations" / "manifest.json"


def comp(id_, name, type_, bbox):
    return ArchComponent(id=id_, name=name, type=type_, bbox=BoundingBox(x1=bbox[0], y1=bbox[1], x2=bbox[2], y2=bbox[3]), confidence=1.0)


def rel(id_, source, target, type_="calls"):
    return ArchRelationship(id=id_, source=source, target=target, type=type_, confidence=1.0)


GRAPHS: list[ArchGraph] = []

# ───────────────────────── 1. GCP microservices-demo (Online Boutique) ─────
GRAPHS.append(ArchGraph(
    id="gcp_microservices_demo",
    name="Online Boutique (GoogleCloudPlatform/microservices-demo)",
    graph_type="intended",
    source="data/diagrams/raw/gcp_microservices_demo.png",
    components=[
        comp("loadgenerator", "loadgenerator", "service", (610, 60, 765, 130)),
        comp("frontend", "frontend", "frontend", (610, 235, 765, 295)),
        comp("ad", "ad", "service", (45, 375, 185, 445)),
        comp("recommendation", "recommendation", "service", (210, 375, 390, 445)),
        comp("checkout", "checkout", "service", (1020, 363, 1155, 422)),
        comp("payment", "payment", "service", (1195, 305, 1330, 365)),
        comp("email", "email", "service", (1195, 435, 1330, 495)),
        comp("productcatalog", "productcatalog", "service", (340, 552, 500, 615)),
        comp("cart", "cart", "service", (620, 552, 758, 615)),
        comp("shipping", "shipping", "service", (803, 562, 940, 622)),
        comp("currency", "currency", "service", (980, 562, 1118, 622)),
        comp("rediscache", "Redis cache", "cache", (618, 663, 758, 745)),
    ],
    relationships=[
        rel("e1", "loadgenerator", "frontend"),
        rel("e2", "frontend", "ad"), rel("e3", "frontend", "recommendation"),
        rel("e4", "frontend", "checkout"), rel("e5", "frontend", "productcatalog"),
        rel("e6", "frontend", "cart"), rel("e7", "frontend", "shipping"),
        rel("e8", "frontend", "currency"),
        rel("e9", "recommendation", "productcatalog"),
        rel("e10", "checkout", "productcatalog"), rel("e11", "checkout", "cart"),
        rel("e12", "checkout", "shipping"), rel("e13", "checkout", "currency"),
        rel("e14", "checkout", "payment"), rel("e15", "checkout", "email"),
        rel("e16", "cart", "rediscache", "uses"),
    ],
    metadata={"source_repository": {
        "repo_url": "https://github.com/GoogleCloudPlatform/microservices-demo",
        "commit": "c7cb6d5bfd6ea3aed768634ebbcb98cb7a523712",
        "license": "Apache-2.0",
        "diagram_provenance": "official",
    }},
))

# ───────────────────────── 2. GCP Bank of Anthos ────────────────────────────
GRAPHS.append(ArchGraph(
    id="gcp_bank_of_anthos",
    name="Bank of Anthos (GoogleCloudPlatform/bank-of-anthos)",
    graph_type="intended",
    source="data/diagrams/raw/gcp_bank_of_anthos.png",
    components=[
        comp("loadgen", "loadgen", "service", (610, 55, 765, 125)),
        comp("frontend", "frontend", "frontend", (610, 235, 765, 300)),
        comp("userservice", "userservice", "service", (160, 430, 315, 500)),
        comp("contacts", "contacts", "service", (385, 430, 540, 500)),
        comp("ledgerwriter", "ledgerwriter", "service", (610, 430, 765, 500)),
        comp("balancereader", "balancereader", "service", (835, 430, 990, 500)),
        comp("transactionhistory", "transactionhistory", "service", (1060, 430, 1215, 500)),
        comp("accountsdb", "accounts db", "database", (265, 635, 420, 710)),
        comp("ledgerdb", "ledger db", "database", (838, 635, 993, 710)),
    ],
    relationships=[
        rel("e1", "loadgen", "frontend"),
        rel("e2", "frontend", "userservice"), rel("e3", "frontend", "contacts"),
        rel("e4", "frontend", "ledgerwriter"), rel("e5", "frontend", "balancereader"),
        rel("e6", "frontend", "transactionhistory"),
        rel("e7", "userservice", "accountsdb", "uses"), rel("e8", "contacts", "accountsdb", "uses"),
        rel("e9", "ledgerwriter", "ledgerdb", "uses"), rel("e10", "balancereader", "ledgerdb", "uses"),
        rel("e11", "transactionhistory", "ledgerdb", "uses"),
    ],
    metadata={"source_repository": {
        "repo_url": "https://github.com/GoogleCloudPlatform/bank-of-anthos",
        "commit": "db35fea9fd090150e2398106aadb475576f80d94",
        "license": "Apache-2.0",
        "diagram_provenance": "official",
    }},
))

# ───────────────────────── 3. dotnet/eShop ──────────────────────────────────
GRAPHS.append(ArchGraph(
    id="dotnet_eshop",
    name="eShop reference application (dotnet/eShop)",
    graph_type="intended",
    source="data/diagrams/raw/dotnet_eshop.png",
    components=[
        comp("mobilebff", "Mobile BFF", "gateway", (823, 461, 1117, 692)),
        comp("webapp", "Web App", "frontend", (823, 774, 1117, 1022)),
        comp("identityservice", "Identity Service", "service", (1176, 412, 1823, 528)),
        comp("catalogservice", "Catalog Service", "service", (1176, 544, 1823, 659)),
        comp("orderservice", "Order Service", "service", (1176, 692, 1823, 857)),
        comp("basketservice", "Basket Service", "service", (1176, 890, 1823, 1022)),
        comp("paymentservice", "Payment Service", "service", (1176, 1038, 1823, 1154)),
        comp("eventbus", "Event Bus", "queue", (1911, 692, 2234, 955)),
        comp("openai", "OpenAI", "external", (2293, 297, 2646, 461)),
        comp("webhooksservice", "Webhooks Service", "service", (823, 1220, 1823, 1450)),
        comp("observability", "Observability", "service", (1852, 1220, 2205, 1450)),
    ],
    relationships=[
        rel("e1", "mobilebff", "identityservice"), rel("e2", "mobilebff", "catalogservice"),
        rel("e3", "mobilebff", "orderservice"), rel("e4", "mobilebff", "basketservice"),
        rel("e5", "webapp", "identityservice"), rel("e6", "webapp", "catalogservice"),
        rel("e7", "webapp", "orderservice"), rel("e8", "webapp", "basketservice"),
        rel("e9", "catalogservice", "openai"),
        rel("e10", "orderservice", "eventbus", "uses"), rel("e11", "basketservice", "eventbus", "uses"),
        rel("e12", "paymentservice", "eventbus", "uses"),
        rel("e13", "eventbus", "openai"),
        rel("e14", "webhooksservice", "webapp"),
    ],
    metadata={"source_repository": {
        "repo_url": "https://github.com/dotnet/eShop",
        "commit": "913acea66708a59595351174cee9b29f37179d29",
        "license": "MIT",
        "diagram_provenance": "official",
    }},
))

# ───────────────────────── 4. Spring PetClinic microservices ───────────────
GRAPHS.append(ArchGraph(
    id="spring_petclinic_microservices",
    name="Spring PetClinic Microservices",
    graph_type="intended",
    source="data/diagrams/raw/spring_petclinic_microservices.jpg",
    components=[
        comp("gitrepo", "Git Repo", "external", (300, 60, 460, 140)),
        comp("configserver", "Spring Cloud Config Server", "service", (35, 195, 280, 330)),
        comp("eureka", "Eureka Service Discovery", "service", (15, 395, 265, 535)),
        comp("gateway", "UI + API Gateway", "gateway", (745, 330, 1005, 460)),
        comp("adminserver", "Spring Boot Admin Server", "service", (1355, 185, 1560, 330)),
        comp("zipkin", "OpenZipkin Distributed Logging Server", "service", (1355, 350, 1560, 540)),
        comp("customersservice", "customers-service", "service", (215, 630, 470, 785)),
        comp("genaiservice", "genai-service", "service", (600, 630, 800, 785)),
        comp("vetsservice", "vets-service", "service", (905, 630, 1105, 785)),
        comp("petsservice", "pets-service", "service", (1195, 630, 1395, 785)),
        comp("customersdb", "customers RDBMS", "database", (300, 805, 420, 930)),
        comp("genaivectorstore", "genai Vector Store", "database", (640, 805, 770, 930)),
        comp("vetsdb", "vets RDBMS", "database", (960, 805, 1080, 930)),
        comp("petsdb", "pets RDBMS", "database", (1250, 805, 1370, 930)),
    ],
    relationships=[
        rel("e1", "gateway", "eureka"),
        rel("e2", "gateway", "customersservice"), rel("e3", "gateway", "genaiservice"),
        rel("e4", "gateway", "vetsservice"), rel("e5", "gateway", "petsservice"),
        rel("e6", "customersservice", "eureka"), rel("e7", "genaiservice", "eureka"),
        rel("e8", "vetsservice", "eureka"), rel("e9", "petsservice", "eureka"),
        rel("e10", "customersservice", "configserver"), rel("e11", "genaiservice", "configserver"),
        rel("e12", "vetsservice", "configserver"), rel("e13", "petsservice", "configserver"),
        rel("e14", "genaiservice", "vetsservice"), rel("e15", "customersservice", "genaiservice"),
        rel("e16", "petsservice", "adminserver"), rel("e17", "petsservice", "zipkin"),
        rel("e18", "customersservice", "customersdb", "uses"), rel("e19", "genaiservice", "genaivectorstore", "uses"),
        rel("e20", "vetsservice", "vetsdb", "uses"), rel("e21", "petsservice", "petsdb", "uses"),
        rel("e22", "configserver", "gitrepo"),
    ],
    metadata={"source_repository": {
        "repo_url": "https://github.com/spring-petclinic/spring-petclinic-microservices",
        "commit": "e8b747ab522721076cacb5cf688eb8a54ba8c5c9",
        "license": "Apache-2.0",
        "diagram_provenance": "official",
    }},
))

# ───────────────────────── 5. flask-microservice-demo ──────────────────────
GRAPHS.append(ArchGraph(
    id="flask_microservice_demo",
    name="flask-microservice-demo (mblitherland)",
    graph_type="intended",
    source="data/diagrams/raw/flask_microservice_demo.png",
    components=[
        comp("backend", "Backend", "gateway", (68, 75, 470, 240)),
        comp("aggregate", "Aggregate", "service", (345, 360, 750, 495)),
        comp("orders", "Orders", "service", (58, 580, 460, 805)),
        comp("items", "Items", "service", (605, 580, 1008, 805)),
    ],
    relationships=[
        rel("e1", "backend", "aggregate"), rel("e2", "backend", "orders"),
        rel("e3", "aggregate", "orders"), rel("e4", "aggregate", "items"),
    ],
    metadata={"source_repository": {
        "repo_url": "https://github.com/mblitherland/flask-microservice-demo",
        "commit": "d98872fcde8ae00f9df3224c1d5d4f08eb312429",
        "license": "Apache-2.0",
        "diagram_provenance": "official",
    }},
))

# ───────────────────────── 6. Sock Shop ─────────────────────────────────────
GRAPHS.append(ArchGraph(
    id="sock_shop",
    name="Sock Shop (microservices-demo/microservices-demo)",
    graph_type="intended",
    source="data/diagrams/raw/sock_shop.png",
    components=[
        comp("user_actor", "User", "external", (730, 30, 913, 215)),
        comp("frontend", "Front-end", "frontend", (730, 310, 913, 497)),
        comp("order", "Order", "service", (240, 692, 413, 862)),
        comp("payment", "Payment", "service", (492, 692, 667, 862)),
        comp("userservice", "User (service)", "service", (730, 692, 910, 862)),
        comp("catalogue", "Catalogue", "service", (970, 692, 1163, 862)),
        comp("cart", "Cart", "service", (1225, 692, 1403, 862)),
        comp("shipping", "Shipping", "service", (490, 975, 670, 1145)),
        comp("queue", "Queue", "queue", (730, 975, 913, 1145)),
        comp("queuemaster", "Queue-Master", "service", (970, 975, 1150, 1145)),
    ],
    relationships=[
        rel("e1", "user_actor", "frontend"),
        rel("e2", "frontend", "order"), rel("e3", "frontend", "payment"),
        rel("e4", "frontend", "userservice"), rel("e5", "frontend", "catalogue"),
        rel("e6", "frontend", "cart"),
        rel("e7", "order", "shipping"), rel("e8", "shipping", "queue", "uses"),
        rel("e9", "queue", "queuemaster", "uses"),
    ],
    metadata={"source_repository": {
        "repo_url": "https://github.com/microservices-demo/microservices-demo",
        "commit": "1ae9f90384364b961fe6bfb6c796ddba328c6ad8",
        "license": "Apache-2.0",
        "diagram_provenance": "official",
        "note": "Diagram file lives in the project's companion docs-site repo (microservices-demo/microservices-demo.github.io) but depicts this app repo's architecture.",
    }},
))

# ───────────────────────── 7. AWS retail-store-sample-app ──────────────────
# Replaces the earlier spring-cloud-samples/brewery "overview" diagram, which
# was a stylized beer-brewing illustration (barrels/bottles) rather than a
# genuine boxes-and-arrows software architecture diagram. This is a clean
# official diagram of a real, actively-maintained polyglot microservices app.
GRAPHS.append(ArchGraph(
    id="aws_retail_store_sample_app",
    name="retail-store-sample-app (aws-containers)",
    graph_type="intended",
    source="data/diagrams/raw/aws_retail_store_sample_app.png",
    components=[
        comp("ui", "UI", "frontend", (233, 19, 309, 95)),
        comp("orders", "Orders", "service", (43, 153, 119, 229)),
        comp("checkout", "Checkout", "service", (173, 153, 249, 229)),
        comp("cart", "Cart", "service", (303, 153, 379, 229)),
        comp("catalog", "Catalog", "service", (433, 153, 509, 229)),
        comp("postgresql", "PostgreSQL", "database", (43, 273, 119, 349)),
        comp("redis", "Redis", "cache", (173, 273, 249, 349)),
        comp("dynamodb", "DynamoDB", "database", (303, 273, 379, 349)),
        comp("mysql_mariadb", "MySQL / MariaDB", "database", (433, 273, 509, 349)),
        comp("sqs_rabbitmq", "SQS / RabbitMQ", "queue", (233, 393, 309, 469)),
    ],
    relationships=[
        rel("e1", "ui", "orders"), rel("e2", "ui", "checkout"),
        rel("e3", "ui", "cart"), rel("e4", "ui", "catalog"),
        rel("e5", "checkout", "orders"),
        rel("e6", "orders", "postgresql", "uses"), rel("e7", "checkout", "redis", "uses"),
        rel("e8", "cart", "dynamodb", "uses"), rel("e9", "catalog", "mysql_mariadb", "uses"),
        rel("e10", "sqs_rabbitmq", "orders", "uses"),
    ],
    metadata={"source_repository": {
        "repo_url": "https://github.com/aws-containers/retail-store-sample-app",
        "commit": "d7a380b843e0759e58754f74188ea18252a51415",
        "license": "MIT-0",
        "diagram_provenance": "official",
    }},
))

# ───────────────────────── 8. Azure aks-store-demo ──────────────────────────
# Replaces the earlier spring-cloud-samples/brewery "dependency graph" diagram
# (same flagged repo). This is a clean official diagram of a real polyglot
# microservices app (Vue/Node/Rust/Go) maintained by Microsoft.
GRAPHS.append(ArchGraph(
    id="azure_aks_store_demo",
    name="aks-store-demo (Azure-Samples)",
    graph_type="intended",
    source="data/diagrams/raw/azure_aks_store_demo.png",
    components=[
        comp("customers", "Customers", "external", (110, 400, 328, 710)),
        comp("employees", "Employees", "external", (110, 1048, 328, 1332)),
        comp("store_front", "store-front", "frontend", (610, 355, 1132, 728)),
        comp("store_admin", "store-admin", "frontend", (610, 986, 1132, 1359)),
        comp("order_service", "order-service", "service", (1595, 79, 2112, 436)),
        comp("product_service", "product-service", "service", (1595, 683, 2112, 1048)),
        comp("makeline_service", "makeline-service", "service", (1595, 1287, 2112, 1652)),
        comp("order_queue", "Order Queue (RabbitMQ)", "queue", (2596, 89, 3050, 436)),
        comp("order_database", "Order Database (MongoDB)", "database", (2596, 1324, 3050, 1687)),
    ],
    relationships=[
        rel("e1", "customers", "store_front"), rel("e2", "employees", "store_admin"),
        rel("e3", "store_front", "order_service"), rel("e4", "store_front", "product_service"),
        rel("e5", "store_admin", "product_service"), rel("e6", "store_admin", "makeline_service"),
        rel("e7", "order_service", "order_queue", "uses"),
        rel("e8", "makeline_service", "order_queue", "uses"),
        rel("e9", "makeline_service", "order_database", "uses"),
    ],
    metadata={"source_repository": {
        "repo_url": "https://github.com/Azure-Samples/aks-store-demo",
        "commit": "1d61b202d1e6dc9a78389c15e4bb9d529e5499d3",
        "license": "MIT",
        "diagram_provenance": "official",
    }},
))

# ───────────────────────── 9. roman-bilyak Microservice.Architecture ───────
GRAPHS.append(ArchGraph(
    id="roman_bilyak_microservice_architecture",
    name="Microservice.Architecture (roman-bilyak)",
    graph_type="intended",
    source="data/diagrams/raw/roman_bilyak_microservice_architecture.png",
    components=[
        comp("browser", "browser (https://localhost)", "external", (15, 275, 135, 390)),
        comp("ingress", "Ingress (NGINX)", "gateway", (210, 35, 295, 655)),
        comp("appangular", "App Angular", "frontend", (370, 50, 520, 115)),
        comp("authservice", "Auth Service", "service", (370, 225, 520, 295)),
        comp("apigateway", "API Gateway Service", "gateway", (370, 400, 520, 465)),
        comp("appreact", "App React", "frontend", (370, 580, 520, 645)),
        comp("identityservice", "Identity Service", "service", (600, 95, 760, 150)),
        comp("movieservice", "Movie Service", "service", (600, 210, 760, 265)),
        comp("paymentservice", "Payment Service", "service", (600, 335, 760, 390)),
        comp("reviewservice", "Review Service", "service", (600, 460, 760, 515)),
        comp("testservice", "Test Service", "service", (600, 580, 760, 635)),
        comp("rabbitmq", "RabbitMQ", "queue", (955, 50, 1020, 650)),
    ],
    relationships=[
        rel("e1", "browser", "ingress"),
        rel("e2", "ingress", "appangular"), rel("e3", "ingress", "authservice"),
        rel("e4", "ingress", "apigateway"), rel("e5", "ingress", "appreact"),
        rel("e6", "appangular", "authservice", "uses"),
        rel("e7", "apigateway", "identityservice"), rel("e8", "apigateway", "movieservice"),
        rel("e9", "apigateway", "paymentservice"), rel("e10", "apigateway", "reviewservice"),
        rel("e11", "apigateway", "testservice"),
        rel("e12", "authservice", "apigateway", "uses"),
        rel("e13", "identityservice", "rabbitmq", "uses"), rel("e14", "movieservice", "rabbitmq", "uses"),
        rel("e15", "paymentservice", "rabbitmq", "uses"), rel("e16", "reviewservice", "rabbitmq", "uses"),
        rel("e17", "testservice", "rabbitmq", "uses"),
    ],
    metadata={"source_repository": {
        "repo_url": "https://github.com/roman-bilyak/Microservice.Architecture",
        "commit": "3a3413b40114b810def53960aeb92a8026a71dcb",
        "license": "MIT",
        "diagram_provenance": "official",
        "note": "Each service also has its own MS SQL database shown adjacent to it in the diagram; omitted as separate components here to keep this first annotation pass tractable (see docs/cv_failure_cases.md).",
    }},
))

# ───────────────────────── 10. Istio Bookinfo (derived) ────────────────────
GRAPHS.append(ArchGraph(
    id="istio_bookinfo_derived",
    name="Bookinfo sample (istio/istio) - derived from source",
    graph_type="intended",
    source="data/diagrams/raw/istio_bookinfo_derived.png",
    components=[
        comp("productpage", "productpage", "service", (370, 40, 530, 110)),
        comp("details", "details", "service", (120, 220, 280, 290)),
        comp("reviews", "reviews", "service", (620, 220, 780, 290)),
        comp("ratings", "ratings", "service", (620, 380, 780, 450)),
    ],
    relationships=[
        rel("e1", "productpage", "details"),
        rel("e2", "productpage", "reviews"),
        rel("e3", "reviews", "ratings"),
    ],
    metadata={"source_repository": {
        "repo_url": "https://github.com/istio/istio",
        "commit": "399ef1bff5261a01708c13b73a93cdc20189b08a",
        "license": "Apache-2.0",
        "diagram_provenance": "derived",
        "evidence": [
            "samples/bookinfo/src/productpage/productpage.py:53-54,62-64,267 (details service config + getProductDetails())",
            "samples/bookinfo/src/productpage/productpage.py:57-58,74-76,272 (reviews service config + getProductReviews())",
            "samples/bookinfo/src/reviews/reviews-application/src/main/java/application/rest/LibertyRestEndpoint.java:42-44,151,191 (ratings_service URL + getRatings())",
        ],
    }},
))


def main():
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = [json.loads(g.model_dump_json()) for g in GRAPHS]
    MANIFEST_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {len(GRAPHS)} manifest entries to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
