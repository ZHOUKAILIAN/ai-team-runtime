import io
import os
import subprocess
import sys
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


class TtyStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


def evidence(name: str, *, kind: str = "report", summary: str = "Evidence provided.") -> dict[str, object]:
    payload: dict[str, object] = {
        "name": name,
        "kind": kind,
        "summary": summary,
    }
    if kind == "command":
        payload["command"] = "python -m unittest"
        payload["exit_code"] = 0
    return payload


class CliTests(unittest.TestCase):
    def test_cli_without_command_exits_with_argparse_error_instead_of_traceback(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "agent_team"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("the following arguments are required: command", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_help_exits_successfully(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "agent_team", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("review", result.stdout)
        self.assertIn("init", result.stdout)
        self.assertNotIn("init-state", result.stdout)
        self.assertNotIn("init-project-structure", result.stdout)
        self.assertIn("run", result.stdout)
        self.assertNotIn("run-requirement", result.stdout)
        self.assertNotIn("agent-run", result.stdout)
        self.assertNotIn("Demo command: execute the deterministic workflow session", result.stdout)
        self.assertNotIn("codex-init", result.stdout)
        self.assertIn("panel", result.stdout)
        self.assertIn("status", result.stdout)
        self.assertNotIn("agent-team dev", result.stdout)

    def test_legacy_run_requirement_alias_still_opens_run_help(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "agent_team", "run-requirement", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("usage: agent-team run", result.stdout)
        self.assertIn("--message", result.stdout)

    def test_init_bootstraps_state_and_project_structure(self) -> None:
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "init",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("state_root:", result.stdout)
            self.assertIn("project_root:", result.stdout)
            self.assertTrue((repo_root / ".agent-team" / "memory").is_dir())
            self.assertTrue((repo_root / "agent-team" / "project" / "doc-map.json").is_file())

    def test_run_help_lists_skill_overrides(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "agent_team", "run", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("--with-skills", result.stdout)
        self.assertIn("--skip-skills", result.stdout)
        self.assertIn("--skills-empty", result.stdout)

    def test_skill_commands_list_builtin_skills(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_team",
                "--repo-root",
                str(repo_root),
                "skill",
                "list",
                "--stage",
                "Dev",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("plan", result.stdout)
        self.assertIn("built-in", result.stdout)

    def test_skill_show_includes_source_reference(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_team",
                "--repo-root",
                str(repo_root),
                "skill",
                "show",
                "plan",
                "--stage",
                "Dev",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("source_ref:", result.stdout)
        self.assertIn("path:", result.stdout)

    def test_skill_preferences_reset_creates_empty_preference_file(self) -> None:
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "skill",
                    "preferences",
                    "--reset",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("dev:", result.stdout)
            self.assertTrue((repo_root / ".agent-team" / "skill-preferences.yaml").exists())

    def test_run_is_registered_and_demo_agent_run_is_not_registered(self) -> None:
        run_help = subprocess.run(
            [sys.executable, "-m", "agent_team", "run", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        agent_run_help = subprocess.run(
            [sys.executable, "-m", "agent_team", "agent-run", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(run_help.returncode, 0)
        self.assertEqual(agent_run_help.returncode, 2)
        self.assertIn("usage: agent-team run", run_help.stdout)
        self.assertIn("invalid choice: 'agent-run'", agent_run_help.stderr)



    def test_run_requirement_dry_run_stops_at_product_approval_gate(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
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
                    "--message",
                    "执行这个需求：做一个 runtime 强制驱动流程",
                    "--executor",
                    "dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("runtime_driver_status: waiting_human", result.stdout)
            self.assertIn("current_state: WaitForCEOApproval", result.stdout)
            self.assertIn("next_action: record-human-decision --decision go", result.stdout)
            output_lines = [line for line in result.stdout.splitlines() if ": " in line]
            output_map = dict(line.split(": ", 1) for line in output_lines)
            session_id = output_map["session_id"]
            session_dir = Path(temp_dir) / session_id
            runtime_session_dir = Path(temp_dir) / "_runtime" / "sessions" / session_id
            self.assertTrue((session_dir / "product-requirements.md").exists())
            self.assertFalse((session_dir / "implementation.md").exists())
            self.assertTrue(
                (
                    runtime_session_dir
                    / "roles"
                    / "product"
                    / "attempt-001"
                    / "stage-results"
                    / "product-stage-result.json"
                ).exists()
            )

    def test_run_requirement_without_message_or_session_id_in_non_tty_fails_cleanly(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_team",
                "--repo-root",
                str(repo_root),
                "run",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "run requires --message or --session-id when stdin/stdout are not interactive.",
            result.stderr + result.stdout,
        )
        self.assertNotIn("Traceback", result.stderr + result.stdout)

    def test_run_requirement_flow_progress_bar_animates_without_hash_dash_bar(self) -> None:
        from agent_team.cli import _render_flow_progress_bar, _render_running_progress_line

        first_frame = _render_flow_progress_bar(1, 5, phase=0)
        second_frame = _render_flow_progress_bar(1, 5, phase=1)
        first_line = _render_running_progress_line(stage="Product", completed=1, phase=0)
        second_line = _render_running_progress_line(stage="Product", completed=1, phase=1)

        self.assertNotEqual(first_frame, second_frame)
        self.assertNotEqual(first_line, second_line)
        self.assertNotIn("#", first_frame)
        self.assertNotIn("-", first_frame)
        self.assertIn(">", first_frame)
        self.assertTrue(first_frame.endswith("1/5"))
        self.assertTrue(first_line.startswith("◐ ["))
        self.assertTrue(second_line.startswith("◓ ["))
        self.assertIn("Product · 读取需求", first_line)
        self.assertIn("Product · 提炼目标边界", second_line)
        self.assertIn(
            "Dev · 技术方案 · 读取 PRD",
            _render_running_progress_line(stage="DevTechnicalPlan", completed=1, phase=0),
        )
        self.assertIn(
            "Dev · 技术方案 · 生成阶段契约",
            _render_running_progress_line(stage="DevTechnicalPlan", completed=1, phase=0, activity="生成阶段契约"),
        )

    def test_run_requirement_animation_wraps_interactive_stage_line(self) -> None:
        import time

        from agent_team.cli import _run_requirement_with_stage_animation

        stdout = TtyStringIO()
        with patch("sys.stdout", stdout):
            result = _run_requirement_with_stage_animation(
                stage="Product",
                completed=0,
                run=lambda: (time.sleep(0.18), "done")[1],
            )

        output = stdout.getvalue()
        self.assertEqual(result, "done")
        self.assertIn("\r◐ [", output)
        self.assertIn("[>", output)
        self.assertIn("Product", output)
        self.assertIn("\033[2K", output)

    def test_run_requirement_stage_banner_keeps_static_progress_for_non_tty(self) -> None:
        from agent_team.cli import _print_run_requirement_stage_banner

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            _print_run_requirement_stage_banner(stage="Product", completed=0)

        output = stdout.getvalue()
        self.assertIn("[1/5 Product] 生成需求方案中", output)
        self.assertIn("进度: [", output)
        self.assertIn("-", output)
        self.assertNotIn("\033[2K", output)

    def test_run_requirement_interactive_tty_walks_through_all_gates(self) -> None:
        from agent_team.cli import main

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            stdin = TtyStringIO("写个js文件，并打印hello world\ny\ny\ny\ny\ny\n")
            stdout = TtyStringIO()
            with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "--state-root",
                        temp_dir,
                        "run",
                        "--executor",
                        "dry-run",
                    ]
                )

            self.assertEqual(exit_code, 0)
            output = stdout.getvalue()
            self.assertIn("[1/5 Product] 生成需求方案中", output)
            self.assertIn("文档:", output)
            self.assertIn("Product Requirements:", output)
            self.assertIn("Technical Plan:", output)
            self.assertIn("Session completed.", output)
            session_line = next(line for line in output.splitlines() if line.startswith("session_id: "))
            session_id = session_line.split(": ", 1)[1]
            session_dir = Path(temp_dir) / session_id
            self.assertTrue((session_dir / "product-requirements.md").exists())
            self.assertTrue((session_dir / "technical_plan.md").exists())

    def test_run_requirement_interactive_auto_skips_intermediate_prompts_only(self) -> None:
        from agent_team.cli import main

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            stdin = TtyStringIO("写个js文件，并打印hello world\ny\nq\n")
            stdout = TtyStringIO()
            with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "--state-root",
                        temp_dir,
                        "run",
                        "--executor",
                        "dry-run",
                        "--auto",
                    ]
                )

            self.assertEqual(exit_code, 0)
            output = stdout.getvalue()
            self.assertIn("[1/5 Product] 生成需求方案中", output)
            self.assertIn("[2/5 Dev · 技术方案] 生成 Dev 技术方案中", output)
            self.assertIn("请选择下一步：", output)
            self.assertIn("Session saved.", output)
            self.assertNotIn("--auto: 已自动通过 Dev · 技术方案，进入 Dev。", output)
            self.assertNotIn("请打开实现文档确认代码改动和自检结果是否通过。", output)
            self.assertNotIn("请打开 QA 报告确认验证结果是否通过。", output)
            session_line = next(line for line in output.splitlines() if line.startswith("session_id: "))
            session_id = session_line.split(": ", 1)[1]
            session_dir = Path(temp_dir) / session_id
            self.assertTrue((session_dir / "technical_plan.md").exists())
            self.assertFalse((session_dir / "implementation.md").exists())
            self.assertFalse((session_dir / "qa_report.md").exists())
            self.assertFalse((session_dir / "acceptance_report.md").exists())

    def test_run_requirement_acceptance_prompt_does_not_reprint_menu_after_invalid_input(self) -> None:
        from agent_team.cli import main

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            stdin = TtyStringIO("写个js文件，并打印hello world\ny\ny\ny\ny\n\nbad\nq\n")
            stdout = TtyStringIO()
            with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "--state-root",
                        temp_dir,
                        "run",
                        "--executor",
                        "dry-run",
                    ]
                )

            self.assertEqual(exit_code, 0)
            output = stdout.getvalue()
            self.assertEqual(output.count("  y) 通过验收，完成交付"), 1)
            self.assertEqual(output.count("  n) 不通过验收，结束为 no-go"), 1)
            self.assertEqual(output.count("请输入 y / n / e / p / q。"), 2)
            self.assertIn("Session saved.", output)

    def test_run_requirement_interactive_tty_waits_on_blocked_stage_instead_of_exiting(self) -> None:
        from agent_team.cli import main

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            worker_path = Path(temp_dir) / "blocked_worker.py"
            worker_path.write_text(
                "import sys\n"
                "print('blocked stdout')\n"
                "print('blocked stderr', file=sys.stderr)\n"
                "sys.exit(1)\n"
            )
            stdin = TtyStringIO("p\nq\n")
            stdout = TtyStringIO()
            with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "--state-root",
                        temp_dir,
                        "run",
                        "--message",
                        "写个js文件，并打印hello world",
                        "--executor",
                        "command",
                        "--executor-command",
                        f"{sys.executable} {worker_path}",
                    ]
                )

            self.assertEqual(exit_code, 0)
            output = stdout.getvalue()
            self.assertIn("当前阶段执行被阻塞", output)
            self.assertIn("诊断信息:", output)
            self.assertIn("Session saved.", output)

    def test_run_requirement_dry_run_stops_at_tech_plan_human_gate_without_auto(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            product_result = subprocess.run(
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
                    "执行这个需求：做一个 runtime 强制驱动流程",
                    "--executor",
                    "dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(product_result.returncode, 0)
            output_lines = [line for line in product_result.stdout.splitlines() if ": " in line]
            session_id = dict(line.split(": ", 1) for line in output_lines)["session_id"]

            approve = subprocess.run(
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
                check=False,
            )
            self.assertEqual(approve.returncode, 0)
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
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("runtime_driver_status: waiting_human", result.stdout)
            self.assertIn("current_state: WaitForTechnicalPlanApproval", result.stdout)
            self.assertIn("current_stage: Dev", result.stdout)
            session_dir = Path(temp_dir) / session_id
            self.assertTrue((session_dir / "product-requirements.md").exists())
            self.assertTrue((session_dir / "acceptance_plan.md").exists())
            self.assertTrue((session_dir / "technical_plan.md").exists())
            self.assertFalse((session_dir / "implementation.md").exists())
            self.assertFalse((session_dir / "qa_report.md").exists())
            self.assertFalse((session_dir / "acceptance_report.md").exists())
            self.assertFalse(
                (
                    Path(temp_dir)
                    / "_runtime"
                    / "sessions"
                    / session_id
                    / "roles"
                    / "acceptance"
                    / "attempt-001"
                    / "stage-results"
                    / "acceptance-stage-result.json"
                ).exists()
            )

    def test_run_requirement_dry_run_auto_stops_at_final_human_decision(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            product_result = subprocess.run(
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
                    "执行这个需求：做一个 runtime 强制驱动流程",
                    "--executor",
                    "dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(product_result.returncode, 0)
            output_lines = [line for line in product_result.stdout.splitlines() if ": " in line]
            session_id = dict(line.split(": ", 1) for line in output_lines)["session_id"]

            approve = subprocess.run(
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
                check=False,
            )
            self.assertEqual(approve.returncode, 0)
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
            self.assertIn("runtime_driver_status: waiting_human", result.stdout)
            self.assertIn("current_state: WaitForTechnicalPlanApproval", result.stdout)
            self.assertIn("current_stage: Dev", result.stdout)

            approve_tech_plan = subprocess.run(
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
                check=False,
            )
            self.assertEqual(approve_tech_plan.returncode, 0)
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
            self.assertIn("runtime_driver_status: waiting_human", result.stdout)
            self.assertIn("current_state: WaitForHumanDecision", result.stdout)
            self.assertIn("current_stage: Acceptance", result.stdout)
            self.assertIn("human_decision: pending", result.stdout)

    def test_run_requirement_command_executor_receives_stage_environment(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            worker_path = Path(temp_dir) / "stage_worker.py"
            worker_path.write_text(
                "import json, os, sys\n"
                "print('worker stdout')\n"
                "print('worker stderr', file=sys.stderr)\n"
                "payload = {\n"
                "  'status': 'completed',\n"
                "  'artifact_content': '# PRD\\n\\n## Acceptance Plan\\n- [Acceptance Plan](acceptance_plan.md)\\n',\n"
                "  'acceptance_plan_content': '# Acceptance Plan\\n\\n## Requirements\\n- [PRD](product-requirements.md)\\n\\n## Verification\\n- Run the command executor path.\\n',\n"
                "  'journal': 'command executor wrote the product bundle',\n"
                "  'evidence': [\n"
                "    {'name': 'explicit_acceptance_plan', 'kind': 'artifact', 'summary': 'acceptance plan present'}\n"
                "  ],\n"
                "  'summary': 'command executor completed Product'\n"
                "}\n"
                "open(os.environ['AGENT_TEAM_RESULT_BUNDLE'], 'w').write(json.dumps(payload))\n"
            )
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
                    "--message",
                    "执行这个需求：验证 command executor",
                    "--executor",
                    "command",
                    "--executor-command",
                    f"{sys.executable} {worker_path}",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("runtime_driver_status: waiting_human", result.stdout)
            output_lines = [line for line in result.stdout.splitlines() if ": " in line]
            session_id = dict(line.split(": ", 1) for line in output_lines)["session_id"]
            session_dir = Path(temp_dir) / session_id
            runtime_session_dir = Path(temp_dir) / "_runtime" / "sessions" / session_id
            self.assertIn("acceptance_plan.md", (session_dir / "product-requirements.md").read_text())
            self.assertIn("Run the command executor path.", (session_dir / "acceptance_plan.md").read_text())
            self.assertIn(
                "worker stdout",
                (
                    runtime_session_dir
                    / "roles"
                    / "product"
                    / "attempt-001"
                    / "command-outputs"
                    / "product-command-stdout.txt"
                ).read_text(),
            )
            self.assertIn(
                "worker stderr",
                (
                    runtime_session_dir
                    / "roles"
                    / "product"
                    / "attempt-001"
                    / "command-outputs"
                    / "product-command-stderr.txt"
                ).read_text(),
            )




    def test_panel_json_prints_snapshot(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        raw_message = "执行这个需求：做一个带面板的 workflow"

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            bootstrap = subprocess.run(
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
                    raw_message,
                    "--executor",
                    "dry-run",
                    "--max-stage-runs",
                    "1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bootstrap.returncode, 0)
            session_id = bootstrap.stdout.splitlines()[0].split(": ", 1)[1]

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "panel",
                    "--session-id",
                    session_id,
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["session"]["session_id"], session_id)

    def test_status_prints_user_friendly_project_role_and_status(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        raw_message = "执行这个需求：做一个可查询状态的 workflow"

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir) / ".agent-team"
            bootstrap = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    str(state_root),
                    "run",
                    "--message",
                    raw_message,
                    "--executor",
                    "dry-run",
                    "--max-stage-runs",
                    "1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bootstrap.returncode, 0)
            session_id = bootstrap.stdout.splitlines()[0].split(": ", 1)[1]

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    str(state_root),
                    "status",
                    "--session-id",
                    session_id,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn(f"project: {repo_root.name}", result.stdout)
            self.assertIn("status:", result.stdout)
            self.assertIn("session_id:", result.stdout)




    def test_acquire_submit_verify_product_moves_to_ceo_wait(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
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
                    "--message",
                    "执行这个需求：做一个带阶段门禁的流程",
                    "--executor",
                    "dry-run",
                    "--max-stage-runs",
                    "1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("current_state: WaitForCEOApproval", result.stdout)
            session_id = result.stdout.splitlines()[0].split(": ", 1)[1]

            self.assertTrue(session_id.startswith("20"))




    def test_record_human_decision_routes_product_approval_to_tech_plan(self) -> None:
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
                    "执行这个需求：做一个 harness-first workflow",
                    "--executor",
                    "dry-run",
                    "--max-stage-runs",
                    "1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run_result.returncode, 0)
            session_id = run_result.stdout.splitlines()[0].split(": ", 1)[1]

            result = subprocess.run(
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
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("current_state: Dev", result.stdout)
            self.assertIn("current_stage: Dev", result.stdout)

    def test_record_feedback_persists_learning_and_feedback_metadata(self) -> None:
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
                    "执行这个需求：测试反馈回流",
                    "--executor",
                    "dry-run",
                    "--max-stage-runs",
                    "1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run_result.returncode, 0)
            session_id = run_result.stdout.splitlines()[0].split(": ", 1)[1]

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "record-feedback",
                    "--session-id",
                    session_id,
                    "--source-stage",
                    "Acceptance",
                    "--target-stage",
                    "Dev",
                    "--issue",
                    "Missing edge case handling",
                    "--severity",
                    "high",
                    "--lesson",
                    "Always check edge cases",
                    "--evidence",
                    "test_output.log",
                    "--evidence-kind",
                    "log",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("recorded_feedback:", result.stdout)
            self.assertIn(session_id, result.stdout)

    def test_record_feedback_can_apply_rework_decision_in_same_command(self) -> None:
        from agent_team.models import WorkflowSummary
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            store = StateStore(Path(temp_dir))
            session = store.create_session("做一个支持验收回流的流程")
            store.save_workflow_summary(
                session,
                WorkflowSummary(
                    session_id=session.session_id,
                    runtime_mode="session_bootstrap",
                    current_state="WaitForHumanDecision",
                    current_stage="Acceptance",
                    prd_status="drafted",
                    dev_status="completed",
                    qa_status="passed",
                    acceptance_status="recommended_go",
                    human_decision="pending",
                    artifact_paths={
                        "workflow_summary": str(store.workflow_summary_path(session.session_id)),
                    },
                ),
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "record-feedback",
                    "--session-id",
                    session.session_id,
                    "--source-stage",
                    "Acceptance",
                    "--target-stage",
                    "Dev",
                    "--issue",
                    "Acceptance found a missed Figma parity issue.",
                    "--severity",
                    "high",
                    "--apply-rework",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("recorded_feedback:", result.stdout)
            self.assertIn("current_state: Dev", result.stdout)
            self.assertIn("current_stage: Dev", result.stdout)
            self.assertIn("human_decision: rework", result.stdout)

if __name__ == "__main__":
    unittest.main()
