"""Sprint 5 / D21: tests for the embedding-baseline math.

ComponentEmbedder itself loads CLIP's pretrained weights (seconds per
instantiation, network download on first use) - exercised end-to-end via
backend/scripts/compute_component_embeddings.py (run and verified manually,
see docs/sprint5_vit_geometry_report.md), not via this fast unit-test suite.
cosine_similarity is pure math and is fully covered here.
"""

import pytest

from app.modules.cv_pipeline.embeddings import cosine_similarity


def test_cosine_similarity_identical_vectors_is_one():
    v = [1.0, 2.0, 3.0]
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_opposite_vectors_is_negative_one():
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_is_symmetric():
    a, b = [1.0, 2.0, 0.5], [0.3, -1.0, 2.0]
    assert cosine_similarity(a, b) == pytest.approx(cosine_similarity(b, a))


def test_cosine_similarity_scale_invariant():
    a, b = [1.0, 2.0, 3.0], [2.0, 4.0, 6.0]  # b is 2x a -> same direction
    assert cosine_similarity(a, b) == pytest.approx(1.0)


def test_cosine_similarity_zero_vector_is_zero_not_nan():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
