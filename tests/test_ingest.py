"""File ingestion must preserve information, not summarise it."""

from __future__ import annotations

import json

from peerlens.services import ingest


def test_supported_extensions():
    for name in ("a.pdf", "b.txt", "c.md", "d.tex", "e.csv", "f.json"):
        assert ingest.is_supported(name)
    assert not ingest.is_supported("results.xlsx")
    assert not ingest.is_supported("archive.zip")


def test_plain_text_is_read_verbatim():
    body = "H1: humidity readings improve prediction.\nE4 varies two things at once."
    outcome = ingest.extract_text(body.encode(), "notes.md")
    assert outcome.text == body
    assert "Markdown" in outcome.note


def test_csv_keeps_exact_values():
    csv_bytes = b"method,mae_celsius,run\nours,2.1,1\nbaseline,2.9,1\n"
    outcome = ingest.extract_text(csv_bytes, "results.csv")
    # Exact values must survive: rounding results would corrupt the science.
    assert "2.1" in outcome.text
    assert "2.9" in outcome.text
    assert "2 data rows" in outcome.text
    assert "mae_celsius" in outcome.text


def test_csv_truncation_is_disclosed():
    rows = "\n".join(f"run{i},{i}" for i in range(ingest.MAX_CSV_ROWS + 50))
    outcome = ingest.extract_text(f"name,value\n{rows}\n".encode(), "big.csv")
    assert "further rows not shown" in outcome.text
    assert str(ingest.MAX_CSV_ROWS) in outcome.note


def test_json_is_pretty_printed():
    payload = {"experiment": "E4", "accuracy": 0.748}
    outcome = ingest.extract_text(json.dumps(payload).encode(), "run.json")
    assert '"accuracy": 0.748' in outcome.text
    assert "JSON parsed" in outcome.note


def test_invalid_json_falls_back_to_raw_text():
    outcome = ingest.extract_text(b"{not json,,,}", "broken.json")
    assert "not json" in outcome.text
    assert "Invalid JSON" in outcome.note


def test_unsupported_type_reports_rather_than_guessing():
    outcome = ingest.extract_text(b"\x00\x01", "data.bin")
    assert outcome.text == ""
    assert "Unsupported" in outcome.note


def test_store_upload_preserves_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "UPLOAD_DIR", tmp_path)
    data = b"raw research bytes"
    stored = ingest.store_upload(data, "my results (final).csv")
    assert stored.read_bytes() == data
    assert stored.suffix == ".csv"
    assert " " not in stored.name  # sanitised, but still recognisable
