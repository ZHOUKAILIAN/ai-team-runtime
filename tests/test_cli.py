import subprocess
import sys
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


class CliTests(unittest.TestCase):
    def test_cli_help_exits_successfully(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "ai_company", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("run", result.stdout)
        self.assertIn("review", result.stdout)
        self.assertIn("agent-run", result.stdout)
        self.assertIn("start-session", result.stdout)
        self.assertIn("codex-init", result.stdout)

    def test_agent_run_accepts_raw_user_message(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ai_company",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "agent-run",
                    "--message",
                    "执行这个需求：做一个支持验收回写学习记录的任务系统",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0)
        self.assertIn("session_id:", result.stdout)
        self.assertIn("acceptance_status:", result.stdout)

    def test_run_and_agent_run_help_describe_demo_deterministic_commands(self) -> None:
        run_help = subprocess.run(
            [sys.executable, "-m", "ai_company", "run", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        agent_run_help = subprocess.run(
            [sys.executable, "-m", "ai_company", "agent-run", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(run_help.returncode, 0)
        self.assertEqual(agent_run_help.returncode, 0)
        self.assertIn("Demo command: execute the deterministic workflow session", run_help.stdout)
        self.assertIn("Demo command: execute the deterministic workflow session", agent_run_help.stdout)

    def test_start_session_bootstraps_session_from_raw_message(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        raw_message = "执行这个需求：做一个支持验收回写学习记录的任务系统"

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ai_company",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "start-session",
                    "--message",
                    raw_message,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("session_id:", result.stdout)
            self.assertIn("artifact_dir:", result.stdout)
            self.assertIn("summary_path:", result.stdout)

            output_lines = [line for line in result.stdout.splitlines() if ":" in line]
            output_map = dict(line.split(": ", 1) for line in output_lines)

            session_id = output_map["session_id"]
            artifact_dir = Path(output_map["artifact_dir"])
            summary_path = Path(output_map["summary_path"])
            request_path = artifact_dir / "request.md"
            session_json_path = Path(temp_dir) / "sessions" / session_id / "session.json"

            self.assertTrue(artifact_dir.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(request_path.exists())
            self.assertTrue(session_json_path.exists())
            self.assertIn("做一个支持验收回写学习记录的任务系统", request_path.read_text())
            self.assertIn(raw_message, request_path.read_text())
            session_payload = json.loads(session_json_path.read_text())
            self.assertEqual(session_payload["raw_message"], raw_message)

    def test_start_session_help_describes_session_scaffold_command(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "ai_company", "start-session", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn(
            "Create a session scaffold for the single-session AI_Team workflow.",
            result.stdout,
        )

    def test_codex_init_reports_project_scoped_codex_setup(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ai_company",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "codex-init",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0)
        self.assertIn("state_root:", result.stdout)
        self.assertIn(".codex/config.toml", result.stdout)
        self.assertIn(".codex/agents", result.stdout)
        self.assertIn(".agents/skills/ai-team-run/SKILL.md", result.stdout)
        self.assertIn("project_root:", result.stdout)
        self.assertIn("recommended_context:", result.stdout)
        self.assertIn("$ai-team-init", result.stdout)
        self.assertIn("$ai-team-run", result.stdout)
        self.assertIn("manual_run_fallback:", result.stdout)


if __name__ == "__main__":
    unittest.main()
