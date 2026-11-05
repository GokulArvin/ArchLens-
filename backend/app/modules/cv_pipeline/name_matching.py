"""
Sprint 6 / D26 + D27: candidate matching between diagram component names and
real code module/service identifiers.

D26's mapping definition: a diagram component's `name` (e.g. "Cart",
"accounts db") is matched against a real repository's directory/module
names (e.g. "cartservice", "accounts-db") by normalizing both to a common
token form, then scoring token overlap, suffix-stripped exact/substring
matches, and `ArchComponent.type` hints (D27's "normalized names, aliases,
type hints" features). This module defines the matching *features*; D28
tests it against real repository listings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Common service-naming suffixes that get glued onto an identifier with no
# separator (e.g. "cartservice") - stripped for exact/substring comparison.
_SUFFIXES = ("microservice", "service", "api", "svc")

# Words that carry no matching signal on their own.
_STOPWORDS = {"service", "microservice", "api", "the", "a", "an", "server", "svc"}

# Component-type -> code-identifier keywords that hint at that type.
TYPE_HINTS: dict[str, set[str]] = {
    "database": {"db", "database", "sql", "repository", "store", "postgres", "mysql", "mongo"},
    "queue": {"queue", "mq", "bus", "broker", "topic", "rabbitmq", "kafka"},
    "gateway": {"gateway", "ingress", "proxy", "router", "apigateway"},
    "frontend": {"frontend", "ui", "web", "client", "webapp"},
    "cache": {"cache", "redis"},
    "external": {"external", "thirdparty"},
}


def normalize_name(name: str) -> str:
    """CamelCase/kebab-case/snake_case/spaced name -> lowercase space-separated tokens, stopwords dropped."""
    s = re.sub(r"(?<!^)(?=[A-Z])", " ", name)  # split camelCase/PascalCase
    s = re.sub(r"[-_/\\]+", " ", s)  # split kebab-case, snake_case, paths
    s = re.sub(r"[^a-zA-Z0-9 ]", " ", s)  # drop punctuation
    tokens = [t.lower() for t in s.split() if t.lower() not in _STOPWORDS]
    return " ".join(tokens)


def tokenize(name: str) -> set[str]:
    return set(normalize_name(name).split())


def _compact(name: str) -> str:
    return normalize_name(name).replace(" ", "")


def stripped_compact(name: str) -> str:
    """Compact form with a trailing service/api/svc suffix removed, if present."""
    c = _compact(name)
    for suf in _SUFFIXES:
        if c.endswith(suf) and len(c) > len(suf):
            return c[: -len(suf)]
    return c


@dataclass
class MatchScore:
    code_identifier: str
    score: float
    jaccard: float
    exact_match: bool
    substring_match: bool
    type_hint_match: bool

    def to_dict(self) -> dict:
        return {
            "code_identifier": self.code_identifier,
            "score": round(self.score, 4),
            "jaccard": round(self.jaccard, 4),
            "exact_match": self.exact_match,
            "substring_match": self.substring_match,
            "type_hint_match": self.type_hint_match,
        }


def match_score(diagram_name: str, code_identifier: str, component_type: str | None = None) -> MatchScore:
    d_tokens, c_tokens = tokenize(diagram_name), tokenize(code_identifier)
    union = d_tokens | c_tokens
    jaccard = len(d_tokens & c_tokens) / len(union) if union else 0.0

    d_stripped, c_stripped = stripped_compact(diagram_name), stripped_compact(code_identifier)
    exact_match = bool(d_stripped) and d_stripped == c_stripped
    substring_match = (not exact_match) and bool(d_stripped) and (d_stripped in c_stripped or c_stripped in d_stripped)

    type_hint_match = bool(component_type and component_type in TYPE_HINTS and TYPE_HINTS[component_type] & c_tokens)

    score = 0.4 * jaccard + (0.6 if exact_match else 0.3 if substring_match else 0.0) + (0.2 if type_hint_match else 0.0)
    return MatchScore(
        code_identifier=code_identifier,
        score=min(1.0, score),
        jaccard=jaccard,
        exact_match=exact_match,
        substring_match=substring_match,
        type_hint_match=type_hint_match,
    )


def best_match(
    diagram_name: str,
    candidates: list[str],
    component_type: str | None = None,
    threshold: float = 0.3,
) -> MatchScore | None:
    """Best-scoring candidate above threshold, or None if nothing qualifies."""
    if not candidates:
        return None
    scored = [match_score(diagram_name, c, component_type) for c in candidates]
    scored.sort(key=lambda m: m.score, reverse=True)
    best = scored[0]
    return best if best.score >= threshold else None
