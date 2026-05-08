import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


class MemoryLayerTests(unittest.TestCase):
    def test_apply_learning_writes_raw_extracted_and_graph_layers(self) -> None:
        from agent_team.models import Finding
        from agent_team.state import StateStore

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            root = Path(temp_dir)
            StateStore(root).apply_learning(
                Finding(
                    source_stage="SessionHandoff",
                    target_stage="Implementation",
                    issue="Acceptance found missing empty-state evidence.",
                    severity="high",
                    lesson="Preserve empty-state validation in regression coverage.",
                    proposed_context_update="Review empty-state behavior before handoff.",
                    proposed_contract_update="Require visible empty-state evidence before reporting success.",
                    evidence="session-handoff.md",
                    evidence_kind="artifact",
                    required_evidence=["empty_state_screenshot"],
                    completion_signal="Attach empty-state screenshot evidence.",
                )
            )

            raw_records = [
                json.loads(line)
                for line in (root / "memory" / "Implementation" / "raw" / "findings.jsonl").read_text().splitlines()
            ]
            graph_records = [
                json.loads(line)
                for line in (root / "memory" / "Implementation" / "graph" / "relations.jsonl").read_text().splitlines()
            ]
            extracted_lesson = (root / "memory" / "Implementation" / "extracted" / "lessons.md").read_text()

        self.assertEqual(raw_records[0]["record_type"], "finding")
        self.assertEqual(raw_records[0]["finding"]["issue"], "Acceptance found missing empty-state evidence.")
        self.assertIn("Preserve empty-state validation", extracted_lesson)
        self.assertIn("SessionHandoff->Implementation", {record["edge"] for record in graph_records})
        self.assertIn("issue->required_evidence", {record["edge"] for record in graph_records})

    def test_keyword_retrieval_searches_memory_layers_before_graph_reasoning(self) -> None:
        from agent_team.memory_layers import retrieve_role_memory
        from agent_team.models import Finding
        from agent_team.state import StateStore

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            root = Path(temp_dir)
            StateStore(root).apply_learning(
                Finding(
                    source_stage="Verification",
                    target_stage="Implementation",
                    issue="Missing pagination retry evidence.",
                    lesson="Keep pagination retry checks in Implementation self-verification.",
                    proposed_context_update="Search previous pagination findings before implementation.",
                )
            )

            result = retrieve_role_memory(
                state_root=root,
                role_name="Implementation",
                query="pagination retry",
                max_results=5,
            )

        self.assertEqual(result.strategy, "keyword_cli")
        self.assertGreaterEqual(len(result.matches), 1)
        self.assertIn("pagination retry", "\n".join(match.preview.lower() for match in result.matches))

    def test_stage_contract_includes_retrieved_memory_section(self) -> None:
        from agent_team.models import Finding
        from agent_team.stage_contracts import build_stage_contract
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            root = Path(temp_dir)
            store = StateStore(root)
            session = store.create_session("Build pagination retry support.", runtime_mode="runtime_driver")
            store.apply_learning(
                Finding(
                    source_stage="Verification",
                    target_stage="Implementation",
                    issue="Missing pagination retry evidence.",
                    lesson="Keep pagination retry checks in Implementation self-verification.",
                )
            )

            contract = build_stage_contract(
                repo_root=repo_root,
                state_store=store,
                session_id=session.session_id,
                stage="Implementation",
            )

        self.assertIn("Relevant Memory (CLI Keyword Retrieval)", contract.role_context)
        self.assertIn("pagination retry", contract.role_context.lower())


if __name__ == "__main__":
    unittest.main()
