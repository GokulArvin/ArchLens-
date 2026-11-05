"""Label normalization dictionary (Sprint 3 D12) and name normalization (used by Sprint 6 alignment).

Two separate jobs:
  * infer_type(name)     -> canonical component TYPE from free text ("Postgres DB" -> database)
  * normalize_name(name) -> canonical NAME key for matching ("OrderSvc", "order-service" -> "order service")
"""
from __future__ import annotations

import re

# canonical type -> aliases (lower-case, matched as whole words / phrases). Order = priority.
TYPE_ALIASES: dict[str, list[str]] = {
    "database": ["database", "db", "rdbms", "postgres", "postgresql", "mysql", "mariadb", "oracle", "sql server",
                 "mssql", "mongodb", "mongo", "dynamodb", "cassandra", "sqlite", "datastore", "data store",
                 "repository db", "warehouse", "data warehouse"],
    "cache": ["cache", "redis", "memcached", "memcache"],
    "queue": ["queue", "mq", "kafka", "rabbitmq", "rabbit", "sqs", "sns", "pubsub", "pub/sub", "topic",
              "event bus", "message bus", "broker", "message broker", "kinesis", "nats", "eventbridge"],
    "storage": ["s3", "blob", "bucket", "object storage", "file storage", "file store", "storage", "cdn"],
    "gateway": ["api gateway", "gateway", "apigw", "load balancer", "lb", "nginx", "proxy", "reverse proxy",
                "ingress", "envoy", "kong", "bff"],
    "frontend": ["frontend", "front end", "front-end", "ui", "web app", "webapp", "web client", "spa",
                 "mobile app", "browser", "client app", "react app", "web ui", "portal", "dashboard"],
    "user": ["user", "users", "actor", "customer", "admin", "end user", "client user", "operator"],
    "external_system": ["external", "third party", "third-party", "3rd party", "stripe", "paypal",
                        "payment provider", "sendgrid", "twilio", "partner api", "legacy system", "saas"],
    "interface": ["interface", "port", "facade", "contract"],
    "module": ["module", "package", "library", "lib", "component library"],
    "service": ["service", "svc", "microservice", "micro service", "api", "server", "backend", "worker",
                "processor", "engine", "handler", "manager", "app server", "lambda", "function"],
}

# Abbreviations expanded before matching names.
ABBREVIATIONS = {
    "svc": "service", "srv": "service", "db": "database", "mgr": "manager", "mgmt": "management",
    "auth": "authentication", "authn": "authentication", "authz": "authorization", "cfg": "config",
    "msg": "message", "notif": "notification", "notifs": "notifications", "repo": "repository",
    "ctrl": "controller", "api gw": "gateway", "apigw": "gateway", "fe": "frontend", "ui": "frontend",
    "inv": "inventory", "pmt": "payment", "pay": "payment", "usr": "user", "acct": "account",
}

# Generic words dropped when building an alignment key (they carry layer, not identity).
GENERIC_SUFFIXES = {"service", "services", "module", "component", "impl", "app", "application", "server",
                    "system", "api", "the", "layer", "microservice", "ms"}

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_NON_ALNUM = re.compile(r"[^a-z0-9/ ]+")


def split_identifier(s: str) -> list[str]:
    s = _CAMEL.sub(" ", s)
    s = s.replace("_", " ").replace("-", " ").replace(".", " ").replace("/", " ")
    return [t for t in _NON_ALNUM.sub(" ", s.lower()).split() if t]


def normalize_name(name: str) -> str:
    toks = split_identifier(name)
    out = []
    for t in toks:
        out.extend(ABBREVIATIONS.get(t, t).split())
    # singularize trivially
    out = [t[:-1] if len(t) > 4 and t.endswith("s") and not t.endswith("ss") else t for t in out]
    return " ".join(out)


def alignment_key(name: str) -> str:
    toks = [t for t in normalize_name(name).split() if t not in GENERIC_SUFFIXES]
    return " ".join(toks) if toks else normalize_name(name)


def infer_type(name: str, default: str = "component") -> tuple[str, float, str]:
    """Return (type, confidence, matched_alias). Purely lexical — a baseline, not the VLM."""
    toks = split_identifier(name)
    text = " " + " ".join(toks) + " "
    # head noun first: in "User Service" the type is decided by "Service", not "User"
    for n in (2, 1):
        head = " ".join(toks[-n:]) if len(toks) >= n else None
        if head:
            for ctype, aliases in TYPE_ALIASES.items():
                if head in aliases:
                    return ctype, (0.85 if ctype != "service" else 0.7), head
    for ctype, aliases in TYPE_ALIASES.items():
        for a in aliases:
            if f" {a} " in text:
                return ctype, (0.85 if ctype != "service" else 0.7), a
    return default, 0.3, ""


def normalize_type_label(label: str) -> str | None:
    """Map an annotator/VLM free-text type ('DB', 'Message Queue', 'ext') to a canonical type, else None."""
    from .schemas import COMPONENT_TYPES
    low = label.strip().lower().replace("-", "_").replace(" ", "_")
    if low in COMPONENT_TYPES:
        return low
    if low in {"ext", "external", "external_service", "3rd_party", "third_party"}:
        return "external_system"
    t, conf, _ = infer_type(label, default="")
    return t or None
