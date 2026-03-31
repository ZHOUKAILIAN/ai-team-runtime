import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


class OrchestratorTests(unittest.TestCase):
    def test_downstream_findings_create_learning_records(self) -> None:
        from ai_company.backend import StaticBackend
        from ai_company.orchestrator import WorkflowOrchestrator
        from ai_company.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir)
            backend = StaticBackend.fixture(
                product_requirements="Users can create a task",
                prd="PRD v1",
                tech_spec="Tech spec v1",
                qa_report="QA found missing delete flow",
                acceptance_report="Rejected because delete flow missing",
                findings=[
                    {
                        "source_stage": "QA",
                        "target_stage": "Product",
                        "issue": "Delete flow missing from PRD",
                        "severity": "high",
                        "lesson": "Enumerate CRUD scope explicitly.",
                        "proposed_context_update": "Always expand user actions into CRUD coverage.",
                    }
                ],
            )

            result = WorkflowOrchestrator(
                repo_root=repo_root,
                state_store=StateStore(state_root),
                backend=backend,
            ).run(request="Build a task manager")

            learned_memory = (state_root / "memory" / "Product" / "lessons.md").read_text()

            self.assertEqual(result.acceptance_status, "recommended_no_go")
            self.assertIn("Enumerate CRUD scope explicitly.", learned_memory)
            self.assertTrue((state_root / "sessions" / result.session_id / "review.md").exists())

    def test_workflow_summary_reflects_progress_and_final_status(self) -> None:
        from ai_company.backend import StaticBackend
        from ai_company.orchestrator import WorkflowOrchestrator
        from ai_company.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir)
            backend = StaticBackend.fixture(
                product_requirements="Users can create a task",
                prd="PRD v1",
                tech_spec="Tech spec v1",
                qa_report="QA found missing delete flow",
                acceptance_report="Rejected because delete flow missing",
                findings=[
                    {
                        "source_stage": "QA",
                        "target_stage": "Product",
                        "issue": "Delete flow missing from PRD",
                        "severity": "high",
                        "lesson": "Enumerate CRUD scope explicitly.",
                        "proposed_context_update": "Always expand user actions into CRUD coverage.",
                    }
                ],
            )

            result = WorkflowOrchestrator(
                repo_root=repo_root,
                state_store=StateStore(state_root),
                backend=backend,
            ).run(request="Build a task manager")

            summary_path = state_root / "artifacts" / result.session_id / "workflow_summary.md"
            summary = summary_path.read_text()

            self.assertIn("- runtime_mode: deterministic_demo", summary)
            self.assertIn("- current_state: WaitForHumanDecision", summary)
            self.assertIn("- current_stage: Acceptance", summary)
            self.assertIn("- prd_status: drafted", summary)
            self.assertIn("- dev_status: completed", summary)
            self.assertIn("- qa_status: blocked", summary)
            self.assertIn("- acceptance_status: recommended_no_go", summary)

    def test_review_includes_workflow_status_from_orchestrator_run(self) -> None:
        from ai_company.backend import StaticBackend
        from ai_company.orchestrator import WorkflowOrchestrator
        from ai_company.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir)
            backend = StaticBackend.fixture(
                product_requirements="Users can create a task",
                prd="PRD v1",
                tech_spec="Tech spec v1",
                qa_report="QA found missing delete flow",
                acceptance_report="Rejected because delete flow missing",
                findings=[
                    {
                        "source_stage": "QA",
                        "target_stage": "Product",
                        "issue": "Delete flow missing from PRD",
                        "severity": "high",
                    }
                ],
            )

            result = WorkflowOrchestrator(
                repo_root=repo_root,
                state_store=StateStore(state_root),
                backend=backend,
            ).run(request="Build a task manager")

            review_path = state_root / "sessions" / result.session_id / "review.md"
            review = review_path.read_text()

            self.assertIn("## Workflow Status", review)
            self.assertIn("runtime_mode: deterministic_demo", review)
            self.assertIn("current_state: WaitForHumanDecision", review)
            self.assertIn("current_stage: Acceptance", review)
            self.assertIn("prd_status: drafted", review)
            self.assertIn("dev_status: completed", review)
            self.assertIn("qa_status: blocked", review)
            self.assertIn("acceptance_status: recommended_no_go", review)
            self.assertIn("human_decision: pending", review)
            self.assertIn("qa_round: 0", review)


if __name__ == "__main__":
    unittest.main()
