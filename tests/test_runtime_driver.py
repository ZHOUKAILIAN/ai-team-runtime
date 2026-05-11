import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch


def local_temp_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".test_tmp"
    path.mkdir(exist_ok=True)
    return path


class RuntimeDriverSchemaTests(unittest.TestCase):
    def test_stage_result_schema_is_strict_for_codex_structured_output(self) -> None:
        from agent_team.runtime_driver import _stage_result_schema

        def assert_strict_objects(schema: dict[str, object], path: str) -> None:
            if schema.get("type") == "object":
                properties = schema.get("properties", {})
                required = schema.get("required", [])
                self.assertEqual(schema.get("additionalProperties"), False, path)
                self.assertEqual(set(required), set(properties), path)
                for name in required:
                    self.assertIn(name, properties, f"{path}: {name} in required but not properties")
                for _name, child in properties.items():
                    if isinstance(child, dict):
                        assert_strict_objects(child, f"{path}.{_name}")
            if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
                assert_strict_objects(schema["items"], f"{path}[]")

        assert_strict_objects(_stage_result_schema(), "$")

    def test_stage_result_schema_excludes_runtime_control_fields(self) -> None:
        from agent_team.runtime_driver import _stage_result_schema
        from agent_team.stage_payload import FORBIDDEN_STAGE_PAYLOAD_FIELDS

        properties = _stage_result_schema()["properties"]

        for field in FORBIDDEN_STAGE_PAYLOAD_FIELDS:
            self.assertNotIn(field, properties)
        self.assertNotIn("supplemental_artifacts", properties)

    def test_codex_prompt_instructs_product_definition_l1_boundaries(self) -> None:
        from agent_team.execution_context import StageExecutionContext
        from agent_team.models import Finding, StageContract
        from agent_team.runtime_driver import StageExecutionRequest, _build_codex_prompt

        request = StageExecutionRequest(
            repo_root=Path("/repo"),
            state_store=None,
            session_id="session",
            run_id="product-definition-run-1",
            contract=StageContract(
                session_id="session",
                stage="ProductDefinition",
                goal="Write L1 delta",
                contract_id="contract",
                required_outputs=["product-definition-delta.md"],
            ),
            context=StageExecutionContext(
                session_id="session",
                stage="ProductDefinition",
                round_index=1,
                context_id="context",
                contract_id="contract",
                original_request_summary="本期 PRD 里包含稳定产品对象和实现细节",
                approved_product_definition_summary="",
                acceptance_matrix=[],
                constraints=[],
                required_outputs=["product-definition-delta.md"],
                required_evidence=[],
                relevant_artifacts=[],
                actionable_findings=[
                    Finding(
                        source_stage="ProductDefinition",
                        target_stage="ProductDefinition",
                        issue="确认哪些内容真正进入 L1",
                    )
                ],
            ),
            contract_path=Path("/tmp/contract.json"),
            context_path=Path("/tmp/context.json"),
            result_path=Path("/tmp/result.json"),
            output_schema_path=Path("/tmp/schema.json"),
        )

        prompt = _build_codex_prompt(request)

        self.assertIn("Write artifact_content in Simplified Chinese", prompt)
        self.assertIn("Write every human-readable artifact", prompt)
        self.assertIn("Do not create or modify the required stage artifact file", prompt)
        self.assertIn("product-definition-delta.md", prompt)
        self.assertIn("Separate L1 candidates from non-L1 task content explicitly", prompt)
        self.assertIn("must not include implementation plans", prompt)
        self.assertIn("确认哪些内容真正进入 L1", prompt)
        self.assertNotIn("Non-Goals", prompt)

    def test_codex_prompt_instructs_technical_design_tables_and_flowcharts(self) -> None:
        from agent_team.execution_context import StageExecutionContext
        from agent_team.models import StageContract
        from agent_team.runtime_driver import StageExecutionRequest, _build_codex_prompt

        request = StageExecutionRequest(
            repo_root=Path("/repo"),
            state_store=None,
            session_id="session",
            run_id="technical-design-run-1",
            contract=StageContract(
                session_id="session",
                stage="TechnicalDesign",
                goal="Write technical design",
                contract_id="contract",
                required_outputs=["technical-design.md"],
            ),
            context=StageExecutionContext(
                session_id="session",
                stage="TechnicalDesign",
                round_index=1,
                context_id="context",
                contract_id="contract",
                original_request_summary="写个js文件，并打印hello world",
                approved_product_definition_summary="# Product Definition Delta",
                acceptance_matrix=[],
                constraints=[],
                required_outputs=["technical-design.md"],
                required_evidence=[],
                relevant_artifacts=[],
            ),
            contract_path=Path("/tmp/contract.json"),
            context_path=Path("/tmp/context.json"),
            result_path=Path("/tmp/result.json"),
            output_schema_path=Path("/tmp/schema.json"),
        )

        prompt = _build_codex_prompt(request)

        self.assertIn("technical-design.md", prompt)
        self.assertIn("Simplified Chinese", prompt)
        self.assertIn("Do not edit repository source code", prompt)
        self.assertIn("Prefer Mermaid flowcharts", prompt)
        self.assertIn("Markdown tables", prompt)
        self.assertIn("Avoid bullet lists", prompt)

    def test_codex_prompt_instructs_implementation_to_follow_approved_technical_design(self) -> None:
        from agent_team.execution_context import StageExecutionContext
        from agent_team.models import StageContract
        from agent_team.runtime_driver import StageExecutionRequest, _build_codex_prompt

        request = StageExecutionRequest(
            repo_root=Path("/repo"),
            state_store=None,
            session_id="session",
            run_id="implementation-run-1",
            contract=StageContract(
                session_id="session",
                stage="Implementation",
                goal="Implement",
                contract_id="contract",
                required_outputs=["implementation.md"],
            ),
            context=StageExecutionContext(
                session_id="session",
                stage="Implementation",
                round_index=1,
                context_id="context",
                contract_id="contract",
                original_request_summary="写个js文件，并打印hello world",
                approved_product_definition_summary="# Product Definition Delta",
                acceptance_matrix=[],
                constraints=[],
                required_outputs=["implementation.md"],
                required_evidence=[],
                relevant_artifacts=[],
                approved_technical_design_content="# 技术设计\n\n- 按已确认技术设计创建 hello.js。\n",
            ),
            contract_path=Path("/tmp/contract.json"),
            context_path=Path("/tmp/context.json"),
            result_path=Path("/tmp/result.json"),
            output_schema_path=Path("/tmp/schema.json"),
        )

        prompt = _build_codex_prompt(request)

        self.assertIn("approved technical design", prompt)
        self.assertIn("implementation.md in Simplified Chinese", prompt)
        self.assertIn("按已确认技术设计创建 hello.js", prompt)

    def test_codex_prompt_includes_enabled_skills(self) -> None:
        from agent_team.execution_context import StageExecutionContext
        from agent_team.models import StageContract
        from agent_team.runtime_driver import StageExecutionRequest, _build_codex_prompt
        from agent_team.skill_registry import Skill

        request = StageExecutionRequest(
            repo_root=Path("/repo"),
            state_store=None,
            session_id="session",
            run_id="implementation-run-1",
            contract=StageContract(
                session_id="session",
                stage="Implementation",
                goal="Implement",
                contract_id="contract",
                required_outputs=["implementation.md"],
            ),
            context=StageExecutionContext(
                session_id="session",
                stage="Implementation",
                round_index=1,
                context_id="context",
                contract_id="contract",
                original_request_summary="写个js文件，并打印hello world",
                approved_product_definition_summary="# Product Definition Delta",
                acceptance_matrix=[],
                constraints=[],
                required_outputs=["implementation.md"],
                required_evidence=[],
                relevant_artifacts=[],
                approved_technical_design_content="# 技术设计\n\n- 创建 hello.js。\n",
            ),
            contract_path=Path("/tmp/contract.json"),
            context_path=Path("/tmp/context.json"),
            result_path=Path("/tmp/result.json"),
            output_schema_path=Path("/tmp/schema.json"),
            skill_asset_root=Path(
                "/repo/.agent-team/_runtime/sessions/session/roles/implementation/attempt-001/execution-contexts/skills/.agent-team/skills"
            ),
            skills=[
                Skill(
                    name="plan",
                    description="Plan the implementation",
                    content="# Plan\n\nDo the plan.",
                    source="builtin",
                    path=Path("/skills/plan/SKILL.md"),
                    source_ref="https://example.com/skills/plan",
                    stages=("Implementation",),
                    delivery="sandbox",
                )
            ],
        )

        prompt = _build_codex_prompt(request)

        self.assertIn("<enabled_skills>", prompt)
        self.assertIn('<skill name="plan">', prompt)
        self.assertIn("<source_type>builtin</source_type>", prompt)
        self.assertIn("<source_ref>https://example.com/skills/plan</source_ref>", prompt)
        self.assertIn(
            "<asset_root>/repo/.agent-team/_runtime/sessions/session/roles/implementation/attempt-001/execution-contexts/skills/.agent-team/skills/plan/</asset_root>",
            prompt,
        )
        self.assertIn("Do the plan", prompt)

    def test_dry_run_product_definition_artifact_records_l1_and_non_l1(self) -> None:
        from agent_team.execution_context import StageExecutionContext
        from agent_team.models import Finding
        from agent_team.runtime_driver import _dry_run_artifact_content, _dry_run_supplemental_artifacts

        context = StageExecutionContext(
            session_id="session",
            stage="ProductDefinition",
            round_index=1,
            context_id="context",
            contract_id="contract",
            original_request_summary="写个js文件，并打印hello world",
            approved_product_definition_summary="",
            acceptance_matrix=[],
            constraints=[],
            required_outputs=["product-definition-delta.md"],
            required_evidence=[],
            relevant_artifacts=[],
            actionable_findings=[
                Finding(
                    source_stage="ProductDefinition",
                    target_stage="ProductDefinition",
                    issue="在桌面生成文件",
                )
            ],
        )

        artifact = _dry_run_artifact_content("ProductDefinition", context)

        self.assertIn("# Product Definition Delta", artifact)
        self.assertIn("人工修改意见", artifact)
        self.assertIn("在桌面生成文件", artifact)
        self.assertIn("非 L1 内容", artifact)
        self.assertNotIn("Non-Goals", artifact)
        self.assertEqual(_dry_run_supplemental_artifacts("ProductDefinition", context), {})

    def test_codex_exec_stage_executor_skips_git_repo_check(self) -> None:
        from agent_team.execution_context import StageExecutionContext
        from agent_team.models import StageContract
        from agent_team.runtime_driver import CodexExecStageExecutor, RuntimeDriverOptions, StageExecutionRequest

        commands = []

        def fake_run(command, *, cwd, capture_output, text, timeout, check, env=None, stdin=None):
            commands.append(command)
            output_path = Path(command[command.index("-o") + 1])
            output_path.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "artifact_content": "# Product Definition Delta\n",
                        "journal": "",
                        "findings": [],
                        "evidence": [],
                        "suggested_next_owner": "",
                        "summary": "ProductDefinition completed.",
                        "acceptance_status": "",
                        "blocked_reason": "",
                    }
                )
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            root = Path(temp_dir)
            request = StageExecutionRequest(
                repo_root=root,
                state_store=None,
                session_id="session",
                run_id="product-definition-run-1",
                contract=StageContract(
                    session_id="session",
                    stage="ProductDefinition",
                    goal="Write an L1 delta.",
                    contract_id="contract",
                    required_outputs=["product-definition-delta.md"],
                ),
                context=StageExecutionContext(
                    session_id="session",
                    stage="ProductDefinition",
                    round_index=1,
                    context_id="context",
                    contract_id="contract",
                    original_request_summary="写个js文件，并打印hello world",
                    approved_product_definition_summary="",
                    acceptance_matrix=[],
                    constraints=[],
                    required_outputs=["product-definition-delta.md"],
                    required_evidence=[],
                    relevant_artifacts=[],
                ),
                contract_path=root / "contract.json",
                context_path=root / "context.json",
                result_path=root / "result.json",
                output_schema_path=root / "schema.json",
                prompt_path=root / "prompt.md",
            )

            with patch("agent_team.runtime_driver.subprocess.run", fake_run):
                envelope = CodexExecStageExecutor(RuntimeDriverOptions()).execute(request)

        self.assertEqual(len(commands), 1)
        self.assertIn("--skip-git-repo-check", commands[0])
        self.assertEqual(envelope.session_id, "session")
        self.assertEqual(envelope.stage, "ProductDefinition")
        self.assertEqual(envelope.contract_id, "contract")
        self.assertEqual(envelope.artifact_name, "product-definition-delta.md")

    def test_stage_payload_parser_rejects_runtime_control_fields(self) -> None:
        from agent_team.runtime_driver import _stage_result_from_json_text

        request = SimpleNamespace(
            session_id="runtime-session",
            contract=SimpleNamespace(stage="ProductDefinition", contract_id="runtime-contract"),
        )
        result = _stage_result_from_json_text(
            request=request,
            value=json.dumps(
                {
                    "stage": "ProductDefinition",
                    "status": "completed",
                    "artifact_content": "# Product Definition Delta\n",
                    "journal": "",
                    "findings": [],
                    "evidence": [],
                    "suggested_next_owner": "",
                    "summary": "done",
                    "acceptance_status": "",
                    "blocked_reason": "",
                }
            ),
            source="stdout",
        )

        self.assertEqual(result.status, "blocked")
        self.assertIn("runtime-controlled field(s): stage", result.blocked_reason)

    def test_stage_run_streams_accept_timeout_bytes(self) -> None:
        from agent_team.runtime_driver import _write_stage_run_streams

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            request = SimpleNamespace(
                result_path=Path(temp_dir) / "stage_runs" / "route-run-1_result.json",
                run_id="route-run-1",
            )
            _write_stage_run_streams(request, stdout=b"partial stdout", stderr=b"partial stderr")

            stdout = (Path(temp_dir) / "stage_runs" / "route-run-1_stdout.txt").read_text()
            stderr = (Path(temp_dir) / "stage_runs" / "route-run-1_stderr.txt").read_text()

        self.assertEqual(stdout, "partial stdout")
        self.assertEqual(stderr, "partial stderr")


class RuntimeDriverTraceTests(unittest.TestCase):
    def test_dry_run_records_non_skippable_stage_trace(self) -> None:
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
                    "执行这个需求：验证 runtime trace 不允许跳过链路步骤",
                    "--executor",
                    "dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            session_id = dict(
                line.split(": ", 1) for line in result.stdout.splitlines() if ": " in line
            )["session_id"]
            stage_result_path = (
                Path(temp_dir)
                / "_runtime"
                / "sessions"
                / session_id
                / "roles"
                / "product-definition"
                / "attempt-001"
                / "stage-results"
                / "product-definition-stage-result.json"
            )
            stage_result = json.loads(stage_result_path.read_text())

        self.assertEqual(
            [step["step"] for step in stage_result["steps"]],
            [
                "contract_built",
                "execution_context_built",
                "stage_run_acquired",
                "executor_started",
                "executor_completed",
                "worktree_changes_detected",
                "result_submitted",
                "gate_evaluated",
                "state_advanced",
            ],
        )
        self.assertTrue(all(step["status"] == "ok" for step in stage_result["steps"]))
        self.assertIn("stage_result", stage_result)
        self.assertNotIn("artifact_content", stage_result["stage_result"])
        self.assertNotIn("supplemental_artifacts", stage_result["stage_result"])
        self.assertIn("artifact_path", stage_result["stage_result"])
        self.assertFalse(
            (
                Path(temp_dir)
                / "_runtime"
                / "sessions"
                / session_id
                / "roles"
                / "product-definition"
                / "attempt-001"
                / "stage-results"
                / "product-definition-run-state.json"
            ).exists()
        )
        self.assertFalse(
            (
                Path(temp_dir)
                / "_runtime"
                / "sessions"
                / session_id
                / "roles"
                / "product-definition"
                / "attempt-001"
                / "stage-results"
                / "product-definition-runtime-trace.json"
            ).exists()
        )
        self.assertFalse(
            (
                Path(temp_dir)
                / "_runtime"
                / "sessions"
                / session_id
                / "roles"
                / "product-definition"
                / "attempt-001"
                / "execution-contexts"
                / "product-definition-agent-prompt-bundle.md"
            ).exists()
        )

    def test_runtime_trace_validator_blocks_missing_required_steps(self) -> None:
        from agent_team.runtime_driver import REQUIRED_PASS_TRACE_STEPS, _validate_runtime_trace

        trace = [{"step": step, "status": "ok"} for step in REQUIRED_PASS_TRACE_STEPS[:-1]]
        result = _validate_runtime_trace(trace, required_steps=REQUIRED_PASS_TRACE_STEPS)

        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("state_advanced", result.reason)

    def test_command_stage_records_worktree_changes(self) -> None:
        from agent_team.runtime_driver import RuntimeDriverOptions, run_requirement
        from agent_team.state import StateStore

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            root = Path(temp_dir)
            repo_root = root / "repo"
            state_root = root / "state"
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

            result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                message="执行这个需求：验证工作树改动记录",
                options=RuntimeDriverOptions(
                    executor="command",
                    executor_command=f"{sys.executable} {worker_path}",
                ),
            )
            run = StateStore(state_root).latest_stage_run(result.session_id, stage="ProductDefinition")

        self.assertIsNotNone(run)
        steps = run.steps if run is not None else []
        details = next(step["details"] for step in steps if step["step"] == "worktree_changes_detected")
        self.assertTrue(details["available"])
        self.assertEqual(details["before_dirty_count"], 1)
        self.assertEqual(details["after_dirty_count"], 2)
        self.assertEqual(set(details["changed_file_paths"]), {"created.txt", "existing.txt"})
        by_path = {item["path"]: item for item in details["changed_files"]}
        self.assertEqual(by_path["created.txt"]["change_type"], "new_dirty_file")
        self.assertEqual(by_path["existing.txt"]["change_type"], "content_changed")
        self.assertTrue(by_path["existing.txt"]["preexisting_dirty"])


class RuntimeDriverInteractiveFlowTests(unittest.TestCase):
    def test_interactive_dry_run_stops_at_technical_design_approval_after_product_definition_go(self) -> None:
        from agent_team.runtime_driver import RuntimeDriverOptions, run_requirement
        from agent_team.stage_machine import StageMachine
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir)
            product_definition_result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                message="执行这个需求：写个js文件，并打印hello world",
                options=RuntimeDriverOptions(executor="dry-run", interactive=True),
            )
            store = StateStore(state_root)
            session = store.load_session(product_definition_result.session_id)
            summary = store.load_workflow_summary(product_definition_result.session_id)
            store.save_workflow_summary(session, StageMachine().apply_human_decision(summary=summary, decision="go"))
            result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                session_id=product_definition_result.session_id,
                options=RuntimeDriverOptions(executor="dry-run", interactive=True),
            )

            self.assertEqual(result.status, "waiting_human")
            self.assertEqual(result.current_state, "WaitForTechnicalDesignApproval")
            self.assertEqual(result.current_stage, "TechnicalDesign")
            self.assertEqual(result.stage_run_count, 2)
            session_dir = Path(temp_dir) / result.session_id
            self.assertTrue((session_dir / "product-definition-delta.md").exists())
            self.assertTrue((session_dir / "project-landing-delta.md").exists())
            self.assertTrue((session_dir / "technical-design.md").exists())

    def test_auto_advance_intermediate_stops_at_final_session_handoff_gate(self) -> None:
        from agent_team.runtime_driver import RuntimeDriverOptions, run_requirement
        from agent_team.stage_machine import StageMachine
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            state_root = Path(temp_dir)
            product_definition_result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                message="执行这个需求：写个js文件，并打印hello world",
                options=RuntimeDriverOptions(executor="dry-run", interactive=True),
            )
            store = StateStore(state_root)
            session = store.load_session(product_definition_result.session_id)
            summary = store.load_workflow_summary(product_definition_result.session_id)
            store.save_workflow_summary(session, StageMachine().apply_human_decision(summary=summary, decision="go"))
            result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                session_id=product_definition_result.session_id,
                options=RuntimeDriverOptions(
                    executor="dry-run",
                    interactive=True,
                    auto_advance_intermediate=True,
                ),
            )

            self.assertEqual(result.status, "waiting_human")
            self.assertEqual(result.current_state, "WaitForTechnicalDesignApproval")
            self.assertEqual(result.current_stage, "TechnicalDesign")
            self.assertEqual(result.stage_run_count, 2)
            summary = store.load_workflow_summary(product_definition_result.session_id)
            store.save_workflow_summary(session, StageMachine().apply_human_decision(summary=summary, decision="go"))

            result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                session_id=product_definition_result.session_id,
                options=RuntimeDriverOptions(
                    executor="dry-run",
                    interactive=True,
                    auto_advance_intermediate=True,
                ),
            )

            self.assertEqual(result.status, "waiting_human")
            self.assertEqual(result.current_state, "WaitForHumanDecision")
            self.assertEqual(result.current_stage, "SessionHandoff")
            self.assertEqual(result.stage_run_count, 5)
            session_dir = Path(temp_dir) / result.session_id
            self.assertTrue((session_dir / "product-definition-delta.md").exists())
            self.assertTrue((session_dir / "project-landing-delta.md").exists())
            self.assertTrue((session_dir / "technical-design.md").exists())
            self.assertTrue((session_dir / "implementation.md").exists())
            self.assertTrue((session_dir / "verification-report.md").exists())
            self.assertTrue((session_dir / "governance-review.md").exists())
            self.assertTrue((session_dir / "acceptance-report.md").exists())
            self.assertTrue((session_dir / "session-handoff.md").exists())

    def test_interactive_driver_blocks_invalid_stage_identity_without_traceback(self) -> None:
        from agent_team.runtime_driver import RuntimeDriverOptions, run_requirement
        from agent_team.stage_machine import StageMachine
        from agent_team.state import StateStore

        repo_root = Path(__file__).resolve().parents[1]

        with TemporaryDirectory(dir=local_temp_dir()) as temp_dir:
            worker_path = Path(temp_dir) / "bad_stage_worker.py"
            worker_path.write_text(
                "import json, os\n"
                "stage = os.environ['AGENT_TEAM_STAGE']\n"
                "contract = json.loads(open(os.environ['AGENT_TEAM_CONTRACT_PATH']).read())\n"
                "payloads = {\n"
                "  'Route': {'status': 'completed', 'artifact_content': '{\"affected_layers\":[\"L1\"]}', 'journal': '', 'findings': [], 'evidence': [{'name': 'route_classification', 'kind': 'artifact', 'summary': 'routed'}], 'summary': 'route'},\n"
                "  'ProductDefinition': {'status': 'completed', 'artifact_content': '# Product Definition Delta\\n', 'journal': '', 'findings': [], 'evidence': [{'name': 'l1_classification', 'kind': 'artifact', 'summary': 'l1'}], 'summary': 'l1'},\n"
                "  'ProjectRuntime': {'status': 'completed', 'artifact_content': '# Project Landing Delta\\n', 'journal': '', 'findings': [], 'evidence': [{'name': 'project_landing_review', 'kind': 'report', 'summary': 'l3'}], 'summary': 'l3'},\n"
                "  'TechnicalDesign': {'status': 'completed', 'artifact_content': '# Technical Design\\n', 'journal': '', 'findings': [], 'evidence': [{'name': 'technical_design_plan', 'kind': 'report', 'summary': 'design'}], 'summary': 'design', 'stage': 'Route'},\n"
                "}\n"
                "payload = payloads[stage]\n"
                "payload.setdefault('suggested_next_owner', '')\n"
                "payload.setdefault('acceptance_status', '')\n"
                "payload.setdefault('blocked_reason', '')\n"
                "open(os.environ['AGENT_TEAM_RESULT_BUNDLE'], 'w').write(json.dumps(payload))\n"
            )

            state_root = Path(temp_dir)
            product_definition_result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                message="执行这个需求：写个js文件，并打印hello world",
                options=RuntimeDriverOptions(
                    executor="command",
                    executor_command=f"{sys.executable} {worker_path}",
                    interactive=True,
                ),
            )
            store = StateStore(state_root)
            session = store.load_session(product_definition_result.session_id)
            summary = store.load_workflow_summary(product_definition_result.session_id)
            store.save_workflow_summary(session, StageMachine().apply_human_decision(summary=summary, decision="go"))
            result = run_requirement(
                repo_root=repo_root,
                state_root=state_root,
                session_id=product_definition_result.session_id,
                options=RuntimeDriverOptions(
                    executor="command",
                    executor_command=f"{sys.executable} {worker_path}",
                    interactive=True,
                ),
            )
            summary = store.load_workflow_summary(result.session_id)
            run = store.latest_stage_run(result.session_id, stage="TechnicalDesign")

            self.assertEqual(result.status, "blocked")
            self.assertEqual(result.current_state, "TechnicalDesign")
            self.assertIn("Invalid stage payload JSON", result.gate_reason)
            self.assertIn("runtime-controlled field(s): stage", result.gate_reason)
            self.assertEqual(summary.blocked_reason, result.gate_reason)
            self.assertIsNotNone(run)
            assert run is not None
            self.assertEqual(run.state, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
