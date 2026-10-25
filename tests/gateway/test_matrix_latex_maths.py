"""Outbound ``$...$`` / ``$$...$$`` become Element ``data-mx-maths`` markup."""

from gateway.config import PlatformConfig
from plugins.platforms.matrix.adapter import MatrixAdapter


def _adapter() -> MatrixAdapter:
    return MatrixAdapter(
        PlatformConfig(
            enabled=True,
            token="syt_test_token",
            extra={
                "homeserver": "https://matrix.example.org",
                "user_id": "@bot:example.org",
            },
        )
    )


def test_inline_and_display_math_survive_sanitizer_with_escaped_tex():
    html = _adapter()._markdown_to_html("Wave: $a<b$ and $$\\hat{H}\\Psi = E\\Psi$$")
    assert '<span data-mx-maths="a&lt;b">a&lt;b</span>' in html
    assert (
        '<div data-mx-maths="\\hat{H}\\Psi = E\\Psi">\\hat{H}\\Psi = E\\Psi</div>'
        in html
    )
    assert "$" not in html


def test_unpaired_dollars_and_sentinel_collisions_pass_through_unchanged():
    text = "Costs $5 or $10 today; HERCULESTEXINLINE7HERCULESTEXEND is not ours"
    assert _adapter()._markdown_to_html(text) == text


def test_dollars_inside_code_are_never_math():
    adapter = _adapter()
    assert adapter._markdown_to_html("`a=$x; b=$y`") == "<code>a=$x; b=$y</code>"
    fenced = adapter._markdown_to_html("```\necho $A $B$\n```")
    assert "data-mx-maths" not in fenced
    assert "echo $A $B$" in fenced


def test_message_content_keeps_raw_tex_in_plain_body():
    text = "Wave: $a<b$ and $$\\hat{H}\\Psi = E\\Psi$$"
    content = _adapter()._build_text_message_content(text)
    assert 'data-mx-maths="a&lt;b"' in content["formatted_body"]
    assert content["body"] == text
