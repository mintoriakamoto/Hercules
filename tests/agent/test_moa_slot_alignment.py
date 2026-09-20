"""MoA preset slots must line up with the credentials the session has.

Regression cover for the ChatGPT-OAuth (openai-codex) install whose default
preset still named OpenRouter/Anthropic slots: resolution fell back to the
Codex route while carrying the Claude model name through, so every advisor —
and the acting aggregator — died on "model is not supported when using Codex
with a ChatGPT account".
"""

import pytest

from agent import moa_slots


@pytest.fixture(autouse=True)
def _clear_cache():
    moa_slots.clear_availability_cache()
    yield
    moa_slots.clear_availability_cache()


def _available(*names):
    allowed = {n.lower() for n in names}
    return lambda provider: provider.lower() in allowed


def test_unauthenticated_slot_is_realigned_to_session_model(monkeypatch):
    monkeypatch.setattr(moa_slots, "provider_is_available", _available("openai-codex"))
    slot, note = moa_slots.align_slot(
        {"provider": "openrouter", "model": "anthropic/claude-opus-4.8"},
        {"provider": "openai-codex", "model": "gpt-6-astra"},
    )
    assert slot == {"provider": "openai-codex", "model": "gpt-6-astra"}
    assert "openrouter" in note and "not authenticated" in note


def test_authenticated_slot_is_left_alone(monkeypatch):
    monkeypatch.setattr(
        moa_slots, "provider_is_available", _available("openai-codex", "openrouter")
    )
    slot, note = moa_slots.align_slot(
        {"provider": "openrouter", "model": "anthropic/claude-opus-4.8"},
        {"provider": "openai-codex", "model": "gpt-6-astra"},
    )
    assert slot == {"provider": "openrouter", "model": "anthropic/claude-opus-4.8"}
    assert note is None


def test_no_fallback_leaves_slot_untouched(monkeypatch):
    monkeypatch.setattr(moa_slots, "provider_is_available", _available())
    slot, note = moa_slots.align_slot(
        {"provider": "openrouter", "model": "anthropic/claude-opus-4.8"}, None
    )
    assert slot == {"provider": "openrouter", "model": "anthropic/claude-opus-4.8"}
    assert note is None


def test_default_preset_collapses_to_one_advisor_on_codex_only_install(monkeypatch):
    monkeypatch.setattr(moa_slots, "provider_is_available", _available("openai-codex"))
    refs, agg, notes = moa_slots.align_preset_slots(
        [
            {"provider": "openai-codex", "model": "gpt-5.5"},
            {"provider": "openrouter", "model": "deepseek/deepseek-v4-pro"},
        ],
        {"provider": "openrouter", "model": "anthropic/claude-opus-4.8"},
        fallback={"provider": "openai-codex", "model": "gpt-6-astra"},
    )
    # The codex advisor survives as configured; the OpenRouter one realigns
    # onto the session model, and the aggregator (acting model) follows.
    assert refs == [
        {"provider": "openai-codex", "model": "gpt-5.5"},
        {"provider": "openai-codex", "model": "gpt-6-astra"},
    ]
    assert agg == {"provider": "openai-codex", "model": "gpt-6-astra"}
    assert any("deepseek" in n for n in notes)
    assert any("claude" in n for n in notes)


def test_duplicate_advisors_after_realignment_are_dropped(monkeypatch):
    monkeypatch.setattr(moa_slots, "provider_is_available", _available("openai-codex"))
    refs, _agg, notes = moa_slots.align_preset_slots(
        [
            {"provider": "openrouter", "model": "anthropic/claude-opus-4.8"},
            {"provider": "anthropic", "model": "claude-sonnet-4"},
        ],
        {"provider": "openai-codex", "model": "gpt-6-astra"},
        fallback={"provider": "openai-codex", "model": "gpt-6-astra"},
    )
    assert refs == [{"provider": "openai-codex", "model": "gpt-6-astra"}]
    assert any("duplicate" in n for n in notes)


def test_local_providers_need_no_credentials():
    # A deliberately local advisor (Ollama / LM Studio) must never be
    # realigned onto a cloud model just because the auth store has no row.
    assert moa_slots._probe_provider("ollama") is True
    assert moa_slots._probe_provider("lmstudio") is True


def test_availability_probe_fails_open(monkeypatch):
    def _boom(provider):
        raise RuntimeError("auth store unreadable")

    monkeypatch.setattr(moa_slots, "_probe_provider", _boom)
    # A broken probe must not strip a working advisor out of the preset.
    assert moa_slots.provider_is_available("openrouter") is True


def test_session_slot_never_returns_a_preset_name_as_a_model(monkeypatch):
    # A session parked on a MoA preset stores provider "moa" + the preset
    # name as its model. Carrying that through as a fallback would swap one
    # unrunnable slot for another.
    monkeypatch.setattr(moa_slots, "provider_is_available", _available("openai-codex"))
    monkeypatch.setattr(
        "hercules_cli.config.load_config",
        lambda *a, **k: {"model": {"provider": "moa", "default": "default"}},
    )
    monkeypatch.setattr("hercules_cli.auth.get_active_provider", lambda: "openai-codex")
    monkeypatch.setattr(
        "hercules_cli.models.get_default_model_for_provider",
        lambda provider: "gpt-5.5",
    )
    assert moa_slots.session_slot() == {
        "provider": "openai-codex",
        "model": "gpt-5.5",
    }


def test_session_slot_reads_configured_provider_and_model(monkeypatch):
    monkeypatch.setattr(moa_slots, "provider_is_available", _available("openai-codex"))
    monkeypatch.setattr(
        "hercules_cli.config.load_config",
        lambda *a, **k: {"model": {"provider": "openai-codex", "default": "gpt-6-astra"}},
    )
    assert moa_slots.session_slot() == {
        "provider": "openai-codex",
        "model": "gpt-6-astra",
    }
