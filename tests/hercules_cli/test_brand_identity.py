"""Brand-identity regression guards.

The upstream branding survived the ``Hermes -> Hercules`` rename because it was
drawn in *block glyphs*, not letters: the wordmark literally spelled
"HERMES-AGENT" while the variable holding it was already called
``HERCULES_AGENT_LOGO``. No text search could catch that. These tests pin the
identity so it cannot regress silently.
"""

from __future__ import annotations

import pytest


# The distinctive glyph run from the inherited "HERMES-AGENT" art: an "M" drawn
# as ``███╗   ███╗``. Nothing in our own wordmark produces this shape.
_UPSTREAM_M_GLYPHS = "███╗   ███╗"

BRAND_HEXES = ("#F7B23B", "#E8712E", "#C73E3A", "#8E2B3F")


class TestWordmark:
    def test_does_not_spell_the_upstream_name(self):
        from hercules_cli.banner import HERCULES_AGENT_LOGO_RAW

        assert _UPSTREAM_M_GLYPHS not in HERCULES_AGENT_LOGO_RAW

    def test_shape_fits_an_eighty_column_terminal(self):
        from hercules_cli.banner import HERCULES_AGENT_LOGO_RAW

        lines = HERCULES_AGENT_LOGO_RAW.split("\n")
        assert len(lines) == 5
        assert max(len(line) for line in lines) <= 80

    def test_uses_the_unshadowed_block_face(self):
        """Our face is solid blocks — no drop-shadow outline glyphs."""
        from hercules_cli.banner import HERCULES_AGENT_LOGO_RAW

        for shadow_glyph in ("╗", "╝", "╔", "╚"):
            assert shadow_glyph not in HERCULES_AGENT_LOGO_RAW


class TestHeroMark:
    def test_caduceus_is_gone(self):
        """The caduceus is *Hermes'* staff and must not be our hero art."""
        import hercules_cli.banner as banner

        assert not hasattr(banner, "HERCULES_CADUCEUS")
        assert hasattr(banner, "HERCULES_PILLARS")

    def test_pillars_are_symmetric(self):
        """Every row must draw two identical pillars — it's a matched pair."""
        import re

        from hercules_cli.banner import HERCULES_PILLARS

        rows = [
            re.sub(r"\[/?[^\]]*\]", "", row)
            for row in HERCULES_PILLARS.split("\n")
        ]
        assert len(rows) == 8
        for row in rows:
            # The gap between the two pillars is the only run of 3+ spaces.
            segments = [s for s in re.split(r"\s{3,}", row.strip()) if s]
            assert len(segments) == 2, row
            assert segments[0] == segments[1], row


class TestCopiesStayInSync:
    """The wordmark and hero art are duplicated across entry points."""

    def test_cli_matches_banner(self):
        import cli
        import hercules_cli.banner as banner

        assert cli.HERCULES_AGENT_LOGO == banner.HERCULES_AGENT_LOGO
        assert cli.HERCULES_PILLARS == banner.HERCULES_PILLARS


class TestPalette:
    def test_inherited_gold_is_gone(self):
        """The gold spectrum was the upstream project's colour, not ours."""
        import cli
        import hercules_cli.banner as banner

        for module in (cli, banner):
            src = open(module.__file__, encoding="utf-8").read()
            for old in ("#FFD700", "#FFBF00", "#CD7F32", "#B8860B"):
                assert old not in src, f"{old} still in {module.__name__}"

    @pytest.mark.parametrize("hex_color", BRAND_HEXES)
    def test_every_brand_colour_has_a_light_mode_value(self, hex_color):
        """A brand colour with no light-mode remap is unreadable on cream."""
        import cli

        remap = cli._LIGHT_MODE_REMAP
        assert hex_color in remap, f"{hex_color} has no light-mode counterpart"
        assert remap[hex_color] != hex_color

    def test_gradient_anchors_span_the_forge_ramp(self):
        from hercules_cli.banner import _GRADIENT_ANCHORS

        assert len(_GRADIENT_ANCHORS) == 5
        # Ramp runs light -> dark, so overall luminance must fall.
        first, last = _GRADIENT_ANCHORS[0], _GRADIENT_ANCHORS[-1]
        assert sum(first) > sum(last)
