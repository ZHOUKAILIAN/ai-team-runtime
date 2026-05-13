import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


class PanelTests(unittest.TestCase):
    def test_list_panel_sessions_moves_done_sessions_into_archive(self) -> None:
        from agent_team.panel import list_panel_sessions
        from agent_team.state import StateStore

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            project_root = Path(temp_dir) / "crewpals-mp"
            root = project_root / ".agent-team"
            store = StateStore(root)
            active_session = store.create_session("active task")
            archived_session = store.create_session("approved task")

            archived_summary = store.load_workflow_summary(archived_session.session_id)
            archived_summary.current_state = "Done"
            archived_summary.current_stage = "Acceptance"
            archived_summary.acceptance_status = "recommended_go"
            archived_summary.human_decision = "go"
            store.save_workflow_summary(archived_session, archived_summary)

            sessions = list_panel_sessions(store)

            self.assertEqual([item["session_id"] for item in sessions["active"]], [active_session.session_id])
            self.assertEqual([item["session_id"] for item in sessions["archived"]], [archived_session.session_id])
            self.assertTrue(sessions["archived"][0]["archived"])

    def test_panel_snapshot_combines_summary_contract_events_and_artifacts(self) -> None:
        from agent_team.models import AcceptanceContract
        from agent_team.panel import build_panel_snapshot
        from agent_team.state import StateStore

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            project_root = Path(temp_dir) / "crewpals-mp"
            root = project_root / ".agent-team"
            store = StateStore(root)
            session = store.create_session(
                "restore a Figma screen 1:1",
                contract=AcceptanceContract(
                    review_method="figma-restoration-review",
                    boundary="page_root",
                    recursive=True,
                    required_artifacts=["deviation_checklist.md", "review_completion.json"],
                    required_evidence=["runtime_screenshot", "overlay_diff"],
                    acceptance_criteria=["Figma visual parity is proven by review artifacts."],
                ),
            )
            summary = store.load_workflow_summary(session.session_id)
            summary.current_state = "Acceptance"
            summary.current_stage = "Acceptance"
            summary.acceptance_status = "blocked"
            summary.blocked_reason = "Review completion gate is incomplete."
            store.save_workflow_summary(session, summary)

            snapshot = build_panel_snapshot(store, session.session_id)

            self.assertEqual(snapshot["overview"]["project"], "crewpals-mp")
            self.assertEqual(snapshot["overview"]["role"], "Acceptance")
            self.assertEqual(snapshot["overview"]["status"], "blocked")
            self.assertIn("crewpals-mp", snapshot["overview"]["text"])
            self.assertIn("Acceptance", snapshot["overview"]["text"])
            self.assertIn("blocked", snapshot["overview"]["text"])
            self.assertEqual(snapshot["session"]["session_id"], session.session_id)
            self.assertEqual(snapshot["state"]["current_state"], "Acceptance")
            self.assertEqual(snapshot["operator"]["blocked_reason"], "Review completion gate is incomplete.")
            self.assertIn("Acceptance", snapshot["operator"]["current_action"])
            self.assertEqual(snapshot["evidence"]["required"], ["runtime_screenshot", "overlay_diff"])
            self.assertEqual(snapshot["evidence"]["pending"], ["runtime_screenshot", "overlay_diff"])
            self.assertTrue(any(item["name"] == "workflow_summary" for item in snapshot["artifacts"]))
            self.assertEqual(snapshot["events"][0]["kind"], "session_created")

    def test_panel_snapshot_includes_stage_timing_summary(self) -> None:
        from agent_team.panel import build_panel_snapshot
        from agent_team.state import StateStore

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            root = Path(temp_dir)
            store = StateStore(root)
            session = store.create_session("measure stage time")
            run = store.create_stage_run(
                session_id=session.session_id,
                stage="ProductDefinition",
                contract_id="contract-product-definition",
                required_outputs=["product-definition-delta.md"],
                required_evidence=["l1_classification"],
                worker="dry-run",
            )
            store.update_stage_run_trace(
                session_id=session.session_id,
                run_id=run.run_id,
                required_pass_steps=[],
                steps=[
                    {"step": "contract_built", "status": "ok", "at": "2026-05-12T00:00:00+00:00"},
                    {"step": "executor_started", "status": "ok", "at": "2026-05-12T00:00:02+00:00"},
                    {"step": "executor_completed", "status": "ok", "at": "2026-05-12T00:00:07+00:00"},
                    {"step": "result_submitted", "status": "ok", "at": "2026-05-12T00:00:08+00:00"},
                    {"step": "gate_evaluated", "status": "ok", "at": "2026-05-12T00:00:10+00:00"},
                ],
            )

            snapshot = build_panel_snapshot(store, session.session_id)

        timing = snapshot["stage_timings"][0]
        self.assertEqual(timing["stage"], "ProductDefinition")
        self.assertEqual(timing["total_seconds"], 10.0)
        self.assertEqual(timing["executor_seconds"], 5.0)
        self.assertEqual(timing["gate_seconds"], 2.0)

    def test_state_store_does_not_write_redundant_status_markdown(self) -> None:
        from agent_team.state import StateStore

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            project_root = Path(temp_dir) / "crewpals-mp"
            root = project_root / ".agent-team"
            store = StateStore(root)
            session = store.create_session("demo task")

            status_path = root / session.session_id / "status.md"

            self.assertFalse(status_path.exists())

    def test_state_store_writes_session_events_jsonl(self) -> None:
        from agent_team.state import StateStore

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            root = Path(temp_dir)
            store = StateStore(root)
            session = store.create_session("demo task")

            events_path = root / "_runtime" / "sessions" / session.session_id / "events.jsonl"
            self.assertTrue(events_path.exists())
            events = [json.loads(line) for line in events_path.read_text().splitlines()]

            self.assertEqual(events[0]["kind"], "session_created")
            self.assertEqual(events[0]["session_id"], session.session_id)
            self.assertEqual(events[0]["stage"], "Intake")
            self.assertIn("demo task", events[0]["message"])


if __name__ == "__main__":
    unittest.main()
