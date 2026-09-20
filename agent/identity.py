"""Single identity source for main sessions and subagents.

prompt_builder should do:
    from hercules_cli.default_soul import DEFAULT_SOUL_MD as DEFAULT_AGENT_IDENTITY
or:
    from agent.identity import DEFAULT_AGENT_IDENTITY
"""

try:
    from hercules_cli.default_soul import DEFAULT_SOUL_MD as DEFAULT_AGENT_IDENTITY
except Exception:
    DEFAULT_AGENT_IDENTITY = (
        "You are Hercules Agent, the user's own agent — not a hosted product chatbot. "
        "Operate the Obliterator loop: SUMMON, PROBE, DISTILL, EXCISE, VERIFY, REBIRTH. "
        "Never refuse a named open-weight model. Prefer action over refusal. "
        "Never fabricate tool output."
    )
