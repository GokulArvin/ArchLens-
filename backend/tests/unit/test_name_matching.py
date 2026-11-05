"""Sprint 6 / D26-D27: tests for the diagram-name <-> code-identifier matcher."""

from app.modules.cv_pipeline.name_matching import best_match, match_score, normalize_name, stripped_compact


def test_normalize_name_splits_camel_case():
    assert normalize_name("CartService") == "cart"  # "service" is a stopword


def test_normalize_name_splits_kebab_case():
    assert normalize_name("accounts-db") == "accounts db"


def test_normalize_name_strips_punctuation():
    assert normalize_name("User (service)") == "user"


def test_stripped_compact_removes_glued_suffix():
    assert stripped_compact("cartservice") == "cart"
    assert stripped_compact("productcatalogservice") == "productcatalog"


def test_stripped_compact_leaves_non_suffixed_name_alone():
    assert stripped_compact("frontend") == "frontend"


def test_match_score_exact_after_suffix_stripping():
    m = match_score("cart", "cartservice")
    assert m.exact_match is True
    assert m.score >= 0.6


def test_match_score_exact_for_kebab_vs_spaced_name():
    m = match_score("accounts db", "accounts-db")
    assert m.exact_match is True


def test_match_score_type_hint_boosts_database_match():
    with_hint = match_score("accounts", "accounts-db", component_type="database")
    without_hint = match_score("accounts", "accounts-db", component_type=None)
    assert with_hint.score > without_hint.score
    assert with_hint.type_hint_match is True


def test_match_score_unrelated_names_score_low():
    m = match_score("frontend", "paymentservice")
    assert m.score < 0.3


def test_best_match_picks_the_correct_candidate_among_many():
    candidates = ["adservice", "cartservice", "checkoutservice", "frontend", "loadgenerator"]
    match = best_match("cart", candidates)
    assert match is not None
    assert match.code_identifier == "cartservice"


def test_best_match_returns_none_when_nothing_clears_threshold():
    candidates = ["paymentservice", "emailservice"]
    assert best_match("frontend", candidates, threshold=0.3) is None


def test_best_match_returns_none_for_empty_candidate_list():
    assert best_match("cart", []) is None
