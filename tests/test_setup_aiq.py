from pathlib import Path

import pytest

from healthcare_alm.setup_aiq import AIQ_SHA256, AIQ_VERSION, verify_sha256


def test_aiq_pin_matches_approved_release():
    assert AIQ_VERSION == "2.2.0-rc3"
    assert AIQ_SHA256 == "93c5c6014e08390d7c80241b39919491fc2a9d260b6226c65c0aad96839c8228"


def test_verify_sha256_fails_closed(tmp_path: Path):
    archive = tmp_path / "aiq.tar.gz"
    archive.write_bytes(b"wrong archive")

    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        verify_sha256(archive, AIQ_SHA256)
