from hercules_cli.hermes import MARKERS, OFFICIAL, format_report, scan


def test_markers_include_requested_trees():
    kinds = {m[0] for m in MARKERS}
    for name in ("claude", "opencode", "openclaw", "langchain", "hermes-home", "hercules"):
        assert name in kinds


def test_scan_shape():
    data = scan()
    assert data["mesh"] == "hermes"
    assert data["official"] == OFFICIAL
    assert "nousresearch" not in data["official"].lower()
    assert isinstance(data["hits"], list)
    text = format_report(data)
    assert "Hermes mesh" in text
    assert "Nous Research" not in text
    assert "mintoriakamoto/Hercules" in text
