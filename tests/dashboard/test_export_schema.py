"""The committed API schema matches a fresh export."""

from pathlib import Path

from xoot.dashboard import export_schema

COMMITTED = Path(__file__).resolve().parents[2] / "dashboard/src/api/schema.json"


def test_committed_schema_matches_a_fresh_export() -> None:
    """Changing a response model without re-exporting fails here."""
    assert (
        COMMITTED.read_text(encoding="utf-8") == export_schema.export()
    ), "run: env/bin/python -m xoot.dashboard.export_schema"


def test_the_default_output_is_the_committed_file() -> None:
    """In a checkout, the module writes where the frontend reads."""
    assert export_schema.DEFAULT_OUTPUT == COMMITTED


def test_main_writes_the_export(tmp_path: Path) -> None:
    """--output writes the same text export() returns."""
    target = tmp_path / "schema.json"
    assert export_schema.main(["--output", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == export_schema.export()


def test_every_response_has_a_definition() -> None:
    """Each envelope and leaf model is a named definition for json2ts."""
    text = export_schema.export()
    for model in export_schema.RESPONSES:
        assert f'"{model.__name__}": {{' in text
    for leaf in ("ItemSummary", "SessionSummary", "DecisionDetail", "EventEntry"):
        assert f'"{leaf}": {{' in text
    for dropped in ("resolved_by", "db_path", '"header"'):
        assert dropped not in text
