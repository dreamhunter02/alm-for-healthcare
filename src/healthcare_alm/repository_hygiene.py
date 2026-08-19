from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class HygieneFinding:
    category: str
    path: Path
    summary: str


PATTERNS = {
    "absolute_home_path": re.compile(rb"/(?:Users|home)/[A-Za-z0-9._-]+/"),
    "personal_email": re.compile(rb"[A-Za-z0-9._%+-]+@nvidia\.com", re.IGNORECASE),
    "nvidia_api_key": re.compile(rb"nvapi-[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    "private_key": re.compile(rb"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
}

DEFAULT_BLOCKED_IDENTIFIER_HASHES = frozenset(
    {
        "b05c4a6d7778490947a8ec1ab4bb44e1737f1048978787af68874c7f44bdd997",
        "d5d9d19b086cdaaebfaeb49935405d73c26cb71eabafe06ca528c9a8fad7094c",
        "07c525387fffeb0a3bd3465036e517979236e271c61c3c21b2c23412564a3c8b",
    }
)


def _payloads(path: Path) -> list[bytes]:
    payloads = [path.read_bytes()]
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            payloads.extend(
                archive.read(info)
                for info in archive.infolist()
                if not info.is_dir() and info.file_size <= 50_000_000
            )
    elif path.suffix.lower() == ".pdf":
        reader = PdfReader(path, strict=False)
        metadata = "\n".join(str(value) for value in (reader.metadata or {}).values())
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        payloads.append(f"{metadata}\n{text}".encode())
    return payloads


def _contains_blocked_identifier(payloads: list[bytes], blocked_hashes: frozenset[str] | set[str]) -> bool:
    for payload in payloads:
        words = re.findall(r"[A-Za-z0-9_-]+", payload.decode(errors="ignore").lower())
        candidates = [*words, *(f"{left} {right}" for left, right in zip(words, words[1:], strict=False))]
        if any(hashlib.sha256(candidate.encode()).hexdigest() in blocked_hashes for candidate in candidates):
            return True
    return False


def scan_paths(
    paths: list[Path],
    *,
    blocked_identifier_hashes: frozenset[str] | set[str] = DEFAULT_BLOCKED_IDENTIFIER_HASHES,
) -> list[HygieneFinding]:
    findings: list[HygieneFinding] = []
    for path in paths:
        try:
            payloads = _payloads(path)
        except (OSError, ValueError, zipfile.BadZipFile):
            continue
        for category, pattern in PATTERNS.items():
            if any(pattern.search(data) for data in payloads):
                findings.append(
                    HygieneFinding(
                        category=category,
                        path=path,
                        summary=f"{category} detected in {path.name}; value redacted",
                    )
                )
        if _contains_blocked_identifier(payloads, blocked_identifier_hashes):
            findings.append(
                HygieneFinding(
                    category="personal_identifier",
                    path=path,
                    summary=f"personal_identifier detected in {path.name}; value redacted",
                )
            )
    return findings
