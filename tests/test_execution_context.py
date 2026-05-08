import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


class ExecutionContextTests(unittest.TestCase):
    def test_build_implementation_execution_context_uses_upstream_deltas_and_contract(self) -> None:
        from agent_team.execution_context import build_stage_execution_context
        from agent_team.models import AcceptanceContract
        from agent_team.stage_contracts import build_stage_contract
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            store = StateStore(Path(temp_dir))
            session = store.create_session(
                "Build a runtime-controlled Implementation handoff.",
                contract=AcceptanceContract(
                    acceptance_criteria=["Implementation receives approved technical design before coding."],
                    required_evidence=["roles/implementation/attempt-001/execution-contexts/implementation-input-context.json"],
                ),
                runtime_mode="harness",
            )
            self._record_route_artifact(store, session.session_id)
            self._record_product_definition_artifact(store, session.session_id)
            self._record_project_runtime_artifact(store, session.session_id)
            self._record_technical_design_artifact(store, session.session_id)
            contract = build_stage_contract(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Implementation",
            )

            context = build_stage_execution_context(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Implementation",
                contract=contract,
            )

        self.assertEqual(context.stage, "Implementation")
        self.assertEqual(context.contract_id, contract.contract_id)
        self.assertIn("Build a runtime-controlled Implementation handoff.", context.original_request_summary)
        self.assertIn("Approved Product Definition Delta", context.approved_product_definition_summary)
        self.assertIn("Use the approved technical design", context.approved_technical_design_content)
        self.assertEqual(context.required_outputs, ["implementation.md"])
        self.assertEqual(context.required_evidence, ["self_code_review", "self_verification"])
        self.assertEqual(context.acceptance_matrix[0]["id"], "AC-001")
        self.assertEqual(
            context.acceptance_matrix[0]["criterion"],
            "Implementation receives approved technical design before coding.",
        )
        artifact_names = {artifact.name for artifact in context.relevant_artifacts}
        self.assertIn("route", artifact_names)
        self.assertIn("product_definition", artifact_names)
        self.assertIn("project_runtime", artifact_names)
        self.assertIn("technical_design", artifact_names)

    def test_build_implementation_execution_context_includes_actionable_findings(self) -> None:
        from agent_team.execution_context import build_stage_execution_context
        from agent_team.models import Finding
        from agent_team.stage_contracts import build_stage_contract
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            store = StateStore(Path(temp_dir))
            session = store.create_session("Build Implementation handoff with findings.", runtime_mode="harness")
            self._record_product_definition_artifact(store, session.session_id)
            store.record_feedback(
                session.session_id,
                Finding(
                    source_stage="Verification",
                    target_stage="Implementation",
                    issue="Missing empty-state verification.",
                    severity="high",
                    required_evidence=["empty-state test output"],
                    completion_signal="Implementation evidence includes empty-state coverage.",
                ),
            )
            contract = build_stage_contract(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Implementation",
            )

            context = build_stage_execution_context(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Implementation",
                contract=contract,
            )

        self.assertEqual(len(context.actionable_findings), 1)
        self.assertEqual(context.actionable_findings[0].issue, "Missing empty-state verification.")
        self.assertEqual(context.actionable_findings[0].target_stage, "Implementation")

    def test_state_store_persists_execution_context_by_stage_and_round(self) -> None:
        from agent_team.execution_context import build_stage_execution_context
        from agent_team.stage_contracts import build_stage_contract
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            store = StateStore(Path(temp_dir))
            session = store.create_session("Persist Implementation handoff.", runtime_mode="harness")
            self._record_product_definition_artifact(store, session.session_id)
            contract = build_stage_contract(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Implementation",
            )
            context = build_stage_execution_context(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Implementation",
                contract=contract,
            )

            path = store.save_execution_context(context)
            loaded = store.load_execution_context(session.session_id, "Implementation")

        self.assertEqual(path.name, "implementation-input-context.json")
        self.assertEqual(path.parent.name, "execution-contexts")
        self.assertEqual(path.parent.parent.name, "attempt-001")
        self.assertEqual(path.parent.parent.parent.name, "implementation")
        self.assertEqual(path.parent.parent.parent.parent.name, "roles")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["context_id"], context.context_id)
        self.assertEqual(loaded["stage"], "Implementation")
        self.assertEqual(loaded["session_id"], session.session_id)
        self.assertEqual(loaded["contract_id"], contract.contract_id)
        self.assertEqual(loaded["round_index"], 1)
        self.assertEqual(loaded["required_outputs"], ["implementation.md"])

    def test_session_handoff_execution_context_excludes_state_artifact_summaries(self) -> None:
        from agent_team.execution_context import build_stage_execution_context
        from agent_team.stage_contracts import build_stage_contract
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            store = StateStore(Path(temp_dir))
            session = store.create_session("Handoff the scoped prompt.", runtime_mode="harness")
            self._record_route_artifact(store, session.session_id)
            self._record_product_definition_artifact(store, session.session_id)
            self._record_project_runtime_artifact(store, session.session_id)
            self._record_technical_design_artifact(store, session.session_id)
            self._record_implementation_artifact(store, session.session_id)
            self._record_verification_artifact(store, session.session_id)
            self._record_governance_review_artifact(store, session.session_id)
            self._record_acceptance_artifact(store, session.session_id)
            execution_context_path = session.session_dir / "previous-execution-context.json"
            execution_context_path.write_text('{"stage": "Verification", "leak": "context"}')
            summary = store.load_workflow_summary(session.session_id)
            summary.artifact_paths["execution_context"] = str(execution_context_path)
            store.save_workflow_summary(session, summary)

            contract = build_stage_contract(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="SessionHandoff",
            )
            context = build_stage_execution_context(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="SessionHandoff",
                contract=contract,
            )

        artifact_names = {artifact.name for artifact in context.relevant_artifacts}
        self.assertIn("route", artifact_names)
        self.assertIn("product_definition", artifact_names)
        self.assertIn("project_runtime", artifact_names)
        self.assertIn("technical_design", artifact_names)
        self.assertIn("implementation", artifact_names)
        self.assertIn("verification", artifact_names)
        self.assertIn("governance_review", artifact_names)
        self.assertIn("acceptance", artifact_names)
        self.assertNotIn("execution_context", artifact_names)
        self.assertNotIn("workflow_summary", artifact_names)
        self.assertIn("Use the approved technical design", context.approved_technical_design_content)

    def _record_route_artifact(self, store, session_id: str) -> None:
        self._record_artifact(
            store,
            session_id,
            stage="Route",
            artifact_name="route-packet.json",
            artifact_content='{"affected_layers":["L1","L2"]}',
            evidence_name="route_classification",
            artifact_key="route",
        )

    def _record_product_definition_artifact(self, store, session_id: str) -> None:
        self._record_artifact(
            store,
            session_id,
            stage="ProductDefinition",
            artifact_name="product-definition-delta.md",
            artifact_content=(
                "# Approved Product Definition Delta\n\n"
                "## Acceptance\n"
                "- Implementation receives approved technical design before coding.\n"
            ),
            evidence_name="l1_classification",
            artifact_key="product_definition",
        )

    def _record_project_runtime_artifact(self, store, session_id: str) -> None:
        self._record_artifact(
            store,
            session_id,
            stage="ProjectRuntime",
            artifact_name="project-landing-delta.md",
            artifact_content="# Project Landing Delta\n\n## Defaults\n- Use repo default runtime.\n",
            evidence_name="project_landing_review",
            artifact_key="project_runtime",
        )

    def _record_technical_design_artifact(self, store, session_id: str) -> None:
        self._record_artifact(
            store,
            session_id,
            stage="TechnicalDesign",
            artifact_name="technical-design.md",
            artifact_content="# Approved Technical Design\n\n## Implementation Approach\nUse the approved technical design.\n",
            evidence_name="technical_design_plan",
            artifact_key="technical_design",
        )

    def _record_implementation_artifact(self, store, session_id: str) -> None:
        self._record_artifact(
            store,
            session_id,
            stage="Implementation",
            artifact_name="implementation.md",
            artifact_content="# Implementation\n\nImplemented the requested behavior.\n",
            evidence_name="self_verification",
            artifact_key="implementation",
            evidence_kind="command",
        )

    def _record_verification_artifact(self, store, session_id: str) -> None:
        self._record_artifact(
            store,
            session_id,
            stage="Verification",
            artifact_name="verification-report.md",
            artifact_content="# Verification Report\n\npassed.\n",
            evidence_name="independent_verification",
            artifact_key="verification",
            evidence_kind="command",
        )

    def _record_governance_review_artifact(self, store, session_id: str) -> None:
        self._record_artifact(
            store,
            session_id,
            stage="GovernanceReview",
            artifact_name="governance-review.md",
            artifact_content="# Governance Review\n\npassed.\n",
            evidence_name="layer_governance_review",
            artifact_key="governance_review",
        )

    def _record_acceptance_artifact(self, store, session_id: str) -> None:
        self._record_artifact(
            store,
            session_id,
            stage="Acceptance",
            artifact_name="acceptance-report.md",
            artifact_content="# Acceptance Report\n\nrecommended_go.\n",
            evidence_name="product_and_governance_validation",
            artifact_key="acceptance",
        )

    def _record_artifact(
        self,
        store,
        session_id: str,
        *,
        stage: str,
        artifact_name: str,
        artifact_content: str,
        evidence_name: str,
        artifact_key: str,
        evidence_kind: str = "artifact",
    ) -> None:
        from agent_team.models import EvidenceItem, StageResultEnvelope

        session = store.load_session(session_id)
        evidence_kwargs = {}
        if evidence_kind == "command":
            evidence_kwargs = {"command": "python -m pytest", "exit_code": 0}
        result = StageResultEnvelope(
            session_id=session_id,
            contract_id=f"{stage}-contract",
            stage=stage,
            status="completed",
            artifact_name=artifact_name,
            artifact_content=artifact_content,
            journal=f"# {stage} Journal\n",
            evidence=[
                EvidenceItem(
                    name=evidence_name,
                    kind=evidence_kind,
                    summary=f"{stage} evidence documented.",
                    **evidence_kwargs,
                )
            ],
            summary=f"{stage} completed.",
        )
        stage_record = store.record_stage_result(session_id, result)
        summary = store.load_workflow_summary(session_id)
        summary.artifact_paths[artifact_key] = str(stage_record.artifact_path)
        store.save_workflow_summary(session, summary)


if __name__ == "__main__":
    unittest.main()
