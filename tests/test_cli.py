import io
import json
import subprocess
import sys
import unittest
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


def _session_id_from_stdout(stdout: str) -> str:
    return dict(line.split(": ", 1) for line in stdout.splitlines() if ": " in line)["session_id"]


class CliTests(unittest.TestCase):
    def test_cli_without_command_exits_with_argparse_error_instead_of_traceback(self) -> None:
        result = subprocess.run([sys.executable, "-m", "agent_team"], capture_output=True, text=True, check=False)

        self.assertEqual(result.returncode, 2)
        self.assertIn("the following arguments are required: command", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_help_exits_successfully(self) -> None:
        result = subprocess.run([sys.executable, "-m", "agent_team", "--help"], capture_output=True, text=True, check=False)

        self.assertEqual(result.returncode, 0)
        self.assertIn("init", result.stdout)
        self.assertIn("update", result.stdout)
        self.assertIn("run", result.stdout)
        self.assertIn("panel", result.stdout)
        self.assertIn("status", result.stdout)
        self.assertNotIn("agent-run", result.stdout)

    def test_project_scripts_include_short_agt_alias(self) -> None:
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"

        payload = pyproject.read_text()

        self.assertIn('agent-team = "agent_team.cli:main"', payload)
        self.assertIn('agt = "agent_team.cli:main"', payload)

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

    def test_init_bootstraps_state_project_structure_and_five_layer_skip_record(self) -> None:
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
            self.assertIn("five_layer_classification_status: skipped", result.stdout)
            self.assertTrue((repo_root / ".agent-team" / "memory").is_dir())
            self.assertTrue((repo_root / "agent-team" / "project" / "doc-map.json").is_file())
            self.assertTrue((repo_root / "agent-team" / "project" / "five-layer" / "classification-prompt.md").is_file())
            self.assertTrue((repo_root / "agent-team" / "project" / "five-layer" / "classification-run.json").is_file())

    def test_update_reports_and_preserves_existing_project_files(self) -> None:
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            project_dir = repo_root / "agent-team" / "project"
            roles_dir = project_dir / "roles"
            roles_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "context.md").write_text("# Custom Context\n")
            (project_dir / "rules.md").write_text("# Custom Rules\n")
            (project_dir / "doc-map.json").write_text(json.dumps({"product_definition": "docs/requirements"}))
            (roles_dir / "dev.context.md").write_text("# Legacy Dev\n")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "update",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Agent Team 项目配置更新", result.stdout)
            self.assertIn("dry_run: false", result.stdout)
            self.assertIn("已创建", result.stdout)
            self.assertIn("已保留", result.stdout)
            self.assertEqual((project_dir / "context.md").read_text(), "# Custom Context\n")
            self.assertEqual((project_dir / "rules.md").read_text(), "# Custom Rules\n")
            self.assertTrue((roles_dir / "dev.context.md").exists())
            doc_map = json.loads((project_dir / "doc-map.json").read_text())
            self.assertEqual(doc_map["product_definition"], "docs/requirements")
            self.assertEqual(doc_map["project_runtime"], "docs/project-runtime")

    def test_update_dry_run_does_not_write_files(self) -> None:
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            project_dir = repo_root / "agent-team" / "project"
            project_dir.mkdir(parents=True)
            (project_dir / "doc-map.json").write_text(json.dumps({"requirements": "docs/requirements"}))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "update",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("dry_run: true", result.stdout)
            self.assertIn("预览更新", result.stdout)
            self.assertEqual((project_dir / "doc-map.json").read_text(), json.dumps({"requirements": "docs/requirements"}))
            self.assertFalse((project_dir / "context.md").exists())
            self.assertFalse((repo_root / ".agent-team").exists())

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
                "Implementation",
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
                "Implementation",
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
            self.assertIn("implementation:", result.stdout)
            self.assertIn("productdefinition:", result.stdout)
            self.assertTrue((repo_root / ".agent-team" / "skill-preferences.yaml").exists())

    def test_run_requirement_dry_run_stops_at_product_definition_approval_gate(self) -> None:
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
            self.assertIn("current_state: WaitForProductDefinitionApproval", result.stdout)
            self.assertIn("current_stage: ProductDefinition", result.stdout)
            self.assertIn("next_action: approve", result.stdout)
            session_id = _session_id_from_stdout(result.stdout)
            session_dir = Path(temp_dir) / session_id
            runtime_session_dir = Path(temp_dir) / "_runtime" / "sessions" / session_id
            self.assertTrue((session_dir / "route-packet.json").exists())
            self.assertTrue((session_dir / "product-definition-delta.md").exists())
            self.assertFalse((session_dir / "technical-design.md").exists())
            self.assertTrue(
                (
                    runtime_session_dir
                    / "roles"
                    / "product-definition"
                    / "attempt-001"
                    / "stage-results"
                    / "product-definition-stage-result.json"
                ).exists()
            )

    def test_run_requirement_without_message_or_session_id_in_non_tty_fails_cleanly(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        result = subprocess.run(
            [sys.executable, "-m", "agent_team", "--repo-root", str(repo_root), "run"],
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

        first_frame = _render_flow_progress_bar(1, 9, phase=0)
        second_frame = _render_flow_progress_bar(1, 9, phase=1)
        first_line = _render_running_progress_line(stage="Route", completed=0, phase=0)
        second_line = _render_running_progress_line(stage="Route", completed=0, phase=1)

        self.assertNotEqual(first_frame, second_frame)
        self.assertNotEqual(first_line, second_line)
        self.assertNotIn("#", first_frame)
        self.assertNotIn("-", first_frame)
        self.assertIn(">", first_frame)
        self.assertTrue(first_frame.endswith("1/9"))
        self.assertTrue(first_line.startswith("◐ ["))
        self.assertTrue(second_line.startswith("◓ ["))
        self.assertIn("Route · 读取需求", first_line)
        self.assertIn("Route · 识别层级", second_line)
        self.assertIn(
            "Technical Design · 准备上下文",
            _render_running_progress_line(stage="TechnicalDesign", completed=3, phase=0, activity="准备上下文"),
        )

    def test_run_requirement_animation_wraps_interactive_stage_line(self) -> None:
        import time

        from agent_team.cli import _run_requirement_with_stage_animation

        stdout = TtyStringIO()
        with patch("sys.stdout", stdout):
            result = _run_requirement_with_stage_animation(
                stage="Route",
                completed=0,
                run=lambda: (time.sleep(0.18), "done")[1],
            )

        output = stdout.getvalue()
        self.assertEqual(result, "done")
        self.assertIn("\r◐ [", output)
        self.assertIn("[>", output)
        self.assertIn("Route", output)
        self.assertIn("\033[2K", output)

    def test_run_requirement_stage_banner_keeps_static_progress_for_non_tty(self) -> None:
        from agent_team.cli import _print_run_requirement_stage_banner

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            _print_run_requirement_stage_banner(stage="Route", completed=0)

        output = stdout.getvalue()
        self.assertIn("[1/9 Route] 路由需求和五层影响中", output)
        self.assertIn("进度: [", output)
        self.assertIn("-", output)
        self.assertNotIn("\033[2K", output)

    def test_run_requirement_interactive_tty_walks_through_all_human_gates(self) -> None:
        from agent_team.cli import main

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            stdin = TtyStringIO("写个js文件，并打印hello world\ny\ny\ny\n")
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
            self.assertIn("[1/9 Route] 路由需求和五层影响中", output)
            self.assertIn("Product Definition Delta:", output)
            self.assertIn("Technical Design:", output)
            self.assertIn("Session Handoff:", output)
            self.assertIn("Session completed.", output)
            session_id = next(line for line in output.splitlines() if line.startswith("session_id: ")).split(": ", 1)[1]
            session_dir = Path(temp_dir) / session_id
            self.assertTrue((session_dir / "product-definition-delta.md").exists())
            self.assertTrue((session_dir / "technical-design.md").exists())
            self.assertTrue((session_dir / "session-handoff.md").exists())

    def test_run_requirement_interactive_auto_keeps_human_design_gate(self) -> None:
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
            self.assertIn("[1/9 Route] 路由需求和五层影响中", output)
            self.assertIn("[4/9 Technical Design] 生成 L2 技术设计中", output)
            self.assertIn("请选择下一步：", output)
            self.assertIn("Session saved.", output)
            self.assertNotIn("--auto: 已自动通过 Technical Design", output)
            session_id = next(line for line in output.splitlines() if line.startswith("session_id: ")).split(": ", 1)[1]
            session_dir = Path(temp_dir) / session_id
            self.assertTrue((session_dir / "technical-design.md").exists())
            self.assertFalse((session_dir / "implementation.md").exists())
            self.assertFalse((session_dir / "verification-report.md").exists())
            self.assertFalse((session_dir / "acceptance-report.md").exists())

    def test_run_requirement_session_handoff_prompt_does_not_reprint_menu_after_invalid_input(self) -> None:
        from agent_team.cli import main

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            stdin = TtyStringIO("写个js文件，并打印hello world\ny\ny\n\nbad\nq\n")
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
            self.assertEqual(output.count("  y) 通过最终交付，完成本次任务"), 1)
            self.assertEqual(output.count("  n) 不通过最终交付，结束为 no-go"), 1)
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

    def test_blocked_next_step_points_users_to_alignment_questions(self) -> None:
        from agent_team.cli import _run_requirement_blocked_next_step_text, _run_requirement_next_step_text

        self.assertIn("product-definition-delta.md", _run_requirement_blocked_next_step_text("ProductDefinition"))
        self.assertIn("澄清问题", _run_requirement_blocked_next_step_text("ProductDefinition"))
        self.assertIn("technical-design.md", _run_requirement_blocked_next_step_text("TechnicalDesign"))
        self.assertIn("待确认问题", _run_requirement_blocked_next_step_text("TechnicalDesign"))
        self.assertIn("澄清问题", _run_requirement_next_step_text("ProductDefinition"))
        self.assertIn("待确认问题", _run_requirement_next_step_text("TechnicalDesign"))

    def test_run_accepts_positional_requirement_message(self) -> None:
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
                    "执行这个需求：支持短命令入口",
                    "--executor",
                    "dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("runtime_driver_status: waiting_human", result.stdout)
            self.assertIn("next_action: approve", result.stdout)

    def test_approve_uses_latest_session_by_default(self) -> None:
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
                    "执行这个需求：测试 approve",
                    "--executor",
                    "dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr)

            approve = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    temp_dir,
                    "approve",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(approve.returncode, 0, approve.stderr)
            self.assertIn("current_state: ProjectRuntime", approve.stdout)
            self.assertIn("human_decision: go", approve.stdout)

    def test_run_requirement_dry_run_stops_at_technical_design_gate_after_product_definition_go(self) -> None:
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
            session_id = _session_id_from_stdout(product_result.stdout)

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
            self.assertIn("current_state: WaitForTechnicalDesignApproval", result.stdout)
            self.assertIn("current_stage: TechnicalDesign", result.stdout)
            session_dir = Path(temp_dir) / session_id
            self.assertTrue((session_dir / "product-definition-delta.md").exists())
            self.assertTrue((session_dir / "project-landing-delta.md").exists())
            self.assertTrue((session_dir / "technical-design.md").exists())
            self.assertFalse((session_dir / "implementation.md").exists())
            self.assertFalse((session_dir / "verification-report.md").exists())

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
            session_id = _session_id_from_stdout(product_result.stdout)

            approve_product_definition = subprocess.run(
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
            self.assertEqual(approve_product_definition.returncode, 0)
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
            self.assertIn("current_state: WaitForTechnicalDesignApproval", result.stdout)

            approve_technical_design = subprocess.run(
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
            self.assertEqual(approve_technical_design.returncode, 0)
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
            self.assertIn("current_stage: SessionHandoff", result.stdout)
            self.assertIn("human_decision: pending", result.stdout)

    def test_run_requirement_command_executor_receives_stage_environment(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            worker_path = Path(temp_dir) / "stage_worker.py"
            worker_path.write_text(
                "import json, os, sys\n"
                "stage = os.environ['AGENT_TEAM_STAGE']\n"
                "print('worker stdout')\n"
                "print('worker stderr', file=sys.stderr)\n"
                "payloads = {\n"
                "  'Route': {'status': 'completed', 'artifact_content': '{\"affected_layers\":[\"L1\"]}', 'journal': '', 'evidence': [{'name': 'route_classification', 'kind': 'artifact', 'summary': 'routed'}], 'summary': 'route'},\n"
                "  'ProductDefinition': {'status': 'completed', 'artifact_content': '# Product Definition Delta\\n', 'journal': '', 'evidence': [{'name': 'l1_classification', 'kind': 'artifact', 'summary': 'l1'}], 'summary': 'l1'},\n"
                "}\n"
                "payload = payloads[stage]\n"
                "payload.setdefault('findings', [])\n"
                "payload.setdefault('suggested_next_owner', '')\n"
                "payload.setdefault('acceptance_status', '')\n"
                "payload.setdefault('blocked_reason', '')\n"
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
            session_id = _session_id_from_stdout(result.stdout)
            session_dir = Path(temp_dir) / session_id
            runtime_session_dir = Path(temp_dir) / "_runtime" / "sessions" / session_id
            self.assertIn("Product Definition Delta", (session_dir / "product-definition-delta.md").read_text())
            self.assertIn(
                "worker stdout",
                (
                    runtime_session_dir
                    / "roles"
                    / "route"
                    / "attempt-001"
                    / "command-outputs"
                    / "route-command-stdout.txt"
                ).read_text(),
            )
            self.assertIn(
                "worker stderr",
                (
                    runtime_session_dir
                    / "roles"
                    / "route"
                    / "attempt-001"
                    / "command-outputs"
                    / "route-command-stderr.txt"
                ).read_text(),
            )

    def test_run_requirement_stage_report_prints_worktree_changes(self) -> None:
        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            root = Path(temp_dir)
            repo_root = root / "repo"
            repo_root.mkdir()
            subprocess.run(["git", "init"], cwd=repo_root, capture_output=True, text=True, check=True)
            (repo_root / "existing.txt").write_text("clean baseline\n")
            subprocess.run(["git", "add", "existing.txt"], cwd=repo_root, capture_output=True, text=True, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Agent Team Test",
                    "-c",
                    "user.email=agent-team@example.invalid",
                    "commit",
                    "-m",
                    "init",
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            (repo_root / "existing.txt").write_text("dirty before stage\n")
            worker_path = root / "stage_worker.py"
            worker_path.write_text(
                "import json, os\n"
                "from pathlib import Path\n"
                "stage = os.environ['AGENT_TEAM_STAGE']\n"
                "repo = Path(os.environ['AGENT_TEAM_REPO_ROOT'])\n"
                "if stage == 'ProductDefinition':\n"
                "    (repo / 'existing.txt').write_text('dirty after stage\\n')\n"
                "    (repo / 'created.txt').write_text('created by stage\\n')\n"
                "payloads = {\n"
                "  'Route': {'status': 'completed', 'artifact_content': '{\"affected_layers\":[\"L1\"]}', 'journal': '', 'evidence': [{'name': 'route_classification', 'kind': 'artifact', 'summary': 'routed'}], 'summary': 'route'},\n"
                "  'ProductDefinition': {'status': 'completed', 'artifact_content': '# Product Definition Delta\\n', 'journal': '', 'evidence': [{'name': 'l1_classification', 'kind': 'artifact', 'summary': 'l1'}], 'summary': 'l1'},\n"
                "}\n"
                "payload = payloads[stage]\n"
                "payload.setdefault('findings', [])\n"
                "payload.setdefault('suggested_next_owner', '')\n"
                "payload.setdefault('acceptance_status', '')\n"
                "payload.setdefault('blocked_reason', '')\n"
                "Path(os.environ['AGENT_TEAM_RESULT_BUNDLE']).write_text(json.dumps(payload))\n"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_team",
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    str(root / "state"),
                    "run",
                    "--message",
                    "执行这个需求：验证 CLI 展示工作树改动",
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
        self.assertIn("本阶段改动:", result.stdout)
        self.assertIn("created.txt", result.stdout)
        self.assertIn("existing.txt", result.stdout)
        self.assertIn("执行前已 dirty", result.stdout)

    def test_panel_json_prints_snapshot(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

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
                    "执行这个需求：做一个带面板的 workflow",
                    "--executor",
                    "dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bootstrap.returncode, 0)
            session_id = _session_id_from_stdout(bootstrap.stdout)

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
                    "执行这个需求：做一个可查询状态的 workflow",
                    "--executor",
                    "dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bootstrap.returncode, 0)
            session_id = _session_id_from_stdout(bootstrap.stdout)

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

    def test_record_human_decision_routes_product_definition_approval_to_project_runtime(self) -> None:
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
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run_result.returncode, 0)
            session_id = _session_id_from_stdout(run_result.stdout)

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
            self.assertIn("current_state: ProjectRuntime", result.stdout)
            self.assertIn("current_stage: ProjectRuntime", result.stdout)

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
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run_result.returncode, 0)
            session_id = _session_id_from_stdout(run_result.stdout)

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
                    "Verification",
                    "--target-stage",
                    "Implementation",
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
                    current_stage="SessionHandoff",
                    stage_statuses={
                        "ProductDefinition": "approved",
                        "Implementation": "completed",
                        "Verification": "passed",
                    },
                    acceptance_status="recommended_go",
                    human_decision="pending",
                    artifact_paths={"workflow_summary": str(store.workflow_summary_path(session.session_id))},
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
                    "SessionHandoff",
                    "--target-stage",
                    "Implementation",
                    "--issue",
                    "Acceptance found a missed parity issue.",
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
            self.assertIn("current_state: Implementation", result.stdout)
            self.assertIn("current_stage: Implementation", result.stdout)
            self.assertIn("human_decision: rework", result.stdout)


    def test_friendly_feedback_can_apply_rework_decision(self) -> None:
        from agent_team.models import WorkflowSummary
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            store = StateStore(Path(temp_dir))
            session = store.create_session("做一个支持简短反馈命令的流程")
            store.save_workflow_summary(
                session,
                WorkflowSummary(
                    session_id=session.session_id,
                    runtime_mode="session_bootstrap",
                    current_state="WaitForHumanDecision",
                    current_stage="SessionHandoff",
                    stage_statuses={
                        "ProductDefinition": "approved",
                        "Implementation": "completed",
                        "Verification": "passed",
                    },
                    acceptance_status="recommended_go",
                    human_decision="pending",
                    artifact_paths={"workflow_summary": str(store.workflow_summary_path(session.session_id))},
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
                    "feedback",
                    "Implementation",
                    "服务端改动缺少 API 到数据库的端到端验证",
                    "--session-id",
                    session.session_id,
                    "--lesson",
                    "服务端改动必须提供接口到数据的证据",
                    "--required-evidence",
                    "API response",
                    "--required-evidence",
                    "database query result",
                    "--rework",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("recorded_feedback:", result.stdout)
            self.assertIn("current_state: Implementation", result.stdout)
            self.assertIn("human_decision: rework", result.stdout)



    def test_run_defaults_to_new_isolated_worktree_and_continue_reuses_it(self) -> None:
        from agent_team.cli import main

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            repo_root.mkdir()
            subprocess.run(["git", "init"], cwd=repo_root, capture_output=True, text=True, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)
            (repo_root / "README.md").write_text("# test repo\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo_root, capture_output=True, text=True, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_root, capture_output=True, text=True, check=True)

            stdout = io.StringIO()
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "run",
                        "--message",
                        "新增 登录 按钮",
                        "--executor",
                        "dry-run",
                    ]
                )

            self.assertEqual(exit_code, 0)
            output = stdout.getvalue()
            self.assertIn("worktree_path:", output)
            self.assertIn("branch: agent-team/", output)
            self.assertIn("新增-登录-按钮", output)
            session_id = _session_id_from_stdout(output)

            index_path = repo_root / ".agent-team" / "session-index.json"
            index_payload = json.loads(index_path.read_text())
            entry = index_payload["sessions"][0]
            self.assertEqual(entry["session_id"], session_id)
            self.assertIn("新增-登录-按钮", entry["branch"])
            worktree_path = Path(entry["worktree_path"])
            self.assertTrue(worktree_path.exists())
            self.assertTrue((worktree_path / ".agent-team" / session_id / "product-definition-delta.md").exists())

            continue_stdout = io.StringIO()
            with patch("sys.stdout", continue_stdout):
                continue_exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "continue",
                        "--executor",
                        "dry-run",
                    ]
                )

            self.assertEqual(continue_exit_code, 0)
            continue_output = continue_stdout.getvalue()
            self.assertIn(f"session_id: {session_id}", continue_output)
            self.assertEqual(len(list((repo_root / ".worktrees").iterdir())), 1)

    def test_continue_accepts_session_id_positional_alias(self) -> None:
        from agent_team.cli import _normalize_command_aliases

        self.assertEqual(
            _normalize_command_aliases(["--repo-root", "/tmp/repo", "continue", "abc123", "--executor", "dry-run"]),
            ["--repo-root", "/tmp/repo", "run", "--continue", "--session-id", "abc123", "--executor", "dry-run"],
        )


if __name__ == "__main__":
    unittest.main()
