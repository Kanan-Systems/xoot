"""Every relative link in the docs resolves to an existing file or anchor."""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DOCS = sorted(
    [REPO / "README.md", REPO / "SECURITY.md", REPO / "CONTRIBUTING.md"]
    + list((REPO / "docs").glob("*.md"))
)

FENCE = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
CODE_SPAN = re.compile(r"`[^`\n]*`")
INLINE = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
REFERENCE = re.compile(r"^\[[^\]]+\]:\s*(\S+)", re.MULTILINE)
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def _prose(path: Path) -> str:
    """The file's text without fenced code blocks or code spans."""
    return CODE_SPAN.sub("", FENCE.sub("", path.read_text(encoding="utf-8")))


def _slug(heading: str) -> str:
    """GitHub's anchor for a heading: lowercase, punctuation dropped, dashes."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def _prose_keep_headings(path: Path) -> str:
    # Code spans stay: a heading's code text is part of its anchor.
    return FENCE.sub("", path.read_text(encoding="utf-8"))


def _anchors(path: Path) -> set[str]:
    seen: dict[str, int] = {}
    anchors: set[str] = set()
    for heading in HEADING.findall(_prose_keep_headings(path)):
        slug = _slug(heading)
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def _relative_links(path: Path) -> list[str]:
    text = _prose(path)
    links = INLINE.findall(text) + REFERENCE.findall(text)
    return [link for link in links if not SCHEME.match(link)]


def test_docs_exist() -> None:
    """The top-level docs and at least one docs/ page are present."""
    assert all(doc.is_file() for doc in DOCS)
    assert any(doc.parent.name == "docs" for doc in DOCS)


def test_slug_follows_github() -> None:
    """Punctuation is dropped, case folded and spaces become dashes."""
    assert _slug("Claude Desktop on Windows/WSL") == "claude-desktop-on-windowswsl"
    assert _slug("`xoot paste` and xpaste") == "xoot-paste-and-xpaste"


def test_docs_have_relative_links() -> None:
    """The scan finds links at all, so an empty result cannot pass silently."""
    assert _relative_links(REPO / "README.md")


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: str(p.relative_to(REPO)))
def test_relative_links_resolve(doc: Path) -> None:
    """Each relative link names an existing file and, if given, an anchor in it."""
    for link in _relative_links(doc):
        target, _, anchor = link.partition("#")
        path = (doc.parent / target).resolve() if target else doc
        assert path.is_relative_to(REPO), f"{doc.name}: {link} leaves the repo"
        assert path.exists(), f"{doc.name}: {link} -> missing {path}"
        if anchor:
            assert path.suffix == ".md", f"{doc.name}: anchor on non-markdown {link}"
            assert anchor in _anchors(path), f"{doc.name}: {link} -> no #{anchor}"
