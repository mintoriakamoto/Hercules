"""Example: Fully integrated agentic harness.

Shows how all components work together to create a complete agent system.
"""

from agent.harness import Agent, AgentState, AgentEvent, ExecutionEngine, ResourceLimits
from agent.harness.state_manager import StateManager
from agent.harness.proof_builder import ProofBuilder, ProofVerifier, VerificationLevel
from agent.harness.agent_algebra import Plan, Step, Sequential, Parallel
from agent.harness.message_bus import MessageBus, MessageType
from typing import Any, Dict


class CodeAnalysisAgent(Agent):
    """Example agent: Analyzes code structure."""

    def __init__(self):
        super().__init__("code_analyzer", "Code Analysis Agent")
        self.state_manager = StateManager("code_analyzer.db")

    def plan(self, task: Any) -> Plan:
        """Plan code analysis."""
        steps = {
            "parse": Step(
                id="parse",
                name="Parse Code",
                execute=lambda x: self._parse_code(x),
                dependencies=[],
            ),
            "analyze": Step(
                id="analyze",
                name="Analyze Structure",
                execute=lambda x: self._analyze_structure(x),
                dependencies=["parse"],
            ),
            "report": Step(
                id="report",
                name="Generate Report",
                execute=lambda x: self._generate_report(x),
                dependencies=["analyze"],
            ),
        }

        return Plan(
            steps=steps,
            dependencies={
                "parse": [],
                "analyze": ["parse"],
                "report": ["analyze"],
            },
        )

    def execute_step(self, step: Step, context: Dict) -> Any:
        """Execute step with verification."""
        result = step.execute(context)

        # Save checkpoint after each step
        checkpoint_id = self.state_manager.save_checkpoint(
            step=hash(step.id),
            state_data={"step": step.id, "result": str(result)[:100]},
        )

        self.record_trace(
            AgentEvent.STEP_COMPLETE,
            {"step": step.id},
            {"result": str(result)[:100]},
            {"checkpoint_id": checkpoint_id},
            f"Step {step.id} completed",
        )

        return result

    def _parse_code(self, context: Dict) -> Dict[str, Any]:
        """Parse code (stub)."""
        return {"lines": 100, "functions": 5}

    def _analyze_structure(self, parsed: Dict) -> Dict[str, Any]:
        """Analyze code structure (stub)."""
        return {
            **parsed,
            "complexity": "moderate",
            "issues": ["unused_import", "long_function"],
        }

    def _generate_report(self, analysis: Dict) -> str:
        """Generate report (stub)."""
        return f"Code analysis: {len(analysis.get('issues', []))} issues found"


class CodeImplementationAgent(Agent):
    """Example agent: Implements code changes."""

    def __init__(self):
        super().__init__("code_implementer", "Code Implementation Agent")
        self.state_manager = StateManager("code_implementer.db")

    def plan(self, task: Any) -> Plan:
        """Plan code implementation."""
        steps = {
            "design": Step(
                id="design",
                name="Design Solution",
                execute=lambda x: self._design_solution(x),
                dependencies=[],
            ),
            "generate": Step(
                id="generate",
                name="Generate Code",
                execute=lambda x: self._generate_code(x),
                dependencies=["design"],
            ),
            "test": Step(
                id="test",
                name="Run Tests",
                execute=lambda x: self._run_tests(x),
                dependencies=["generate"],
            ),
            "verify": Step(
                id="verify",
                name="Verify Output",
                execute=lambda x: self._verify_output(x),
                dependencies=["test"],
            ),
        }

        return Plan(
            steps=steps,
            dependencies={
                "design": [],
                "generate": ["design"],
                "test": ["generate"],
                "verify": ["test"],
            },
        )

    def execute_step(self, step: Step, context: Dict) -> Any:
        """Execute step with proof generation."""
        # Build proof during execution
        proof_builder = ProofBuilder(
            proof_id=f"proof_{step.id}",
            task=self.name,
        )
        proof_builder.add_precondition(f"Step {step.id} prerequisites met")
        proof_builder.add_step(
            step_num=1,
            description=f"Execute {step.id}",
            precondition=f"Preconditions for {step.id} valid",
            action=f"Run {step.id}",
            postcondition=f"Step {step.id} succeeded",
        )

        result = step.execute(context)

        # Add evidence
        proof_builder.add_evidence(
            claim=f"{step.id} executed successfully",
            evidence_type="execution",
            data={"result": str(result)[:100]},
            confidence=0.95,
        )

        proof = proof_builder.build()

        # Verify proof
        is_valid = ProofVerifier.verify(proof, VerificationLevel.ASSERTION)

        self.record_trace(
            AgentEvent.STEP_COMPLETE,
            {"step": step.id},
            {"result": str(result)[:100], "proof_valid": is_valid},
            {"proof_id": proof.proof_id},
            f"Step {step.id} verified",
        )

        return result

    def _design_solution(self, context: Dict) -> Dict[str, Any]:
        """Design solution (stub)."""
        return {"approach": "refactoring", "files_affected": 3}

    def _generate_code(self, design: Dict) -> str:
        """Generate code (stub)."""
        return "def improved_function():\n    pass"

    def _run_tests(self, code: str) -> Dict[str, Any]:
        """Run tests (stub)."""
        return {"passed": 10, "failed": 0, "coverage": 0.95}

    def _verify_output(self, test_results: Dict) -> bool:
        """Verify output (stub)."""
        return test_results["failed"] == 0


async def example_integrated_harness():
    """Example: Run integrated harness with multiple agents."""
    print("=" * 60)
    print("INTEGRATED AGENTIC HARNESS EXAMPLE")
    print("=" * 60)

    # 1. Create agents
    analyzer = CodeAnalysisAgent()
    implementer = CodeImplementationAgent()

    # 2. Create execution engines
    analyzer_engine = ExecutionEngine(analyzer, ResourceLimits(max_api_calls=10))
    implementer_engine = ExecutionEngine(implementer, ResourceLimits(max_tokens=2000))

    # 3. Create message bus
    bus = MessageBus()
    await bus.register_agent("code_analyzer")
    await bus.register_agent("code_implementer")

    # 4. Generate plans
    analysis_plan = analyzer.plan({"code": "sample code"})
    impl_plan = implementer.plan({"analysis": "from analyzer"})

    # 5. Execute analyzer
    print("\n→ Executing code analyzer...")
    analysis_result = analyzer_engine.execute(analysis_plan)

    if analysis_result.success:
        print("✓ Analysis succeeded")
        print(f"  Trace entries: {len(analysis_result.trace)}")
        print(f"  Resources used: {analysis_result.resource_usage}")
    else:
        print(f"✗ Analysis failed: {analysis_result.error}")

    # 6. Send result via message bus
    print("\n→ Sending analysis results via message bus...")
    message_id = await bus.send_message(
        from_agent="code_analyzer",
        to_agent="code_implementer",
        message_type=MessageType.RESPONSE,
        payload={"analysis": analysis_result.output},
    )
    print(f"✓ Message sent: {message_id}")

    # 7. Execute implementer
    print("\n→ Executing code implementer...")
    impl_result = implementer_engine.execute(impl_plan)

    if impl_result.success:
        print("✓ Implementation succeeded")
        print(f"  Trace entries: {len(impl_result.trace)}")
        print(f"  Proof valid: {impl_result.proof.get('proof_method') == 'trace_validation'}")
    else:
        print(f"✗ Implementation failed: {impl_result.error}")

    # 8. Summary
    print("\n" + "=" * 60)
    print("EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Analyzer: {analyzer.state}")
    print(f"Implementer: {implementer.state}")
    print(f"Total trace entries: {len(analyzer.trace) + len(implementer.trace)}")

    # 9. Get conversation history
    conversations = bus.message_log
    print(f"Total messages: {len(conversations)}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_integrated_harness())
