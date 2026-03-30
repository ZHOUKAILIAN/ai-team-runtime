import subprocess
import sys
import unittest
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

    def test_start_session_bootstraps_session_from_raw_message(self) -> None:
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
                    "start-session",
                    "--message",
                    "执行这个需求：做一个支持验收回写学习记录的任务系统",
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

            artifact_dir = Path(output_map["artifact_dir"])
            summary_path = Path(output_map["summary_path"])
            request_path = artifact_dir / "request.md"

            self.assertTrue(artifact_dir.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(request_path.exists())
            self.assertIn("做一个支持验收回写学习记录的任务系统", request_path.read_text())
            self.assertNotIn("执行这个需求", request_path.read_text())


if __name__ == "__main__":
    unittest.main()
