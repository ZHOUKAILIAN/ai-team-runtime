import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


class ExecutionContextTests(unittest.TestCase):
    def test_build_dev_execution_context_uses_approved_prd_and_contract(self) -> None:
        from agent_team.execution_context import build_stage_execution_context
        from agent_team.models import AcceptanceContract
        from agent_team.stage_contracts import build_stage_contract
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            store = StateStore(Path(temp_dir))
            session = store.create_session(
                "Build a runtime-controlled Dev handoff.",
                contract=AcceptanceContract(
                    acceptance_criteria=["Dev receives approved PRD context before implementation."],
                    required_evidence=["roles/dev/attempt-001/execution-contexts/dev-input-context.json"],
                ),
                runtime_mode="harness",
            )
            self._record_product_artifact(store, session.session_id)
            self._record_tech_plan_artifact(store, session.session_id)
            contract = build_stage_contract(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Dev",
            )

            context = build_stage_execution_context(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Dev",
                contract=contract,
            )

        self.assertEqual(context.stage, "Dev")
        self.assertEqual(context.contract_id, contract.contract_id)
        self.assertIn("Build a runtime-controlled Dev handoff.", context.original_request_summary)
        self.assertIn("Approved Product PRD", context.approved_prd_summary)
        self.assertIn("Use the approved technical plan", context.approved_tech_plan_content)
        self.assertEqual(context.required_outputs, ["implementation.md"])
        self.assertEqual(context.required_evidence, ["self_code_review", "self_verification"])
        self.assertEqual(context.acceptance_matrix[0]["id"], "AC-001")
        self.assertEqual(
            context.acceptance_matrix[0]["criterion"],
            "Dev receives approved PRD context before implementation.",
        )
        self.assertIn("Dev/context.md", context.repo_context_summary)

    def test_build_dev_execution_context_includes_actionable_findings(self) -> None:
        from agent_team.execution_context import build_stage_execution_context
        from agent_team.models import Finding
        from agent_team.stage_contracts import build_stage_contract
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            store = StateStore(Path(temp_dir))
            session = store.create_session("Build Dev handoff with findings.", runtime_mode="harness")
            self._record_product_artifact(store, session.session_id)
            store.record_feedback(
                session.session_id,
                Finding(
                    source_stage="QA",
                    target_stage="Dev",
                    issue="Missing empty-state verification.",
                    severity="high",
                    required_evidence=["empty-state test output"],
                    completion_signal="Dev evidence includes empty-state coverage.",
                ),
            )
            contract = build_stage_contract(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Dev",
            )

            context = build_stage_execution_context(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Dev",
                contract=contract,
            )

        self.assertEqual(len(context.actionable_findings), 1)
        self.assertEqual(context.actionable_findings[0].issue, "Missing empty-state verification.")
        self.assertEqual(context.actionable_findings[0].target_stage, "Dev")

    def test_state_store_persists_execution_context_by_stage_and_round(self) -> None:
        from agent_team.execution_context import build_stage_execution_context
        from agent_team.stage_contracts import build_stage_contract
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            store = StateStore(Path(temp_dir))
            session = store.create_session("Persist Dev handoff.", runtime_mode="harness")
            self._record_product_artifact(store, session.session_id)
            contract = build_stage_contract(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Dev",
            )
            context = build_stage_execution_context(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Dev",
                contract=contract,
            )

            path = store.save_execution_context(context)
            loaded = store.load_execution_context(session.session_id, "Dev")

        self.assertEqual(path.name, "dev-input-context.json")
        self.assertEqual(path.parent.name, "execution-contexts")
        self.assertEqual(path.parent.parent.name, "attempt-001")
        self.assertEqual(path.parent.parent.parent.name, "dev")
        self.assertEqual(path.parent.parent.parent.parent.name, "roles")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["context_id"], context.context_id)
        self.assertEqual(loaded["stage"], "Dev")
        self.assertEqual(loaded["session_id"], session.session_id)
        self.assertEqual(loaded["contract_id"], contract.contract_id)
        self.assertEqual(loaded["round_index"], 1)
        self.assertEqual(loaded["required_outputs"], ["implementation.md"])

    def test_acceptance_execution_context_excludes_dev_qa_and_state_artifact_summaries(self) -> None:
        from agent_team.execution_context import build_stage_execution_context
        from agent_team.stage_contracts import build_stage_contract
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            store = StateStore(Path(temp_dir))
            session = store.create_session("Accept the scoped prompt.", runtime_mode="harness")
            self._record_product_artifact(store, session.session_id)
            self._record_tech_plan_artifact(store, session.session_id)
            self._record_dev_artifact(store, session.session_id)
            self._record_qa_artifact(store, session.session_id)
            execution_context_path = session.session_dir / "previous-execution-context.json"
            execution_context_path.write_text('{"stage": "QA", "leak": "qa context"}')
            summary = store.load_workflow_summary(session.session_id)
            summary.artifact_paths["execution_context"] = str(execution_context_path)
            store.save_workflow_summary(session, summary)

            contract = build_stage_contract(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Acceptance",
            )
            context = build_stage_execution_context(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Acceptance",
                contract=contract,
            )

        artifact_names = {artifact.name for artifact in context.relevant_artifacts}
        self.assertIn("product", artifact_names)
        self.assertTrue({"acceptance_plan", "acceptance_plan.md"} & artifact_names)
        self.assertNotIn("technical_plan", artifact_names)
        self.assertNotIn("dev", artifact_names)
        self.assertNotIn("qa", artifact_names)
        self.assertNotIn("execution_context", artifact_names)
        self.assertNotIn("workflow_summary", artifact_names)
        self.assertEqual(context.approved_tech_plan_content, "")

    def _record_product_artifact(self, store, session_id: str) -> None:
        from agent_team.models import EvidenceItem, StageResultEnvelope

        session = store.load_session(session_id)
        result = StageResultEnvelope(
            session_id=session_id,
            contract_id="product-contract",
            stage="Product",
            status="completed",
            artifact_name="product-requirements.md",
            artifact_content=(
                "# Approved Product PRD\n\n"
                "## Summary\n"
                "Build a runtime-controlled Dev handoff.\n\n"
                "## Acceptance Criteria\n"
                "- Dev receives approved PRD context before implementation.\n"
            ),
            journal="# Product Journal\n",
            supplemental_artifacts={
                "acceptance_plan.md": (
                    "# Acceptance Plan\n\n"
                    "## Verification\n"
                    "- Dev receives approved PRD context before implementation.\n"
                )
            },
            evidence=[
                EvidenceItem(
                    name="explicit_acceptance_criteria",
                    kind="report",
                    summary="Acceptance criteria documented.",
                ),
                EvidenceItem(
                    name="explicit_acceptance_plan",
                    kind="artifact",
                    summary="Acceptance plan documented.",
                )
            ],
            summary="Drafted PRD.",
        )
        stage_record = store.record_stage_result(session_id, result)
        summary = store.load_workflow_summary(session_id)
        summary.artifact_paths["product"] = str(stage_record.artifact_path)
        summary.artifact_paths["prd"] = str(stage_record.artifact_path)
        summary.artifact_paths.update(stage_record.supplemental_artifact_paths)
        store.save_workflow_summary(session, summary)

    def _record_tech_plan_artifact(self, store, session_id: str) -> None:
        from agent_team.models import EvidenceItem, StageResultEnvelope

        session = store.load_session(session_id)
        result = StageResultEnvelope(
            session_id=session_id,
            contract_id="dev-technical-plan-contract",
            stage="Dev",
            status="completed",
            artifact_name="technical_plan.md",
            artifact_content=(
                "# Approved Technical Plan\n\n"
                "## Implementation Approach\n"
                "Use the approved technical plan.\n"
            ),
            journal="# Dev Technical Plan Journal\n",
            evidence=[
                EvidenceItem(
                    name="implementation_plan",
                    kind="report",
                    summary="Technical plan documented.",
                )
            ],
            summary="Drafted technical plan.",
        )
        stage_record = store.record_stage_result(session_id, result)
        summary = store.load_workflow_summary(session_id)
        summary.artifact_paths["technical_plan"] = str(stage_record.artifact_path)
        store.save_workflow_summary(session, summary)

    def _record_dev_artifact(self, store, session_id: str) -> None:
        from agent_team.models import EvidenceItem, StageResultEnvelope

        session = store.load_session(session_id)
        result = StageResultEnvelope(
            session_id=session_id,
            contract_id="dev-contract",
            stage="Dev",
            status="completed",
            artifact_name="implementation.md",
            artifact_content="# Implementation\n\nDev implemented the requested behavior.\n",
            journal="# Dev Journal\n",
            evidence=[
                EvidenceItem(
                    name="self_verification",
                    kind="command",
                    summary="Dev verification passed.",
                    command="node index.js",
                    exit_code=0,
                ),
                EvidenceItem(
                    name="self_code_review",
                    kind="report",
                    summary="Self review completed.",
                ),
            ],
            summary="Implemented.",
        )
        stage_record = store.record_stage_result(session_id, result)
        summary = store.load_workflow_summary(session_id)
        summary.artifact_paths["dev"] = str(stage_record.artifact_path)
        store.save_workflow_summary(session, summary)

    def _record_qa_artifact(self, store, session_id: str) -> None:
        from agent_team.models import EvidenceItem, StageResultEnvelope

        session = store.load_session(session_id)
        result = StageResultEnvelope(
            session_id=session_id,
            contract_id="qa-contract",
            stage="QA",
            status="completed",
            artifact_name="qa_report.md",
            artifact_content="# QA Report\n\nQA passed.\n",
            journal="# QA Journal\n",
            evidence=[
                EvidenceItem(
                    name="independent_verification",
                    kind="command",
                    summary="QA verification passed.",
                    command="node index.js",
                    exit_code=0,
                )
            ],
            summary="QA passed.",
        )
        stage_record = store.record_stage_result(session_id, result)
        summary = store.load_workflow_summary(session_id)
        summary.artifact_paths["qa"] = str(stage_record.artifact_path)
        store.save_workflow_summary(session, summary)


if __name__ == "__main__":
    unittest.main()
