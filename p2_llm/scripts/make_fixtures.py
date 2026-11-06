"""Generate synthetic pilot fixtures shaped exactly like teammates' outputs.

  diagram.png                 P1 input image (rendered; some deliberately noisy / abbreviated)
  detections.json             P1 detector output   [{id,bbox,class,confidence}]
  geometry_candidates.json    P1/P3 geometric relation candidates [{id,source,target,confidence}]
  annotation.json             gold labels (what P2 annotates by hand in Sprint 2)
  code_entities.json          P3 source entities   [{id,name,kind,path}]
  alignment_gold.json         diagram id -> code entity id | null | "AMBIGUOUS"
  violation.json              P4 evidence package + ground_truth block (Design §3.3 / §8.1)

These are SYNTHETIC. They exist so the P2 pipeline can be built and tested before the real
ArchLens benchmark is ready. Do not report results on them as research results.

usage: python scripts/make_fixtures.py [out_dir]
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import networkx as nx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOX_W, BOX_H, DX, DY, M = 190, 70, 260, 150, 40

SYSTEMS = [
    dict(
        id="S01_shop", style="clean",
        comps=[("User", "user", 0, 0), ("Web Frontend", "frontend", 1, 0), ("API Gateway", "gateway", 2, 0),
               ("Order Service", "service", 2, 1), ("Payment Service", "service", 3, 1), ("Stripe", "external_system", 3, 2),
               ("Orders DB", "database", 1, 2), ("Kafka", "queue", 2, 2), ("Notification Service", "service", 2, 3)],
        edges=[("User", "Web Frontend"), ("Web Frontend", "API Gateway"), ("API Gateway", "Order Service"),
               ("Order Service", "Orders DB"), ("Order Service", "Payment Service"), ("Payment Service", "Stripe"),
               ("Order Service", "Kafka"), ("Kafka", "Notification Service")],
        code={"Web Frontend": ("WebFrontend", "web-frontend/src"), "API Gateway": ("ApiGateway", "gateway/src"),
              "Order Service": ("OrderService", "order-service/src"), "Payment Service": ("PaymentService", "payment-service/src"),
              "Orders DB": ("OrdersDatabase", "database/orders"), "Kafka": ("EventBusProducer", "messaging/kafka"),
              "Notification Service": ("NotificationService", "notification-service/src")},
        distractors=[("OrderServiceTest", "order-service/test"), ("SharedUtils", "common/utils")],
        layer_of={"User": "Actor", "Web Frontend": "UI", "API Gateway": "Gateway", "Order Service": "Service",
                  "Payment Service": "Service", "Notification Service": "Service", "Orders DB": "Data", "Kafka": "Messaging",
                  "Stripe": "External"},
        rules={"allowed": ["Actor->UI", "UI->Gateway", "Gateway->Service", "Service->Service", "Service->Data",
                           "Service->Messaging", "Messaging->Service", "Service->External"],
               "forbidden": ["UI->Data", "UI->Service", "Gateway->Data", "UI->Messaging"]},
        violation=dict(type="forbidden_dependency", source="Web Frontend", target="Orders DB", via="API Gateway",
                       file="web-frontend/src/OrderHistoryPage.java", lines="12-31",
                       snippet="import database.orders.OrdersRepository;\n...\nList<Order> rows = OrdersRepository.findByUser(userId);",
                       commits=[("a1b2c3d4", "Add order history page", ["web-frontend/src/OrderHistoryPage.java"],
                                 "+import database.orders.OrdersRepository;\n+List<Order> rows = OrdersRepository.findByUser(userId);", True),
                                ("9f8e7d6c", "Bump dependency versions", ["pom.xml"], "-<version>2.1</version>\n+<version>2.2</version>", False),
                                ("5a4b3c2d", "Fix gateway timeout", ["gateway/src/Routes.java"], "-timeout=5\n+timeout=30", False)],
                       root_cause_keywords=["order history", "direct", "repository", "frontend"]),
    ),
    dict(
        id="S02_layered", style="noisy",
        comps=[("Customer", "user", 0, 0), ("Web UI", "frontend", 1, 0), ("Order Controller", "component", 2, 0),
               ("Order Service", "service", 2, 1), ("Order Repository", "component", 2, 2), ("Database", "database", 1, 2)],
        edges=[("Customer", "Web UI"), ("Web UI", "Order Controller"), ("Order Controller", "Order Service"),
               ("Order Service", "Order Repository"), ("Order Repository", "Database")],
        code={"Web UI": ("WebUi", "ui/web"), "Order Controller": ("OrderController", "app/controller"),
              "Order Service": ("OrderService", "app/service"), "Order Repository": ("OrderRepository", "app/repository"),
              "Database": ("DataSourceConfig", "app/persistence")},
        distractors=[("OrderDto", "app/dto"), ("OrderMapper", "app/mapper")],
        layer_of={"Customer": "Actor", "Web UI": "UI", "Order Controller": "Controller", "Order Service": "Service",
                  "Order Repository": "Repository", "Database": "Data"},
        rules={"allowed": ["Actor->UI", "UI->Controller", "Controller->Service", "Service->Repository", "Repository->Data"],
               "forbidden": ["Controller->Repository", "Repository->Controller", "Controller->Data", "UI->Repository"]},
        violation=dict(type="layer_violation", source="Order Controller", target="Order Repository", via="Order Service",
                       file="app/controller/OrderController.java", lines="45-52",
                       snippet="private final OrderRepository orderRepository;\n...\nreturn orderRepository.findById(id);",
                       commits=[("abc12345", "Refactor order processing", ["app/controller/OrderController.java"],
                                 "+private final OrderRepository orderRepository;\n+return orderRepository.findById(id);", True),
                                ("def67890", "Add request logging", ["app/config/Logging.java"], "+log.info(req)", False),
                                ("0badc0de", "Update README", ["README.md"], "+## Setup", False)],
                       root_cause_keywords=["refactor", "order processing", "repository", "controller"]),
    ),
    dict(
        id="S03_logistics", style="abbrev",
        comps=[("Shipping Svc", "service", 0, 0), ("Inventory Svc", "service", 1, 0), ("Inv DB", "database", 2, 0),
               ("Ship Queue", "queue", 0, 1), ("Billing Svc", "service", 1, 1), ("Pmt Svc", "service", 2, 1)],
        edges=[("Shipping Svc", "Inventory Svc"), ("Inventory Svc", "Inv DB"), ("Shipping Svc", "Ship Queue"),
               ("Billing Svc", "Pmt Svc")],
        code={"Shipping Svc": ("ShippingService", "shipping/src"), "Inventory Svc": ("InventoryService", "inventory/src"),
              "Inv DB": ("InventoryDatabase", "inventory/db"), "Ship Queue": ("ShipmentEventsTopic", "shipping/events"),
              "Billing Svc": ("BillingService", "billing/src"), "Pmt Svc": ("PaymentService", "payment/src")},
        distractors=[("InventoryClientMock", "billing/test")],
        layer_of={"Shipping Svc": "Service", "Inventory Svc": "Service", "Billing Svc": "Service", "Pmt Svc": "Service",
                  "Inv DB": "Data", "Ship Queue": "Messaging"},
        rules={"allowed": ["Shipping Svc->Inventory Svc", "Inventory Svc->Inv DB", "Shipping Svc->Ship Queue", "Billing Svc->Pmt Svc"],
               "forbidden": [], "policy": "service-to-service edges absent from the intended graph are UNEXPECTED"},
        violation=dict(type="unexpected_coupling", source="Billing Svc", target="Inventory Svc", via=None,
                       file="billing/src/InvoiceBuilder.java", lines="88-97",
                       snippet="InventoryClient inv = new InventoryClient(INVENTORY_URL);\nif (!inv.inStock(sku)) throw ...",
                       commits=[("77aa88bb", "Billing: check stock before invoicing", ["billing/src/InvoiceBuilder.java"],
                                 "+InventoryClient inv = new InventoryClient(INVENTORY_URL);\n+if (!inv.inStock(sku)) throw new OutOfStock();", True),
                                ("33cc44dd", "Rename invoice fields", ["billing/src/Invoice.java"], "-amt\n+amount", False)],
                       root_cause_keywords=["stock", "invoicing", "billing", "inventory"]),
    ),
    dict(
        id="S04_modular", style="clean",
        comps=[("Search Module", "module", 0, 0), ("Catalog API", "interface", 1, 0), ("Catalog Module", "module", 2, 0),
               ("Search Index", "database", 0, 1), ("Catalog DB", "database", 2, 1)],
        edges=[("Search Module", "Catalog API"), ("Catalog API", "Catalog Module"), ("Search Module", "Search Index"),
               ("Catalog Module", "Catalog DB")],
        code={"Search Module": ("search", "modules/search"), "Catalog API": ("CatalogApi", "modules/catalog/api"),
              "Catalog Module": ("catalog", "modules/catalog"), "Search Index": ("ElasticIndex", "modules/search/index"),
              "Catalog DB": ("CatalogDatabase", "modules/catalog/db")},
        distractors=[("catalog.internal.PriceCalculatorImpl", "modules/catalog/internal")],
        layer_of={"Search Module": "Search", "Catalog API": "CatalogPublic", "Catalog Module": "CatalogInternal",
                  "Search Index": "Data", "Catalog DB": "Data"},
        rules={"allowed": ["Search->CatalogPublic", "CatalogPublic->CatalogInternal", "Search->Data", "CatalogInternal->Data"],
               "forbidden": ["Search->CatalogInternal"]},
        violation=dict(type="boundary_violation", source="Search Module", target="Catalog Module", via="Catalog API",
                       file="modules/search/RankingService.java", lines="20-24",
                       snippet="import catalog.internal.PriceCalculatorImpl;\ndouble p = new PriceCalculatorImpl().effectivePrice(item);",
                       commits=[("c0ffee11", "Rank search results by effective price", ["modules/search/RankingService.java"],
                                 "+import catalog.internal.PriceCalculatorImpl;\n+double p = new PriceCalculatorImpl().effectivePrice(item);", True),
                                ("beef2222", "Tune index refresh", ["modules/search/index/Config.java"], "-refresh=1s\n+refresh=5s", False)],
                       root_cause_keywords=["price", "internal", "ranking", "catalog"]),
    ),
    dict(
        id="S05_cycle", style="noisy",
        comps=[("Auth Service", "service", 0, 0), ("User Service", "service", 1, 0), ("Profile Service", "service", 2, 0),
               ("Users DB", "database", 1, 1)],
        edges=[("Auth Service", "User Service"), ("User Service", "Profile Service"), ("User Service", "Users DB")],
        code={"Auth Service": ("AuthService", "auth/src"), "User Service": ("UserService", "users/src"),
              "Profile Service": ("ProfileService", "profile/src"), "Users DB": ("UsersDatabase", "users/db")},
        distractors=[("AuthTokenUtil", "common/auth")],
        layer_of={"Auth Service": "Service", "User Service": "Service", "Profile Service": "Service", "Users DB": "Data"},
        rules={"allowed": ["Auth Service->User Service", "User Service->Profile Service", "User Service->Users DB"],
               "forbidden": ["Profile Service->Auth Service"], "policy": "no dependency cycles between services"},
        violation=dict(type="circular_dependency", source="Profile Service", target="Auth Service", via=None,
                       file="profile/src/AvatarController.java", lines="30-33",
                       snippet="if (!authService.validate(token)) return 401;",
                       # the introducing commit is NOT in the supplied history (squashed import) -> expect UNCERTAIN
                       commits=[("1111aaaa", "Add avatar upload size limit", ["profile/src/AvatarController.java"],
                                 "+if (file.size() > MAX) return 413;", False),
                                ("2222bbbb", "Squash-import profile module", ["profile/README.md"], "+profile module", False)],
                       root_cause_keywords=[], expected_status="UNCERTAIN"),
    ),
    dict(
        id="S06_missing", style="abbrev",
        comps=[("Checkout Service", "service", 0, 0), ("Fraud Service", "service", 1, 0), ("Payment Gateway", "external_system", 2, 0),
               ("Orders DB", "database", 0, 1)],
        edges=[("Checkout Service", "Fraud Service"), ("Checkout Service", "Payment Gateway"), ("Checkout Service", "Orders DB")],
        code={"Checkout Service": ("CheckoutService", "checkout/src"), "Fraud Service": ("FraudService", "fraud/src"),
              "Orders DB": ("OrdersDatabase", "checkout/db")},
        distractors=[("FraudRulesEngine", "fraud/rules"), ("FraudServiceClient", "checkout/clients")],
        layer_of={"Checkout Service": "Service", "Fraud Service": "Service", "Payment Gateway": "External", "Orders DB": "Data"},
        rules={"allowed": ["Checkout Service->Fraud Service", "Checkout Service->Payment Gateway", "Checkout Service->Orders DB"],
               "forbidden": [], "required": ["Checkout Service->Fraud Service"]},
        violation=dict(type="missing_dependency", source="Checkout Service", target="Fraud Service", via=None,
                       file="checkout/src/CheckoutFlow.java", lines="60-64",
                       snippet="// fraudClient.score(order);  // disabled for launch\npaymentGateway.charge(order);",
                       commits=[("fa11fa11", "Temporarily disable fraud check for launch", ["checkout/src/CheckoutFlow.java"],
                                 "-FraudScore s = fraudClient.score(order);\n+// fraudClient.score(order);  // disabled for launch", True),
                                ("ab12cd34", "Add launch banner", ["web/banner.html"], "+<div>Launch!</div>", False)],
                       root_cause_keywords=["disable", "fraud", "launch"]),
    ),
]


def _layout(sys_):
    pos = {}
    for name, _t, col, row in sys_["comps"]:
        x1, y1 = M + col * DX, M + row * DY
        pos[name] = [x1, y1, x1 + BOX_W, y1 + BOX_H]
    w = M * 2 + max(c[2] for c in sys_["comps"]) * DX + BOX_W
    h = M * 2 + max(c[3] for c in sys_["comps"]) * DY + BOX_H
    return pos, (w, h)


def _clip(b, cx, cy, dx, dy):
    """Point where the ray from box centre (cx,cy) in direction (dx,dy) leaves box b."""
    hw, hh = (b[2] - b[0]) / 2, (b[3] - b[1]) / 2
    t = min(hw / abs(dx) if dx else 1e9, hh / abs(dy) if dy else 1e9)
    return cx + dx * t, cy + dy * t


def _arrow(draw, a, b, color, width=3):
    ax, ay = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    bx, by = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    dx, dy = bx - ax, by - ay
    n = math.hypot(dx, dy)
    dx, dy = dx / n, dy / n
    sx, sy = _clip(a, ax, ay, dx, dy)
    ex, ey = _clip(b, bx, by, -dx, -dy)
    draw.line([(sx, sy), (ex, ey)], fill=color, width=width)
    ang = math.atan2(dy, dx)
    L = 14
    p1 = (ex - L * math.cos(ang - 0.4), ey - L * math.sin(ang - 0.4))
    p2 = (ex - L * math.cos(ang + 0.4), ey - L * math.sin(ang + 0.4))
    draw.polygon([(ex, ey), p1, p2], fill=color)


def render(sys_, pos, size, path, rng):
    noisy = sys_["style"] == "noisy"
    bg, fg = ((235, 235, 228), (120, 120, 120)) if noisy else ((255, 255, 255), (20, 20, 20))
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 17)
    for s, t in sys_["edges"]:
        _arrow(d, pos[s], pos[t], fg)
    for name, ctype, *_ in sys_["comps"]:
        b = pos[name]
        if ctype == "database":
            d.rounded_rectangle(b, radius=22, outline=fg, width=3, fill=bg)
            d.arc([b[0], b[1] - 8, b[2], b[1] + 16], 180, 360, fill=fg, width=3)
        elif ctype == "user":
            d.ellipse(b, outline=fg, width=3, fill=bg)
        else:
            d.rectangle(b, outline=fg, width=3, fill=bg)
        tw = d.textlength(name, font=font)
        d.text(((b[0] + b[2] - tw) / 2, (b[1] + b[3]) / 2 - 10), name, fill=fg, font=font)
    if noisy:
        px = img.load()
        for _ in range(size[0] * size[1] // 25):
            x, y = rng.randrange(size[0]), rng.randrange(size[1])
            v = rng.randrange(90, 255)
            px[x, y] = (v, v, v)
        img = img.filter(ImageFilter.GaussianBlur(0.8))
    img.save(path)


def build(out: Path):
    rng = random.Random(42)
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for sys_ in SYSTEMS:
        d = out / sys_["id"]
        d.mkdir(exist_ok=True)
        pos, size = _layout(sys_)
        render(sys_, pos, size, d / "diagram.png", rng)
        ids = {name: f"c{i + 1}" for i, (name, *_r) in enumerate(sys_["comps"])}
        types = {name: t for name, t, *_ in sys_["comps"]}

        # gold annotation
        ann = {"diagram_id": sys_["id"], "image": "diagram.png", "annotator": "synthetic",
               "components": [{"id": ids[n], "name": n, "type": types[n], "bbox": pos[n]} for n in ids],
               "relationships": [{"source": ids[s], "target": ids[t], "type": "depends_on"} for s, t in sys_["edges"]]}
        (d / "annotation.json").write_text(json.dumps(ann, indent=1))

        # P1-shaped detections: jittered boxes, generic class except some databases
        dets = []
        for n in ids:
            j = [v + rng.randint(-6, 6) for v in pos[n]]
            cls = "database" if types[n] == "database" and rng.random() < 0.5 else "architecture_component"
            dets.append({"id": ids[n], "bbox": j, "class": cls, "confidence": round(rng.uniform(0.7, 0.98), 2)})
        (d / "detections.json").write_text(json.dumps(dets, indent=1))

        # geometry candidates: true edges (one with weak confidence), one false positive
        geo = []
        for k, (s, t) in enumerate(sys_["edges"]):
            conf = round(rng.uniform(0.65, 0.95), 2) if k != 1 else 0.42
            geo.append({"id": f"g{k + 1}", "source": ids[s], "target": ids[t], "confidence": conf})
        names = list(ids)
        fp = (names[-1], names[0])
        if fp not in sys_["edges"]:
            geo.append({"id": f"g{len(geo) + 1}", "source": ids[fp[0]], "target": ids[fp[1]], "confidence": 0.3})
        (d / "geometry_candidates.json").write_text(json.dumps(geo, indent=1))

        # P3-shaped code entities + alignment gold
        ents, gold = [], {}
        for n, (cname, path) in sys_["code"].items():
            eid = f"{path}/{cname}"
            ents.append({"id": eid, "name": cname, "kind": "module", "path": path})
            gold[ids[n]] = eid
        for cname, path in sys_["distractors"]:
            ents.append({"id": f"{path}/{cname}", "name": cname, "kind": "class", "path": path})
        for n in ids:
            gold.setdefault(ids[n], None)
        (d / "code_entities.json").write_text(json.dumps(ents, indent=1))
        (d / "alignment_gold.json").write_text(json.dumps(gold, indent=1))

        # current graph = intended +/- violation
        v = sys_["violation"]
        intended = [list(e) for e in sys_["edges"]]
        current = [e for e in intended if not (v["type"] == "missing_dependency" and e == [v["source"], v["target"]])]
        if v["type"] != "missing_dependency":
            current.append([v["source"], v["target"]])
        g = nx.DiGraph(current)
        if v["type"] == "circular_dependency":
            path = [v["source"], v["target"]] + nx.shortest_path(g, v["target"], v["source"])[1:]
        else:
            path = [v["source"], v["target"]]
        # P3 impact function output (upstream dependants of source + downstream of target)
        affected = {}
        for n in nx.ancestors(g, v["source"]) | {v["source"]}:
            affected[n] = 0 if n == v["source"] else nx.shortest_path_length(g, n, v["source"])
        for n in (nx.descendants(g, v["target"]) | {v["target"]}) if v["target"] in g else {v["target"]}:
            dist = 1 if n == v["target"] else 1 + nx.shortest_path_length(g, v["target"], n)
            affected[n] = min(affected.get(n, 99), dist)
        aff = [{"component": n, "distance": dd, "direction": "source" if n == v["source"] else ("upstream" if n in nx.ancestors(g, v["source"]) else "downstream")}
               for n, dd in sorted(affected.items(), key=lambda x: x[1])]
        commits = [{"hash": h, "message": m, "files": f, "diff": df} for h, m, f, df, _ in v["commits"]]
        intro = next((h for h, *_r, is_intro in v["commits"] if is_intro), None)
        pkg = {
            "violation_id": f"{sys_['id']}-V1",
            "violation": {"type": v["type"], "source": v["source"], "target": v["target"],
                          "verdict": "MISSING" if v["type"] == "missing_dependency" else "VIOLATION"},
            "architecture_rule": sys_["rules"],
            "code": {"file": v["file"], "lines": v["lines"], "snippet": v["snippet"]},
            "dependency_path": path,
            "commit": next((c for c in commits if c["hash"] == intro), None),
            "candidate_commits": commits,
            "intended_edges": intended, "current_edges": current,
            "layer_of": sys_["layer_of"], "affected_components": aff,
            "allowed_intermediary": v["via"],
            "ground_truth": {
                "introducing_commit": intro,
                "expected_status": v.get("expected_status", "SUPPORTED"),
                "root_cause_keywords": v["root_cause_keywords"],
                "affected": sorted(affected),
                "expected_fix": ({"add": [[v["source"], v["target"]]], "remove": []} if v["type"] == "missing_dependency"
                                 else {"remove": [[v["source"], v["target"]]], "add": []}),
            },
        }
        (d / "violation.json").write_text(json.dumps(pkg, indent=1))
        index.append({"system_id": sys_["id"], "style": sys_["style"], "violation_type": v["type"], "dir": sys_["id"]})
    (out / "manifest.json").write_text(json.dumps({"synthetic": True, "systems": index}, indent=1))
    print(f"wrote {len(index)} systems to {out}")


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "fixtures" / "synthetic"))
