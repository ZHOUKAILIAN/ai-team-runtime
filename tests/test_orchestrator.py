import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


class RuntimeFlowReplacementTests(unittest.TestCase):
    def test_runtime_driver_replaces_legacy_product_dev_qa_orchestrator_flow(self) -> None:
        from agent_team.runtime_driver import RuntimeDriverOptions, run_requirement
        from agent_team.stage_machine import StageMachine
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir)
            first = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                message="执行这个需求：验证五层 runtime flow",
                options=RuntimeDriverOptions(executor="dry-run"),
            )
            self.assertEqual(first.status, "waiting_human")
            self.assertEqual(first.current_state, "WaitForProductDefinitionApproval")
            self.assertEqual(first.current_stage, "ProductDefinition")

            store = StateStore(state_root)
            session = store.load_session(first.session_id)
            summary = store.load_workflow_summary(first.session_id)
            store.save_workflow_summary(session, StageMachine().apply_human_decision(summary=summary, decision="go"))

            second = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                session_id=first.session_id,
                options=RuntimeDriverOptions(executor="dry-run"),
            )
            self.assertEqual(second.status, "waiting_human")
            self.assertEqual(second.current_state, "WaitForTechnicalDesignApproval")
            self.assertEqual(second.current_stage, "TechnicalDesign")

            summary = store.load_workflow_summary(first.session_id)
            store.save_workflow_summary(session, StageMachine().apply_human_decision(summary=summary, decision="go"))

            final = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                session_id=first.session_id,
                options=RuntimeDriverOptions(executor="dry-run", auto_advance_intermediate=True),
            )
            self.assertEqual(final.status, "waiting_human")
            self.assertEqual(final.current_state, "WaitForHumanDecision")
            self.assertEqual(final.current_stage, "SessionHandoff")

            artifact_dir = Path(temp_dir) / first.session_id
            self.assertTrue((artifact_dir / "route-packet.json").exists())
            self.assertTrue((artifact_dir / "product-definition-delta.md").exists())
            self.assertTrue((artifact_dir / "project-landing-delta.md").exists())
            self.assertTrue((artifact_dir / "technical-design.md").exists())
            self.assertTrue((artifact_dir / "implementation.md").exists())
            self.assertTrue((artifact_dir / "verification-report.md").exists())
            self.assertTrue((artifact_dir / "governance-review.md").exists())
            self.assertTrue((artifact_dir / "acceptance-report.md").exists())
            self.assertTrue((artifact_dir / "session-handoff.md").exists())


if __name__ == "__main__":
    unittest.main()
