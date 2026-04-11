import subprocess
import sys
import tomllib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


class ConsoleScriptTests(unittest.TestCase):
    def test_project_declares_user_facing_cli_entrypoints(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        payload = tomllib.loads((repo_root / "pyproject.toml").read_text())

        scripts = payload["project"]["scripts"]

        self.assertEqual(scripts["ai-team"], "ai_company.cli:main")
        self.assertNotIn("ai-team-harness", scripts)

    def test_installed_cli_entrypoints_run_help_without_python_module_command(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            venv_dir = Path(temp_dir) / "venv"
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [str(venv_dir / "bin" / "python"), "-m", "pip", "install", "-e", str(repo_root)],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            )

            ai_team_help = subprocess.run(
                [str(venv_dir / "bin" / "ai-team"), "--help"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(ai_team_help.returncode, 0, ai_team_help.stderr)
        self.assertIn("start-session", ai_team_help.stdout)
        self.assertIn("current-stage", ai_team_help.stdout)


if __name__ == "__main__":
    unittest.main()
