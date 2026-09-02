from hercules_cli.hermes import MARKERS, format_report, scan


def test_markers_include_requested_trees():
    kinds = {m[0] for m in MARKERS}
    for name in ("claude", "opencode", "openclaw", "langchain"):
        assert name in kinds


def test_scan_shape():
    data = scan()
    assert data["mesh"] == "hermes"
    assert data["official"] == "https://github.com/mintoriakamoto/Hercules"
    assert "nousresearch" not in data["official"].lower()
    assert isinstance(data["hits"], list)
    text = format_report(data)
    assert "Hermes mesh" in text
    assert "Nous Research" not in text
