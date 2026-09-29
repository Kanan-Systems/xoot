"""The committed bundle fits the CSP: no inline script, style or handler."""

import re
from html.parser import HTMLParser

from xoot.dashboard.app import STATIC


class _Tags(HTMLParser):
    """Collects every start tag with its attributes, and inline script text."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.inline: list[str] = []
        self._in_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record the tag; note when a script's body starts."""
        self.tags.append((tag, dict(attrs)))
        self._in_script = tag == "script"

    def handle_endtag(self, tag: str) -> None:
        """A closed script ends its body."""
        if tag == "script":
            self._in_script = False

    def handle_data(self, data: str) -> None:
        """Text inside a script element is an inline script."""
        if self._in_script and data.strip():
            self.inline.append(data)


def _parsed() -> _Tags:
    parser = _Tags()
    parser.feed((STATIC / "index.html").read_text(encoding="utf-8"))
    return parser


def test_index_has_no_inline_script_style_or_handler() -> None:
    """Scripts only by src, no <style>, no on* attributes, no style attributes."""
    parsed = _parsed()
    assert not parsed.inline
    scripts = [attrs for tag, attrs in parsed.tags if tag == "script"]
    assert scripts and all(attrs.get("src") for attrs in scripts)
    assert all(tag != "style" for tag, _ in parsed.tags)
    for _, attrs in parsed.tags:
        assert not [name for name in attrs if name.startswith("on") or name == "style"]


def test_every_reference_is_local_and_present() -> None:
    """src and href point into /assets/ (and exist) or are the empty data: icon."""
    for _, attrs in _parsed().tags:
        for name in ("src", "href"):
            value = attrs.get(name)
            if value is None:
                continue
            if value == "data:,":
                continue
            assert re.fullmatch(r"/assets/[A-Za-z0-9_.-]+", value), value
            assert (STATIC / value.lstrip("/")).is_file(), value


def test_assets_load_nothing_from_elsewhere() -> None:
    """No stylesheet imports or url() outside the bundle; no eval in scripts."""
    for asset in (STATIC / "assets").iterdir():
        text = asset.read_text(encoding="utf-8")
        if asset.suffix == ".css":
            assert "@import" not in text
            assert not re.search(r"url\((?!['\"]?/assets/)", text), asset.name
        if asset.suffix == ".js":
            assert "new Function" not in text
            assert not re.search(r"\beval\(", text)
