"""Sprint 1 / D2: the resolution/format policy must be enforced in code, not just described.

Full preprocessing behavior (resize correctness, unreadable files, aspect
ratio, output dimensions) is Sprint 2's D10 - this only checks that the
policy from docs/cv_pipeline_note.md is actually wired into CVPreprocessor.
"""

import pytest

from app.modules.cv_pipeline.pipeline import ALLOWED_INPUT_EXTENSIONS, DEFAULT_MAX_SIZE, CVPreprocessor


def test_default_max_size_matches_documented_policy():
    assert DEFAULT_MAX_SIZE == 1920
    assert CVPreprocessor().max_size == DEFAULT_MAX_SIZE


def test_allowed_extensions_match_documented_policy():
    assert ALLOWED_INPUT_EXTENSIONS == {".png", ".jpg", ".jpeg"}


def test_preprocess_rejects_unsupported_format(tmp_path):
    bogus = tmp_path / "diagram.bmp"
    bogus.write_bytes(b"not a real image")
    with pytest.raises(ValueError, match="Unsupported input format"):
        CVPreprocessor().preprocess(str(bogus))
