import argparse
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


def evidence(name: str, *, kind: str = "artifact", summary: str = "Evidence provided.") -> dict[str, object]:
    payload: dict[str, object] = {
        "name": name,
        "kind": kind,
        "summary": summary,
    }
    if kind == "command":
        payload["command"] = "python3 -m unittest"
        payload["exit_code"] = 0
    return payload


class JudgeStageResultCliTests(unittest.TestCase):
    def test_resolve_openai_oa_header_defaults_to_user_agent(self) -> None:
        from agent_team.cli import _resolve_openai_oa_header

        args = argparse.Namespace(
            openai_oa=None,
            openai_user_agent="Agent-Team-Runtime/0.1",
        )

        self.assertEqual(_resolve_openai_oa_header(args), "Agent-Team-Runtime/0.1")

    def test_resolve_openai_oa_header_prefers_explicit_value(self) -> None:
        from agent_team.cli import _resolve_openai_oa_header

        args = argparse.Namespace(
            openai_oa="proxy-specific-oa",
            openai_user_agent="Agent-Team-Runtime/0.1",
        )

        self.assertEqual(_resolve_openai_oa_header(args), "proxy-specific-oa")

    def test_verify_stage_result_dry_run_outputs_gate_status_json(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            run_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "run",
                    "--message",
                    "执行这个需求：测试 dry-run verify",
                    "--executor",
                    "dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run_result.returncode, 0)
            session_id = run_result.stdout.splitlines()[0].split(": ", 1)[1]

            # status --verbose should show the session state
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "status",
                    "--session-id",
                    session_id,
                    "--verbose",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("current_state: WaitForProductDefinitionApproval", result.stdout)
            self.assertIn("next_action: record-human-decision", result.stdout)

    def test_verify_stage_result_with_noop_judge_advances_workflow(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            run_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "run",
                    "--message",
                    "执行这个需求：测试带 judge 的验收流转",
                    "--executor",
                    "dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run_result.returncode, 0)
            session_id = run_result.stdout.splitlines()[0].split(": ", 1)[1]

            # After run, session is at WaitForProductDefinitionApproval. Advance and run again.
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "record-human-decision",
                    "--session-id",
                    session_id,
                    "--decision",
                    "go",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            # Run the next stages (ProjectRuntime + TechnicalDesign)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "run",
                    "--session-id",
                    session_id,
                    "--executor",
                    "dry-run",
                    "--auto",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("current_state: WaitForTechnicalDesignApproval", result.stdout)

    def test_verify_stage_result_requires_submitted_run(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            run_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "run",
                    "--message",
                    "执行这个需求：测试 verify 的状态校验",
                    "--executor",
                    "dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run_result.returncode, 0)
            session_id = run_result.stdout.splitlines()[0].split(": ", 1)[1]

            # verify-stage-result without dry-run should fail because no SUBMITTED run
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "verify-stage-result",
                    "--session-id",
                    session_id,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)

if __name__ == "__main__":
    unittest.main()
