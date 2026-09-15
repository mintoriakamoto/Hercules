"""Tests for the hercules-tools-as-MCP server module surface.

We don't run a live MCP session in unit tests — that requires the codex
subprocess + client + an event loop. These tests pin the static
contract: the module imports, the EXPOSED_TOOLS list is sane, and the
build helper assembles a server when the SDK is present.
"""

from __future__ import annotations




class TestModuleSurface:
    def test_module_imports_clean(self):
        from agent.transports import hercules_tools_mcp_server as m
        assert callable(m.main)
        assert callable(m._build_server)
        assert isinstance(m.EXPOSED_TOOLS, tuple)
        assert len(m.EXPOSED_TOOLS) > 0

    def test_exposed_tools_are_safe_subset(self):
        """We MUST NOT expose tools codex already has, because codex'
        own builtins are better-integrated with its sandbox + approvals.
        Specifically: no terminal/shell, no read_file/write_file, no
        patch — those are codex's built-in tools."""
        from agent.transports.hercules_tools_mcp_server import EXPOSED_TOOLS
        forbidden = {
            "terminal", "shell", "read_file", "write_file", "patch",
            "search_files", "process",
        }
        leaked = forbidden & set(EXPOSED_TOOLS)
        assert not leaked, (
            f"these tools must NOT be exposed via the codex callback "
            f"because codex has built-in equivalents: {leaked}"
        )

    def test_expected_hercules_specific_tools_listed(self):
        """The Hercules-specific tools should be present so users on the
        codex runtime keep access to them."""
        from agent.transports.hercules_tools_mcp_server import EXPOSED_TOOLS
        for required in (
            "web_search",
            "web_extract",
            "browser_navigate",
            "vision_analyze",
            "image_generate",
            "skill_view",
        ):
            assert required in EXPOSED_TOOLS, f"missing {required!r}"

    def test_agent_loop_tools_not_exposed(self):
        """delegate_task / memory / session_search / todo require the
        running AIAgent context to dispatch, so a stateless MCP callback
        can't drive them. They must NOT be in EXPOSED_TOOLS."""
        from agent.transports.hercules_tools_mcp_server import EXPOSED_TOOLS
        for agent_loop_tool in ("delegate_task", "memory", "session_search", "todo"):
            assert agent_loop_tool not in EXPOSED_TOOLS, (
                f"{agent_loop_tool!r} requires the agent loop context "
                "and can't be reached through a stateless MCP callback"
            )

    def test_kanban_worker_tools_exposed(self):
        """Kanban workers run as `hercules chat -q` subprocesses; if they
        come up on the codex_app_server runtime, the worker can do the
        actual work via codex's shell but needs the kanban tools through
        the MCP callback to report back to the kernel. Without these
        tools available, the worker would hang at completion time."""
        from agent.transports.hercules_tools_mcp_server import EXPOSED_TOOLS
        # Worker handoff tools — every dispatched worker uses at least
        # one of {complete, block, comment} to close out its task.
        for worker_tool in (
            "kanban_complete",
            "kanban_block",
            "kanban_comment",
            "kanban_heartbeat",
        ):
            assert worker_tool in EXPOSED_TOOLS, (
                f"{worker_tool!r} missing from codex callback — kanban "
                "workers on codex_app_server runtime would hang"
            )

    def test_kanban_orchestrator_tools_exposed(self):
        """Orchestrator agents need to dispatch new tasks, query the
        board, and unblock/link tasks. Exposed so an orchestrator on
        codex_app_server can do its job."""
        from agent.transports.hercules_tools_mcp_server import EXPOSED_TOOLS
        for orch_tool in (
            "kanban_create",
            "kanban_show",
            "kanban_list",
            "kanban_unblock",
            "kanban_link",
        ):
            assert orch_tool in EXPOSED_TOOLS, (
                f"{orch_tool!r} missing from codex callback"
            )


class TestMain:
    def test_main_returns_2_when_mcp_unavailable(self, monkeypatch):
        """When the mcp package isn't installed, main() should exit
        cleanly with code 2 and an install hint, not crash."""
        import agent.transports.hercules_tools_mcp_server as m

        def boom_build(*a, **kw):
            raise ImportError("mcp not installed")

        monkeypatch.setattr(m, "_build_server", boom_build)
        rc = m.main(["--verbose"])
        assert rc == 2

    def test_main_handles_keyboard_interrupt(self, monkeypatch):
        import agent.transports.hercules_tools_mcp_server as m

        class FakeServer:
            def run(self):
                raise KeyboardInterrupt()

        monkeypatch.setattr(m, "_build_server", lambda: FakeServer())
        rc = m.main([])
        assert rc == 0

    def test_main_returns_1_on_runtime_error(self, monkeypatch):
        import agent.transports.hercules_tools_mcp_server as m

        class CrashingServer:
            def run(self):
                raise RuntimeError("boom")

        monkeypatch.setattr(m, "_build_server", lambda: CrashingServer())
        rc = m.main([])
        assert rc == 1


class TestSchemaBridging:
    """FastMCP derives the argument model from the handler's signature.

    A bare ``**kwargs`` handler registers as a tool with one required string
    field named ``kwargs`` and every real call fails validation. These tests
    pin the fix: the synthesised signature accepts the tool's real arguments
    and clients see Hercules' own JSON schema.
    """

    SCHEMA = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "search query"},
            "max_results": {"type": "integer"},
        },
        "required": ["query"],
    }

    def _server(self, calls):
        import asyncio  # noqa: F401 - keep import local; module is loop-free

        pytest = __import__("pytest")
        fastmcp = pytest.importorskip("mcp.server.fastmcp")
        import agent.transports.hercules_tools_mcp_server as m

        def dispatch(name, args):
            calls.append((name, dict(args)))
            return "ok"

        mcp = fastmcp.FastMCP("t")
        handler = m._make_handler("web_search", "desc", self.SCHEMA, dispatch)
        mcp.add_tool(handler, name="web_search", description="desc")
        m._publish_input_schema(mcp, "web_search", self.SCHEMA)
        return mcp

    def test_published_input_schema_is_hercules_schema(self):
        import asyncio

        mcp = self._server([])
        tools = asyncio.run(mcp.list_tools())
        assert [t.name for t in tools] == ["web_search"]
        assert tools[0].inputSchema == self.SCHEMA

    def test_call_dispatches_real_arguments_and_drops_omitted_optionals(self):
        import asyncio

        calls = []
        mcp = self._server(calls)
        asyncio.run(mcp.call_tool("web_search", {"query": "x"}))
        assert calls[-1] == ("web_search", {"query": "x"})
        asyncio.run(mcp.call_tool("web_search", {"query": "x", "max_results": 3}))
        assert calls[-1] == ("web_search", {"query": "x", "max_results": 3})

    def test_missing_required_argument_is_rejected(self):
        import asyncio

        pytest = __import__("pytest")
        calls = []
        mcp = self._server(calls)
        with pytest.raises(Exception):
            asyncio.run(mcp.call_tool("web_search", {"max_results": 3}))
        assert calls == []

    def test_handler_without_parameters_still_callable(self):
        import asyncio

        pytest = __import__("pytest")
        fastmcp = pytest.importorskip("mcp.server.fastmcp")
        import agent.transports.hercules_tools_mcp_server as m

        calls = []
        schema = {"type": "object", "properties": {}}
        mcp = fastmcp.FastMCP("t")
        handler = m._make_handler("skills_list", "d", schema, lambda n, a: calls.append((n, a)) or "ok")
        mcp.add_tool(handler, name="skills_list", description="d")
        m._publish_input_schema(mcp, "skills_list", schema)
        asyncio.run(mcp.call_tool("skills_list", {}))
        assert calls == [("skills_list", {})]
