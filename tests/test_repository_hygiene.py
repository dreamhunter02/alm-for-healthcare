import hashlib
import subprocess
import zipfile
from pathlib import Path

from pypdf import PdfWriter

from healthcare_alm.repository_hygiene import scan_paths


def test_repository_hygiene_detects_personal_identity_and_secret_shapes(tmp_path):
    unsafe = tmp_path / "unsafe.txt"
    unsafe.write_text(
        "owner=/" + "Users/example-person/project\n"
        "account=example-person@" + "nvidia.com\n"
        "api_key=nvapi-" + "abcdefghijklmnopqrstuvwxyz012345\n"
        "presenter=Example Person\n"
    )

    blocked = {hashlib.sha256(b"example person").hexdigest()}
    findings = scan_paths([unsafe], blocked_identifier_hashes=blocked)

    assert {finding.category for finding in findings} == {
        "absolute_home_path",
        "personal_email",
        "personal_identifier",
        "nvidia_api_key",
    }
    assert all("abcdefghijklmnopqrstuvwxyz" not in finding.summary for finding in findings)


def test_repository_hygiene_accepts_participant_placeholders(tmp_path):
    safe = tmp_path / ".env.example"
    safe.write_text(
        "NVIDIA_API_KEY=\n"
        "NVIDIA_API_BASE_URL=https://integrate.api.nvidia.com/v1\n"
        "NVIDIA_MODEL_NAME=nvidia/example-model\n"
    )

    assert scan_paths([safe]) == []


def test_repository_hygiene_scans_presentation_xml_and_pdf_metadata(tmp_path):
    deck = tmp_path / "workshop.pptx"
    with zipfile.ZipFile(deck, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ppt/slides/slide1.xml", "presenter=Example Person")

    pdf = tmp_path / "workshop.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Author": "Example Person"})
    with pdf.open("wb") as stream:
        writer.write(stream)

    blocked = {hashlib.sha256(b"example person").hexdigest()}
    findings = scan_paths([deck, pdf], blocked_identifier_hashes=blocked)

    assert [(finding.category, finding.path.name) for finding in findings] == [
        ("personal_identifier", "workshop.pptx"),
        ("personal_identifier", "workshop.pdf"),
    ]


def test_committed_environment_template_is_safe_and_local_env_is_ignored():
    root = Path(__file__).resolve().parents[1]
    example = root / ".env.example"

    assert example.is_file()
    ignored = subprocess.run(["git", "check-ignore", "--quiet", ".env"], cwd=root, check=False)
    assert ignored.returncode == 0
    assert scan_paths([example]) == []
