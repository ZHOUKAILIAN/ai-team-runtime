from __future__ import annotations

import argparse
import json
import shlex
import sys
import threading
from dataclasses import dataclass, replace
from pathlib import Path

from .execution_context import build_stage_execution_context
from .five_layer_init import DEFAULT_FIVE_LAYER_SKILL_SOURCE, run_five_layer_classification
from .gatekeeper import evaluate_candidate
from .harness_paths import default_state_root
from .models import Finding, GateResult, StageResultEnvelope, WorkflowSummary
from .panel import build_panel_snapshot
from .project_structure import ensure_project_structure
from .skill_registry import STAGES, SOURCE_LABELS, SkillRegistry
from .stage_contracts import build_stage_contract
from .stage_machine import StageMachine
from .state import StateStore
from .workflow import (
    HUMAN_REWORK_TARGETS,
    STAGES as WORKFLOW_STAGES,
    WAIT_STATES,
    artifact_key_for,
)
from .workspace_metadata import refresh_workspace_metadata


RUN_REQUIREMENT_STAGE_ORDER = WORKFLOW_STAGES
RUN_REQUIREMENT_STAGE_LABELS = {
    "Route": "Route",
    "ProductDefinition": "Product Definition",
    "ProjectRuntime": "Project Runtime",
    "TechnicalDesign": "Technical Design",
    "Implementation": "Implementation",
    "Verification": "Verification",
    "GovernanceReview": "Governance Review",
    "Acceptance": "Acceptance",
    "SessionHandoff": "Session Handoff",
}
RUN_REQUIREMENT_STAGE_TITLES = {
    "Route": "路由需求和五层影响中",
    "ProductDefinition": "生成 L1 产品定义 delta 中",
    "ProjectRuntime": "生成 L3 项目落地 delta 中",
    "TechnicalDesign": "生成 L2 技术设计中",
    "Implementation": "执行 L2 实现中",
    "Verification": "执行独立验证中",
    "GovernanceReview": "执行 L4 治理审查中",
    "Acceptance": "执行验收判断中",
    "SessionHandoff": "生成 L5 会话接力中",
}
RUN_REQUIREMENT_STAGE_ACTIVITY_STEPS = {
    "Route": ("读取需求", "识别层级", "检查红线", "整理基线", "写路由包"),
    "ProductDefinition": ("读取路由包", "识别 L1 候选", "下沉非 L1", "记录冲突", "写 delta"),
    "ProjectRuntime": ("读取 L1 delta", "识别入口", "整理目录/运行默认", "检查 L3 边界", "写落地 delta"),
    "TechnicalDesign": ("读取 L1/L3", "确认影响范围", "拆实现步骤", "整理验证策略", "写技术设计"),
    "Implementation": ("读取技术设计", "定位改动文件", "应用代码变更", "记录自检结果", "整理实现文档"),
    "Verification": ("读取实现结果", "运行验证命令", "检查证据", "记录问题", "整理验证报告"),
    "GovernanceReview": ("读取全量产物", "检查层级红线", "检查证据", "确认回写目标", "写治理审查"),
    "Acceptance": ("读取交付产物", "核对治理证据", "汇总风险证据", "形成最终建议"),
    "SessionHandoff": ("读取最终状态", "整理下一步", "保留本地现场", "标记未决项", "写接力文档"),
}
RUN_REQUIREMENT_TRACE_STEP_LABELS = {
    "contract_built": "生成阶段契约",
    "execution_context_built": "收集阶段上下文",
    "stage_run_acquired": "准备执行环境",
    "executor_started": "执行阶段任务",
    "executor_completed": "读取执行结果",
    "result_submitted": "提交阶段产物",
    "gate_evaluated": "执行质量门禁",
    "state_advanced": "更新流程状态",
}
RUN_REQUIREMENT_SPINNER_FRAMES = ("◐", "◓", "◑", "◒")
RUN_REQUIREMENT_WAIT_TO_STAGE = {
    "WaitForProductDefinitionApproval": "ProductDefinition",
    "WaitForTechnicalDesignApproval": "TechnicalDesign",
    "WaitForHumanDecision": "SessionHandoff",
}
RUN_REQUIREMENT_STAGE_DOCS = {
    "Route": ("Route Packet", "route", "route-packet.json"),
    "ProductDefinition": ("Product Definition Delta", "product_definition", "product-definition-delta.md"),
    "ProjectRuntime": ("Project Landing Delta", "project_runtime", "project-landing-delta.md"),
    "TechnicalDesign": ("Technical Design", "technical_design", "technical-design.md"),
    "Implementation": ("Implementation", "implementation", "implementation.md"),
    "Verification": ("Verification Report", "verification", "verification-report.md"),
    "GovernanceReview": ("Governance Review", "governance_review", "governance-review.md"),
    "Acceptance": ("Acceptance Report", "acceptance", "acceptance-report.md"),
    "SessionHandoff": ("Session Handoff", "session_handoff", "session-handoff.md"),
}


@dataclass(frozen=True, slots=True)
class RunRequirementMenuChoice:
    key: str
    label: str
    action: str
    decision: str = ""
    target_stage: str = ""
    requires_issue: bool = False
    aliases: tuple[str, ...] = ()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(_normalize_command_aliases(sys.argv[1:] if argv is None else argv))
    args.repo_root = args.repo_root.resolve()
    args.state_root = (
        args.state_root.resolve()
        if args.state_root is not None
        else default_state_root(repo_root=args.repo_root).resolve()
    )
    if _should_refresh_workspace_metadata(args.command):
        refresh_workspace_metadata(state_root=args.state_root, repo_root=args.repo_root)
    return args.handler(args)


def _normalize_command_aliases(argv: list[str]) -> list[str]:
    normalized = list(argv)
    index = 0
    value_options = {"--repo-root", "--state-root"}
    while index < len(normalized):
        token = normalized[index]
        if token in value_options:
            index += 2
            continue
        if token.startswith("--repo-root=") or token.startswith("--state-root="):
            index += 1
            continue
        if token == "run-requirement":
            normalized[index] = "run"
            break
        if not token.startswith("-"):
            break
        index += 1
    return normalized


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-team",
        description="Agent Team single-session workflow CLI.",
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--state-root", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Create workflow state directories and the project-level doc structure.",
        description=(
            "Create workflow state directories and the project-level doc structure. "
            "Use this once per clone before running the workflow."
        ),
    )
    init_parser.add_argument(
        "--five-layer-classification",
        choices=["auto", "run", "skip"],
        default="auto",
        help=(
            "Five-layer init classification mode. auto runs codex exec only from an interactive terminal, "
            "run forces codex exec, and skip records the init structure without running classification."
        ),
    )
    init_parser.add_argument(
        "--five-layer-timeout-seconds",
        type=int,
        default=1800,
        help="Timeout for the init-time codex exec five-layer classification run.",
    )
    init_parser.add_argument(
        "--five-layer-codex-bin",
        default="codex",
        help="Codex executable used by init-time five-layer classification.",
    )
    init_parser.add_argument(
        "--five-layer-skill-source",
        default=DEFAULT_FIVE_LAYER_SKILL_SOURCE,
        help="Remote source URL for the five-layer-classifier skill used during init.",
    )
    init_parser.set_defaults(handler=_handle_init)

    run_requirement_parser = subparsers.add_parser(
        "run",
        help="Drive an Agent Team requirement through runtime-controlled stage execution.",
        description=(
            "Create or resume an Agent Team session and let the runtime acquire, execute, submit, "
            "verify, and advance each executable stage. ProductDefinition, TechnicalDesign, "
            "and final SessionHandoff gates are always preserved."
        ),
    )
    run_requirement_target = run_requirement_parser.add_mutually_exclusive_group(required=False)
    run_requirement_target.add_argument("--message", help="Raw user message for a new requirement session.")
    run_requirement_target.add_argument("--session-id", help="Existing session ID to continue driving.")
    run_requirement_parser.add_argument(
        "--executor",
        choices=["codex-exec", "command", "dry-run"],
        default="codex-exec",
        help="Stage executor backend. codex-exec runs Codex CLI; command runs --executor-command.",
    )
    run_requirement_parser.add_argument(
        "--executor-command",
        help=(
            "Shell command for --executor command. The command receives AGENT_TEAM_* environment variables "
            "and must write a stage payload JSON to AGENT_TEAM_RESULT_BUNDLE or stdout. Runtime-controlled "
            "fields such as session_id, stage, contract_id, and artifact_name are injected by agent-team."
        ),
    )
    run_requirement_parser.add_argument(
        "--command-timeout-seconds",
        type=int,
        default=3600,
        help="Timeout for codex-exec or command executor stage runs.",
    )
    run_requirement_parser.add_argument(
        "--auto",
        action="store_true",
        help=(
            "Automatically pass non-human intermediate stages. ProductDefinition approval, "
            "TechnicalDesign approval, and final Go/No-Go remain human-gated."
        ),
    )
    run_requirement_parser.add_argument(
        "--max-stage-runs",
        type=int,
        default=12,
        help="Maximum executable stage attempts before the driver blocks to avoid loops.",
    )
    run_requirement_parser.add_argument(
        "--judge",
        choices=["off", "noop", "openai-sandbox"],
        default="off",
        help="Optional independent judge after hard gates pass.",
    )
    run_requirement_parser.add_argument("--model", default="gpt-5.4", help="Model for --judge openai-sandbox.")
    run_requirement_parser.add_argument("--docker-image", default="python:3.13-slim")
    run_requirement_parser.add_argument("--openai-api-key")
    run_requirement_parser.add_argument("--openai-base-url")
    run_requirement_parser.add_argument("--openai-proxy-url")
    run_requirement_parser.add_argument("--openai-user-agent", default="Agent-Team-Runtime/0.1")
    run_requirement_parser.add_argument("--openai-oa")
    run_requirement_parser.add_argument("--codex-model", default="", help="Optional model for codex-exec.")
    run_requirement_parser.add_argument(
        "--codex-sandbox",
        choices=["read-only", "workspace-write", "danger-full-access"],
        default="workspace-write",
        help="Sandbox mode passed to codex exec.",
    )
    run_requirement_parser.add_argument(
        "--codex-approval-policy",
        choices=["untrusted", "on-request", "never"],
        default="never",
        help="Approval policy passed to codex exec.",
    )
    run_requirement_parser.add_argument(
        "--codex-extra-arg",
        action="append",
        default=[],
        help="Extra argument passed through to codex exec. Repeat for multiple arguments.",
    )
    run_requirement_parser.add_argument(
        "--trace-prompts",
        action="store_true",
        help="Persist rendered agent prompt bundles for debugging. Disabled by default.",
    )
    run_requirement_parser.add_argument(
        "--model-output",
        choices=["summary", "raw", "off"],
        default="summary",
        help="Interactive terminal output mode. summary shows stage progress; raw adds runtime details; off prints only gates and document paths.",
    )
    run_requirement_parser.add_argument(
        "--with-skills",
        action="append",
        default=[],
        help=(
            "Enable skills for this run, e.g. Implementation:plan or Verification:security-audit. "
            "Without this flag, run uses .agent-team/skill-preferences.yaml defaults."
        ),
    )
    run_requirement_parser.add_argument(
        "--skip-skills",
        action="append",
        default=[],
        help="Skip configured skills for this run, e.g. Verification:security-audit.",
    )
    run_requirement_parser.add_argument("--skills-empty", action="store_true", help="Run without skills for this invocation.")
    run_requirement_parser.set_defaults(handler=_handle_run_requirement)

    skill_parser = subparsers.add_parser("skill", help="Inspect and manage Agent Team stage skills.")
    skill_subparsers = skill_parser.add_subparsers(dest="skill_command", required=True)

    skill_list_parser = skill_subparsers.add_parser("list", help="List available skills.")
    skill_list_parser.add_argument("--stage", choices=list(STAGES), help="Filter by stage.")
    skill_list_parser.add_argument("--source", choices=["builtin", "personal", "project"], help="Filter by source.")
    skill_list_parser.set_defaults(handler=_handle_skill_list)

    skill_show_parser = skill_subparsers.add_parser("show", help="Show a skill.")
    skill_show_parser.add_argument("name", help="Skill name.")
    skill_show_parser.add_argument("--stage", choices=list(STAGES), help="Resolve skill for a stage.")
    skill_show_parser.set_defaults(handler=_handle_skill_show)

    skill_preferences_parser = skill_subparsers.add_parser("preferences", help="Show or reset skill preferences.")
    skill_preferences_parser.add_argument("--reset", action="store_true", help="Clear skill preferences.")
    skill_preferences_parser.set_defaults(handler=_handle_skill_preferences)

    skill_default_parser = skill_subparsers.add_parser("default", help="Set or reset a stage default skill list.")
    skill_default_parser.add_argument("stage", choices=list(STAGES), help="Stage name.")
    skill_default_parser.add_argument("skills", nargs="*", help="Default skill names.")
    skill_default_parser.add_argument("--reset", action="store_true", help="Clear default skills for the stage.")
    skill_default_parser.set_defaults(handler=_handle_skill_default)

    verify_result_parser = subparsers.add_parser(
        "verify-stage-result",
        help="Run gatekeeper verification for the submitted candidate result.",
    )
    verify_result_parser.add_argument("--session-id", required=True, help="Existing workflow session ID.")
    verify_result_parser.add_argument("--run-id", help="Optional explicit stage run to verify.")
    verify_result_parser.add_argument(
        "--judge",
        choices=["off", "noop", "openai-sandbox"],
        default="off",
        help="Optional independent judge to run after hard gates pass.",
    )
    verify_result_parser.add_argument("--model", default="gpt-5.4", help="Model for --judge openai-sandbox.")
    verify_result_parser.add_argument(
        "--docker-image",
        default="python:3.13-slim",
        help="Docker image for --judge openai-sandbox.",
    )
    verify_result_parser.add_argument(
        "--openai-api-key",
        help="Optional API key for --judge openai-sandbox. Defaults to SDK environment resolution.",
    )
    verify_result_parser.add_argument(
        "--openai-base-url",
        help="Optional base URL for --judge openai-sandbox. Defaults to SDK environment resolution.",
    )
    verify_result_parser.add_argument(
        "--openai-proxy-url",
        help="Optional HTTP proxy URL for --judge openai-sandbox, for example http://127.0.0.1:7897.",
    )
    verify_result_parser.add_argument(
        "--openai-user-agent",
        default="Agent-Team-Runtime/0.1",
        help="User-Agent for OpenAI-compatible requests. Defaults to Agent-Team-Runtime/0.1.",
    )
    verify_result_parser.add_argument(
        "--openai-oa",
        help="Optional oa header for OpenAI-compatible proxy requests. Defaults to --openai-user-agent.",
    )
    verify_result_parser.add_argument(
        "--acceptance-matrix",
        type=Path,
        help="Optional JSON file containing the approved acceptance matrix.",
    )
    verify_result_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run gate and judge without advancing workflow state.",
    )
    verify_result_parser.set_defaults(handler=_handle_verify_stage_result)

    human_decision_parser = subparsers.add_parser(
        "record-human-decision",
        help="Record a human workflow decision for a wait state.",
    )
    human_decision_parser.add_argument("--session-id", required=True, help="Existing workflow session ID.")
    human_decision_parser.add_argument("--decision", required=True, help="One of go, no-go, rework.")
    human_decision_parser.add_argument("--target-stage", help="Required for final rework decisions from SessionHandoff.")
    human_decision_parser.set_defaults(handler=_handle_record_human_decision)

    feedback_parser = subparsers.add_parser(
        "record-feedback",
        help="Record human feedback as a structured learning finding.",
    )
    feedback_parser.add_argument("--session-id", required=True, help="Existing workflow session ID.")
    feedback_parser.add_argument("--source-stage", required=True, help="Stage where the feedback originated.")
    feedback_parser.add_argument("--target-stage", required=True, help="Stage that should learn from the feedback.")
    feedback_parser.add_argument("--issue", required=True, help="Issue summary.")
    feedback_parser.add_argument("--severity", default="medium", help="Feedback severity.")
    feedback_parser.add_argument("--lesson", default="", help="Reusable lesson to store.")
    feedback_parser.add_argument("--context-update", default="", help="Context rule to store.")
    feedback_parser.add_argument("--contract-update", default="", help="Contract rule to store.")
    feedback_parser.add_argument("--evidence", default="", help="Optional evidence summary.")
    feedback_parser.add_argument("--evidence-kind", default="", help="Evidence source classification.")
    feedback_parser.add_argument(
        "--required-evidence",
        action="append",
        default=[],
        help="Evidence that must exist before the issue can be closed. Repeat to provide multiple values.",
    )
    feedback_parser.add_argument(
        "--completion-signal",
        default="",
        help="Explicit closure signal for the learning overlay.",
    )
    feedback_parser.add_argument(
        "--apply-rework",
        action="store_true",
        help="Also route the waiting workflow back to the target stage as a human rework decision.",
    )
    feedback_parser.set_defaults(handler=_handle_record_feedback)

    review_parser = subparsers.add_parser("review", help="Print the latest or a selected review.")
    review_parser.add_argument("--session-id", help="Specific session ID to inspect.")
    review_parser.set_defaults(handler=_handle_review)

    status_parser = subparsers.add_parser(
        "status",
        help="Print a user-friendly project, role, and status summary for a session.",
    )
    status_parser.add_argument("--session-id", help="Specific session ID to inspect.")
    status_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include next action, contract requirements, and stage run details.",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of the user-friendly summary.",
    )
    status_parser.set_defaults(handler=_handle_status)

    panel_parser = subparsers.add_parser(
        "panel",
        help="Start a local read-only web panel for workflow visibility.",
    )
    panel_parser.add_argument("--session-id", help="Specific session ID to inspect.")
    panel_parser.add_argument("--host", default="127.0.0.1", help="Host interface for the local panel.")
    panel_parser.add_argument("--port", type=int, default=8765, help="Port for the local panel.")
    panel_parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the local panel URL in the default browser.",
    )
    panel_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON snapshot instead of starting the web server.",
    )
    panel_parser.set_defaults(handler=_handle_panel)

    return parser


def _handle_init(args: argparse.Namespace) -> int:
    store = StateStore(args.state_root)
    store.ensure_layout()
    structure = ensure_project_structure(args.repo_root)
    five_layer = run_five_layer_classification(
        repo_root=structure.repo_root,
        project_root=structure.project_root,
        mode=args.five_layer_classification,
        interactive=sys.stdin.isatty() and sys.stdout.isatty(),
        timeout_seconds=args.five_layer_timeout_seconds,
        codex_bin=args.five_layer_codex_bin,
        skill_source=args.five_layer_skill_source,
    )
    print(f"state_root: {args.state_root}")
    print(f"repo_root: {structure.repo_root}")
    print(f"project_root: {structure.project_root}")
    print(f"doc_map_path: {structure.doc_map_path}")
    print(f"used_default_docs: {structure.used_default_docs}")
    print(f"doc_map: {json.dumps(structure.doc_map, ensure_ascii=False, sort_keys=True)}")
    print(f"five_layer_classification_status: {five_layer.status}")
    print(f"five_layer_classification_reason: {five_layer.reason}")
    print(f"five_layer_classification_report: {five_layer.report_path}")
    print(f"five_layer_classification_metadata: {five_layer.metadata_path}")
    return 0


def _handle_run_requirement(args: argparse.Namespace) -> int:
    from .runtime_driver import RuntimeDriverError, run_requirement

    interactive = _run_requirement_should_be_interactive(args)
    message, session_id = _resolve_run_requirement_target(args, interactive=interactive)
    if interactive:
        return _handle_run_requirement_interactive(args, message=message, session_id=session_id)

    try:
        result = run_requirement(
            repo_root=args.repo_root,
            state_root=args.state_root,
            message=message,
            session_id=session_id,
            options=_runtime_driver_options_from_args(args, interactive=False),
        )
    except RuntimeDriverError as exc:
        raise SystemExit(str(exc))

    _print_runtime_driver_result(result)
    return 1 if result.status in {"blocked", "failed"} else 0


def _runtime_driver_options_from_args(args: argparse.Namespace, *, interactive: bool):
    from .runtime_driver import RuntimeDriverOptions

    skill_registry = SkillRegistry(args.repo_root)
    return RuntimeDriverOptions(
        executor=args.executor,
        executor_command=args.executor_command or "",
        command_timeout_seconds=args.command_timeout_seconds,
        auto_advance_intermediate=args.auto and not interactive,
        max_stage_runs=args.max_stage_runs,
        judge=args.judge,
        model=args.model,
        docker_image=args.docker_image,
        openai_api_key=args.openai_api_key,
        openai_base_url=args.openai_base_url,
        openai_proxy_url=args.openai_proxy_url,
        openai_user_agent=args.openai_user_agent,
        openai_oa=args.openai_oa,
        codex_model=args.codex_model,
        codex_sandbox=args.codex_sandbox,
        codex_approval_policy=args.codex_approval_policy,
        codex_extra_args=list(args.codex_extra_arg),
        enabled_skills_by_stage=_resolve_run_enabled_skills(args, skill_registry),
        interactive=interactive,
        trace_prompts=bool(args.trace_prompts),
    )


def _print_runtime_driver_result(result) -> None:
    print(f"session_id: {result.session_id}")
    print(f"artifact_dir: {result.artifact_dir}")
    print(f"summary_path: {result.summary_path}")
    print(f"runtime_driver_status: {result.status}")
    print(f"current_state: {result.current_state}")
    print(f"current_stage: {result.current_stage}")
    print(f"acceptance_status: {result.acceptance_status}")
    print(f"human_decision: {result.human_decision}")
    print(f"stage_run_count: {result.stage_run_count}")
    if result.gate_status:
        print(f"gate_status: {result.gate_status}")
    if result.gate_reason:
        print(f"gate_reason: {result.gate_reason}")
    if result.next_action:
        print(f"next_action: {result.next_action}")


def _run_requirement_should_be_interactive(args: argparse.Namespace) -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _resolve_run_requirement_target(args: argparse.Namespace, *, interactive: bool) -> tuple[str, str]:
    if args.message and args.session_id:
        raise SystemExit("Provide either --message or --session-id, not both.")
    if args.message:
        return args.message, args.session_id or ""
    if args.session_id:
        return "", args.session_id
    if interactive:
        message = input("请输入需求：").strip()
        if not message:
            raise SystemExit("需求不能为空。")
        return message, ""
    raise SystemExit("run requires --message or --session-id when stdin/stdout are not interactive.")


def _handle_run_requirement_interactive(args: argparse.Namespace, *, message: str, session_id: str) -> int:
    from .runtime_driver import RuntimeDriverError, run_requirement

    store = StateStore(args.state_root)
    current_message = message
    current_session_id = session_id
    header_printed = False

    while True:
        running_stage = "Route"
        running_completed = 0
        animate_stage_run = False
        activity_provider = None
        if current_session_id:
            summary_before = store.load_workflow_summary(current_session_id)
            running_stage = _run_requirement_stage_for_summary(summary_before)
            running_completed = _run_requirement_completed_stage_count(summary_before)
            if summary_before.current_state not in RUN_REQUIREMENT_WAIT_TO_STAGE and summary_before.current_state not in {
                "Blocked",
                "Done",
            }:
                _print_run_requirement_stage_banner(stage=running_stage, completed=running_completed)
                animate_stage_run = True
                activity_provider = _runtime_trace_activity_provider(
                    store=store,
                    session_id=current_session_id,
                    stage=_runtime_stage_for_run_requirement_stage(running_stage),
                )
        else:
            _print_run_requirement_stage_banner(stage=running_stage, completed=running_completed)
            animate_stage_run = True

        try:
            def run_stage():
                return run_requirement(
                    repo_root=args.repo_root,
                    state_root=args.state_root,
                    message=current_message,
                    session_id=current_session_id,
                    options=_runtime_driver_options_from_args(args, interactive=True),
                )

            if animate_stage_run:
                result = _run_requirement_with_stage_animation(
                    stage=running_stage,
                    completed=running_completed,
                    activity_provider=activity_provider,
                    run=run_stage,
                )
            else:
                result = run_stage()
        except RuntimeDriverError as exc:
            raise SystemExit(str(exc))

        if not header_printed:
            print(f"session_id: {result.session_id}")
            print(f"artifact_dir: {result.artifact_dir}")
            print(f"summary_path: {result.summary_path}")
            print("")
            header_printed = True

        summary = store.load_workflow_summary(result.session_id)
        stage = _run_requirement_stage_for_summary(summary)
        completed = _run_requirement_completed_stage_count(summary)
        _print_run_requirement_stage_report(
            store=store,
            session_id=result.session_id,
            stage=stage,
            completed=completed,
            summary=summary,
            model_output=args.model_output,
            result=result,
            auto_approving=_run_requirement_should_auto_approve_stage(args, stage),
        )

        if result.status in {"blocked", "failed"}:
            blocked_decision = _prompt_run_requirement_blocked_decision(
                store=store,
                summary=summary,
                stage=stage,
                result=result,
                args=args,
            )
            if blocked_decision == "quit":
                print("Session saved.")
                print(_run_requirement_resume_command(args, result.session_id))
                return 0
            _clear_run_requirement_blocker(store=store, summary=summary, stage=stage)
            current_session_id = result.session_id
            current_message = ""
            continue
        if result.status == "done" or summary.current_state == "Done":
            print("Session completed.")
            return 0
        if result.status != "waiting_human":
            return 0

        if _run_requirement_should_auto_approve_stage(args, stage):
            updated_summary = _apply_run_requirement_decision(
                store=store,
                summary=summary,
                decision="go",
                target_stage=None,
                issue="",
            )
            next_stage = (
                "完成交付"
                if updated_summary.current_state == "Done"
                else _run_requirement_stage_for_summary(updated_summary)
            )
            print(
                f"--auto: 已自动通过 {_run_requirement_stage_label(stage)}，"
                f"进入 {_run_requirement_stage_label(next_stage)}。"
            )
            current_session_id = result.session_id
            current_message = ""
            if updated_summary.current_state == "Done":
                print("Session completed.")
                return 0
            continue

        decision = _prompt_run_requirement_decision(
            store=store,
            summary=summary,
            stage=stage,
            model_output=args.model_output,
        )
        if decision["action"] == "quit":
            print("Session saved.")
            print(_run_requirement_resume_command(args, result.session_id))
            return 0

        updated_summary = _apply_run_requirement_decision(
            store=store,
            summary=summary,
            decision=decision["decision"],
            target_stage=decision.get("target_stage"),
            issue=decision.get("issue", ""),
        )
        current_session_id = result.session_id
        current_message = ""

        if updated_summary.current_state == "Done":
            print("Session completed.")
            return 0


def _run_requirement_should_auto_approve_stage(args: argparse.Namespace, stage: str) -> bool:
    return bool(args.auto) and stage not in {"ProductDefinition", "TechnicalDesign", "SessionHandoff"}


def _print_run_requirement_stage_banner(*, stage: str, completed: int) -> None:
    total = len(RUN_REQUIREMENT_STAGE_ORDER)
    print(f"[{completed + 1}/{total} {_run_requirement_stage_label(stage)}] {RUN_REQUIREMENT_STAGE_TITLES.get(stage, stage)}...")
    if not _run_requirement_stage_animation_enabled():
        print(f"进度: {_render_progress_bar(completed, total)}")


def _run_requirement_stage_animation_enabled() -> bool:
    return sys.stdout.isatty()


def _run_requirement_with_stage_animation(*, stage: str, completed: int, run, activity_provider=None):
    if not _run_requirement_stage_animation_enabled():
        return run()

    stop_event = threading.Event()
    started_event = threading.Event()

    def animate() -> None:
        phase = 0
        while not stop_event.is_set():
            activity = _read_stage_activity(activity_provider)
            line = _render_running_progress_line(
                stage=stage,
                completed=completed,
                phase=phase,
                activity=activity,
            )
            sys.stdout.write("\r" + line)
            sys.stdout.flush()
            started_event.set()
            phase += 1
            stop_event.wait(0.12)

    thread = threading.Thread(target=animate, daemon=True)
    thread.start()
    started_event.wait(0.15)
    try:
        return run()
    finally:
        stop_event.set()
        thread.join(timeout=0.5)
        sys.stdout.write("\r" + _terminal_clear_line() + "\n")
        sys.stdout.flush()


def _read_stage_activity(activity_provider) -> str:
    if activity_provider is None:
        return ""
    try:
        return str(activity_provider() or "")
    except (OSError, ValueError, json.JSONDecodeError):
        return ""


def _render_running_progress_line(*, stage: str, completed: int, phase: int, activity: str = "") -> str:
    total = len(RUN_REQUIREMENT_STAGE_ORDER)
    current_activity = activity or _run_requirement_stage_activity(stage=stage, phase=phase)
    return (
        f"{_render_stage_spinner(phase)} {_render_flow_progress_bar(completed, total, phase=phase)} "
        f"{_run_requirement_stage_label(stage)} · {current_activity}"
    )


def _render_stage_spinner(phase: int) -> str:
    return RUN_REQUIREMENT_SPINNER_FRAMES[phase % len(RUN_REQUIREMENT_SPINNER_FRAMES)]


def _run_requirement_stage_activity(*, stage: str, phase: int) -> str:
    steps = RUN_REQUIREMENT_STAGE_ACTIVITY_STEPS.get(stage) or ("推进当前阶段",)
    return steps[phase % len(steps)]


def _runtime_trace_activity_provider(*, store: StateStore, session_id: str, stage: str):
    def read_activity() -> str:
        run = store.latest_stage_run(session_id, stage=stage)
        if run is None:
            return ""
        steps = [item for item in run.steps if item.get("status") in {"ok", "blocked", "failed"}]
        if not steps:
            session = store.load_session(session_id)
            return ""
        if not steps:
            return ""
        step = str(steps[-1].get("step", ""))
        return RUN_REQUIREMENT_TRACE_STEP_LABELS.get(step, step.replace("_", " "))

    return read_activity


def _runtime_stage_for_run_requirement_stage(stage: str) -> str:
    return stage


def _render_flow_progress_bar(completed: int, total: int, *, phase: int, width: int = 10) -> str:
    total = max(total, 1)
    completed = max(0, min(completed, total))
    filled = int(width * completed / total)
    cells = [" "] * width
    for index in range(filled):
        cells[index] = "="
    cursor_span = max(1, width - filled)
    cursor_index = min(width - 1, filled + (phase % cursor_span))
    cells[cursor_index] = ">"
    return f"[{''.join(cells)}] {completed}/{total}"


def _terminal_clear_line() -> str:
    return "\033[2K"


def _print_run_requirement_stage_report(
    *,
    store: StateStore,
    session_id: str,
    stage: str,
    completed: int,
    summary: WorkflowSummary,
    model_output: str,
    result,
    auto_approving: bool = False,
) -> None:
    session = store.load_session(session_id)
    label, artifact_key, filename = RUN_REQUIREMENT_STAGE_DOCS.get(stage, (stage, stage.lower(), f"{stage.lower()}.md"))
    doc_path = summary.artifact_paths.get(artifact_key) or str(session.artifact_dir / filename)
    print(
        f"[{completed}/{len(RUN_REQUIREMENT_STAGE_ORDER)} {_run_requirement_stage_label(stage)}] "
        f"{RUN_REQUIREMENT_STAGE_TITLES.get(stage, stage)}"
    )
    print(f"进度: {_render_progress_bar(completed, len(RUN_REQUIREMENT_STAGE_ORDER))}")
    if model_output != "off":
        for line in _run_requirement_stage_summary_lines(stage, summary, auto_approving=auto_approving):
            print(f"- {line}")
    print("文档:")
    print(f"- {label}: {doc_path}")
    if model_output == "raw":
        print("调试信息:")
        _print_runtime_driver_result(result)
        _print_run_requirement_raw_streams(store=store, session_id=session_id, stage=stage)
    if result.gate_reason and model_output != "raw":
        print(f"gate_reason: {result.gate_reason}")
    print("下一步:")
    if result.status == "done":
        print("流程已完成。")
    elif result.status in {"blocked", "failed"}:
        print("请检查 gate_reason、stage_run trace 和阶段产物后修复。")
    elif auto_approving:
        print(_run_requirement_auto_next_step_text(stage))
    else:
        print(_run_requirement_next_step_text(stage))
    print("")


def _run_requirement_stage_summary_lines(
    stage: str,
    summary: WorkflowSummary,
    *,
    auto_approving: bool = False,
) -> list[str]:
    del summary
    if stage == "Route":
        return [
            "已完成需求路由和五层影响判断",
            "已记录红线和需要执行的阶段",
            "已写入 route-packet.json",
        ]
    if stage == "ProductDefinition":
        return [
            "已识别 L1 产品定义候选",
            "已把非 L1 内容下沉到对应层",
            "已写入 product-definition-delta.md",
        ]
    if stage == "ProjectRuntime":
        return [
            "已整理 L3 项目落地默认做法",
            "已检查未重写 L1 或伪装成 L4",
            "已写入 project-landing-delta.md",
        ]
    if stage == "TechnicalDesign":
        return [
            "已确认 L1/L3 delta 作为技术设计输入",
            "已拆分实现步骤和验证方式",
            "已写入 technical-design.md",
        ]
    if stage == "Implementation":
        return [
            "已根据技术方案完成实现",
            "已记录自检和改动文件",
            "已写入 implementation.md",
        ]
    if stage == "Verification":
        return [
            "已独立验证实现结果",
            "已记录验证结论和发现",
            "已写入 verification-report.md",
        ]
    if stage == "GovernanceReview":
        return [
            "已检查五层边界和红线",
            "已记录证据质量和回写义务",
            "已写入 governance-review.md",
        ]
    if stage == "Acceptance":
        return [
            "已按产品结果和治理证据汇总结论",
            "已写入 acceptance-report.md",
        ]
    if stage == "SessionHandoff":
        return [
            "已保留 L5 本地现场和下一步",
            "已写入 session-handoff.md",
            "等待最终人工决策",
        ]
    return [
        "已推进到当前阶段",
    ]


def _run_requirement_next_step_text(stage: str) -> str:
    if stage == "ProductDefinition":
        return "请打开 L1 delta 文档确认哪些进入产品定义，哪些不是 L1。"
    if stage == "TechnicalDesign":
        return "请打开技术设计文档确认实现路径和验证方式是否通过。"
    if stage == "SessionHandoff":
        return "请打开接力文档并确认最终决策。"
    if stage == "Acceptance":
        return "请打开验收报告确认 AI 最终建议。"
    return "请确认当前阶段是否通过。"


def _run_requirement_auto_next_step_text(stage: str) -> str:
    try:
        index = RUN_REQUIREMENT_STAGE_ORDER.index(stage)
        next_stage = RUN_REQUIREMENT_STAGE_ORDER[index + 1]
    except (ValueError, IndexError):
        next_stage = "下一阶段"
    return f"--auto 已启用，将自动通过 {_run_requirement_stage_label(stage)} 并进入 {_run_requirement_stage_label(next_stage)}。"


def _run_requirement_stage_label(stage: str) -> str:
    return RUN_REQUIREMENT_STAGE_LABELS.get(stage, stage)


def _prompt_run_requirement_blocked_decision(
    *,
    store: StateStore,
    summary: WorkflowSummary,
    stage: str,
    result,
    args: argparse.Namespace,
) -> str:
    choices = [
        RunRequirementMenuChoice("r", "重新执行当前阶段", "retry"),
        RunRequirementMenuChoice("p", "打印诊断文件路径", "print"),
        RunRequirementMenuChoice("q", "保存并退出", "quit"),
    ]
    while True:
        print("当前阶段执行被阻塞。")
        _print_run_requirement_menu(choices)
        choice = _read_run_requirement_menu_choice(choices)
        if choice.action == "retry":
            return "retry"
        if choice.action == "print":
            _print_run_requirement_diagnostics(store=store, session_id=result.session_id, stage=stage, args=args)
            continue
        if choice.action == "quit":
            return "quit"


def _clear_run_requirement_blocker(*, store: StateStore, summary: WorkflowSummary, stage: str) -> None:
    session = store.load_session(summary.session_id)
    current_state = summary.current_state
    current_stage = summary.current_stage
    runtime_stage = _runtime_stage_for_run_requirement_stage(stage)
    if current_state == "Blocked":
        current_state = runtime_stage if runtime_stage in WORKFLOW_STAGES else "Route"
        current_stage = current_state
    store.save_workflow_summary(
        session,
        replace(
            summary,
            current_state=current_state,
            current_stage=current_stage,
            blocked_reason="",
        ),
    )
    store.record_event(
        summary.session_id,
        kind="workflow_blocker_cleared",
        stage=current_stage,
        state=current_state,
        actor="human",
        status="retry",
        message="Interactive operator chose to retry the blocked stage.",
    )


def _print_run_requirement_diagnostics(
    *,
    store: StateStore,
    session_id: str,
    stage: str,
    args: argparse.Namespace,
) -> None:
    session = store.load_session(session_id)
    run = store.latest_stage_run(session_id, stage=_runtime_stage_for_run_requirement_stage(stage))
    print("诊断信息:")
    print(f"- executor: {args.executor}")
    print(f"- artifact_dir: {session.artifact_dir}")
    print(f"- workflow_summary: {store.workflow_summary_path(session_id)}")
    if run is None:
        return
    print(f"- run_id: {run.run_id}")
    print(f"- run_status: {run.state}")
    if run.blocked_reason:
        print(f"- blocked_reason: {run.blocked_reason}")
    context_path = store.latest_execution_context_path(session_id, stage)
    if context_path is not None:
        print(f"- context: {context_path}")
    legacy_stage_runs_dir = session.session_dir / "stage_runs"
    for label, path in (
        ("contract", store.stage_contract_path(session, run.stage, run.attempt)),
        ("stage_result", store.stage_result_path(session, run.stage, run.attempt)),
        ("prompt", store.stage_prompt_bundle_path(session, run.stage, run.attempt)),
        ("stdout", store.command_stdout_path(session, run.stage, run.attempt)),
        ("stderr", store.command_stderr_path(session, run.stage, run.attempt)),
        ("legacy_contract", legacy_stage_runs_dir / f"{run.run_id}_contract.json"),
        ("legacy_result", legacy_stage_runs_dir / f"{run.run_id}_result.json"),
        ("legacy_candidate", legacy_stage_runs_dir / f"{run.run_id}_candidate.json"),
        ("legacy_stdout", legacy_stage_runs_dir / f"{run.run_id}_stdout.txt"),
        ("legacy_stderr", legacy_stage_runs_dir / f"{run.run_id}_stderr.txt"),
        ("legacy_trace", legacy_stage_runs_dir / f"{run.run_id}_trace.json"),
    ):
        if path.exists():
            print(f"- {label}: {path}")


def _print_run_requirement_raw_streams(*, store: StateStore, session_id: str, stage: str) -> None:
    run = store.latest_stage_run(session_id, stage=_runtime_stage_for_run_requirement_stage(stage))
    if run is None:
        return
    session = store.load_session(session_id)
    stage_result_path = store.stage_result_path(session, run.stage, run.attempt)
    if stage_result_path.exists():
        print(f"stage_result: {stage_result_path}")
    stream_paths = {
        "stdout": store.command_stdout_path(session, run.stage, run.attempt),
        "stderr": store.command_stderr_path(session, run.stage, run.attempt),
    }
    legacy_stage_runs_dir = session.session_dir / "stage_runs"
    for stream_name, stream_path in stream_paths.items():
        if not stream_path.exists():
            stream_path = legacy_stage_runs_dir / f"{run.run_id}_{stream_name}.txt"
        if not stream_path.exists():
            continue
        print(f"{stream_name}_path: {stream_path}")
        content = stream_path.read_text()
        if content.strip():
            print(f"{stream_name}:")
            print(_truncate_terminal_text(content, limit=4000))


def _truncate_terminal_text(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value.rstrip()
    return value[:limit].rstrip() + "\n...<truncated>"


def _prompt_run_requirement_decision(
    *,
    store: StateStore,
    summary: WorkflowSummary,
    stage: str,
    model_output: str,
) -> dict[str, str]:
    del model_output
    choices = _run_requirement_decision_choices(stage)
    print("请选择下一步：")
    _print_run_requirement_menu(choices)
    while True:
        choice = _read_run_requirement_menu_choice(choices)
        if choice.action == "print":
            _print_run_requirement_document_link(store=store, summary=summary, stage=stage)
            continue
        if choice.action == "quit":
            return {"action": "quit"}
        if choice.requires_issue:
            issue = input("修改意见：").strip()
            if stage == "SessionHandoff" and choice.decision == "rework":
                target_stage = _prompt_session_handoff_rework_target()
                return {
                    "action": "apply",
                    "decision": choice.decision,
                    "target_stage": target_stage,
                    "issue": issue or "用户要求返工。",
                }
            return {
                "action": "apply",
                "decision": choice.decision,
                "target_stage": choice.target_stage,
                "issue": issue or "用户要求返工。",
            }
        if choice.action == "apply":
            return {"action": "apply", "decision": choice.decision, "target_stage": choice.target_stage}


def _prompt_session_handoff_rework_target() -> str:
    target_labels = {
        "Route": ("r", "Route 重新判断五层路由", ("route",)),
        "ProductDefinition": ("p", "ProductDefinition 重新澄清 L1 delta", ("productdefinition", "product-definition", "product")),
        "ProjectRuntime": ("l", "ProjectRuntime 重新整理 L3 落地默认", ("projectruntime", "project-runtime", "runtime")),
        "TechnicalDesign": ("t", "TechnicalDesign 重新生成技术设计", ("technicaldesign", "technical-design", "design")),
        "Implementation": ("i", "Implementation 根据意见返工实现", ("implementation", "impl")),
        "Verification": ("v", "Verification 重新独立验证", ("verification", "verify")),
        "GovernanceReview": ("g", "GovernanceReview 重新检查治理红线", ("governancereview", "governance-review", "governance")),
    }
    choices = [
        RunRequirementMenuChoice(key, label, "target", target_stage=stage, aliases=aliases)
        for stage, (key, label, aliases) in target_labels.items()
        if stage in HUMAN_REWORK_TARGETS
    ]
    while True:
        print("返工目标：")
        _print_run_requirement_menu(choices)
        choice = _read_run_requirement_menu_choice(choices)
        if choice.target_stage:
            return choice.target_stage


def _run_requirement_decision_choices(stage: str) -> list[RunRequirementMenuChoice]:
    labels = {
        "ProductDefinition": {
            "go": "通过 L1 产品定义 delta，进入 L3 项目落地",
            "no_go": "不通过 L1 产品定义 delta，结束为 no-go",
            "rework": "提交修改意见，重新生成 L1 产品定义 delta",
            "print": "重新打印 L1 delta 文档路径",
        },
        "TechnicalDesign": {
            "go": "通过技术设计，进入 Implementation",
            "no_go": "不通过技术设计，结束为 no-go",
            "rework": "提交修改意见，重新生成技术设计",
            "print": "重新打印技术设计文档路径",
        },
        "SessionHandoff": {
            "go": "通过最终交付，完成本次任务",
            "no_go": "不通过最终交付，结束为 no-go",
            "rework": "提交修改意见，选择返工目标",
            "print": "重新打印 L5 接力文档路径",
        },
    }.get(
        stage,
        {
            "go": "通过，进入下一阶段",
            "rework": "提交修改意见，重新生成当前阶段",
            "print": "重新打印文档路径",
        },
    )
    choices = [
        RunRequirementMenuChoice("y", labels["go"], "apply", decision="go", aliases=("yes",)),
    ]
    if "no_go" in labels:
        choices.append(
            RunRequirementMenuChoice("n", labels["no_go"], "apply", decision="no-go", aliases=("no",))
        )
    choices.extend(
        [
            RunRequirementMenuChoice(
                "e",
                labels["rework"],
                "apply",
                decision="rework",
                target_stage=_run_requirement_rework_target(stage),
                requires_issue=True,
                aliases=("edit",),
            ),
            RunRequirementMenuChoice("p", labels["print"], "print", aliases=("print",)),
            RunRequirementMenuChoice("q", "保存并退出", "quit", aliases=("quit",)),
        ]
    )
    return choices


def _print_run_requirement_menu(choices: list[RunRequirementMenuChoice]) -> None:
    for choice in choices:
        print(f"  {choice.key}) {choice.label}")


def _read_run_requirement_menu_choice(choices: list[RunRequirementMenuChoice]) -> RunRequirementMenuChoice:
    by_key: dict[str, RunRequirementMenuChoice] = {}
    for choice in choices:
        by_key[choice.key] = choice
        for alias in choice.aliases:
            by_key[alias] = choice
    allowed = " / ".join(choice.key for choice in choices)
    while True:
        raw = input("> ").strip().lower()
        if raw in by_key:
            return by_key[raw]
        print(f"请输入 {allowed}。")


def _run_requirement_rework_target(stage: str) -> str:
    return "" if stage == "SessionHandoff" else stage


def _print_run_requirement_document_link(*, store: StateStore, summary: WorkflowSummary, stage: str) -> None:
    session = store.load_session(summary.session_id)
    label, artifact_key, filename = RUN_REQUIREMENT_STAGE_DOCS.get(stage, (stage, stage.lower(), f"{stage.lower()}.md"))
    doc_path = summary.artifact_paths.get(artifact_key) or str(session.artifact_dir / filename)
    print("文档:")
    print(f"- {label}: {doc_path}")


def _apply_run_requirement_decision(
    *,
    store: StateStore,
    summary: WorkflowSummary,
    decision: str,
    target_stage: str | None,
    issue: str,
) -> WorkflowSummary:
    session = store.load_session(summary.session_id)
    if issue:
        source_stage = _run_requirement_stage_for_summary(summary)
        finding = Finding(
            source_stage=source_stage,
            target_stage=target_stage or source_stage,
            issue=issue,
            severity="medium",
        )
        store.record_feedback(summary.session_id, finding)
    updated_summary = StageMachine().apply_human_decision(
        summary=summary,
        decision=decision,
        target_stage=target_stage,
    )
    store.save_workflow_summary(session, updated_summary)
    store.set_human_decision(summary.session_id, updated_summary.human_decision)
    store.record_event(
        summary.session_id,
        kind="workflow_state_changed",
        stage=updated_summary.current_stage,
        state=updated_summary.current_state,
        actor="human",
        status=updated_summary.human_decision,
        message=(
            f"Workflow moved to {updated_summary.current_stage} / "
            f"{updated_summary.current_state} after interactive decision."
        ),
    )
    return updated_summary


def _run_requirement_resume_command(args: argparse.Namespace, session_id: str) -> str:
    return (
        "Resume:\n"
        f"agent-team --repo-root {shlex.quote(str(args.repo_root))} "
        f"--state-root {shlex.quote(str(args.state_root))} "
        f"run --session-id {shlex.quote(session_id)}"
    )


def _run_requirement_stage_for_summary(summary: WorkflowSummary) -> str:
    if summary.current_state in RUN_REQUIREMENT_WAIT_TO_STAGE:
        return RUN_REQUIREMENT_WAIT_TO_STAGE[summary.current_state]
    if summary.current_state in RUN_REQUIREMENT_STAGE_ORDER:
        return summary.current_state
    if summary.current_state == "Intake":
        return "Route"
    if summary.current_stage in RUN_REQUIREMENT_STAGE_ORDER:
        return summary.current_stage
    return "Route"


def _run_requirement_completed_stage_count(summary: WorkflowSummary) -> int:
    if summary.current_state == "Intake":
        return 0
    if summary.current_state in {"WaitForHumanDecision", "Done"}:
        return len(RUN_REQUIREMENT_STAGE_ORDER)
    if summary.current_state in RUN_REQUIREMENT_WAIT_TO_STAGE:
        stage = RUN_REQUIREMENT_WAIT_TO_STAGE[summary.current_state]
        return RUN_REQUIREMENT_STAGE_ORDER.index(stage) + 1
    if summary.current_state in RUN_REQUIREMENT_STAGE_ORDER:
        return RUN_REQUIREMENT_STAGE_ORDER.index(summary.current_state)
    if summary.current_state == "Blocked" and summary.current_stage in RUN_REQUIREMENT_STAGE_ORDER:
        return RUN_REQUIREMENT_STAGE_ORDER.index(summary.current_stage)
    return 0


def _render_progress_bar(completed: int, total: int, width: int = 10) -> str:
    total = max(total, 1)
    completed = max(0, min(completed, total))
    filled = int(width * completed / total)
    return f"[{'#' * filled}{'-' * (width - filled)}] {completed}/{total}"


def _resolve_run_enabled_skills(args: argparse.Namespace, registry: SkillRegistry):
    if args.skills_empty:
        return {}

    preferences = registry.load_preferences()
    selected = {stage: preferences.selected_for(stage) for stage in STAGES}
    for stage, names in _parse_stage_skill_specs(args.with_skills).items():
        selected[stage] = names
    for stage, names in _parse_stage_skill_specs(args.skip_skills).items():
        selected[stage] = [name for name in selected.get(stage, []) if name not in set(names)]
    _validate_selected_skill_names(selected, registry)
    return registry.resolve_enabled(selected)


def _parse_stage_skill_specs(specs: list[str]) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for spec in specs:
        if ":" not in spec:
            raise SystemExit(f"Skill spec must be stage:name[,name]: {spec}")
        stage_raw, names_raw = spec.split(":", 1)
        stage = _normalize_stage_name(stage_raw)
        names = [name.strip() for name in names_raw.split(",") if name.strip()]
        parsed.setdefault(stage, []).extend(names)
    return parsed


def _validate_selected_skill_names(selected: dict[str, list[str]], registry: SkillRegistry) -> None:
    for stage, names in selected.items():
        if not names:
            continue
        available = {skill.name for skill in registry.list_skills(stage=stage)}
        missing = [name for name in names if name not in available]
        if missing:
            raise SystemExit(f"Unknown skill(s) for {stage}: {', '.join(missing)}")


def _normalize_stage_name(stage: str) -> str:
    for known in STAGES:
        if known.lower() == stage.lower():
            return known
    raise SystemExit(f"Unknown skill stage: {stage}")


def _handle_skill_list(args: argparse.Namespace) -> int:
    registry = SkillRegistry(args.repo_root)
    for skill in registry.list_skills(stage=args.stage, source=args.source):
        stages = ",".join(skill.stages)
        source_ref = skill.source_ref or str(skill.path.parent.resolve())
        print(f"{skill.name}\t{SOURCE_LABELS[skill.source]}\t{source_ref}\t{stages}\t{skill.description}")
    return 0


def _handle_skill_show(args: argparse.Namespace) -> int:
    registry = SkillRegistry(args.repo_root)
    skill = registry.get_skill(args.name, stage=args.stage)
    if skill is None:
        raise SystemExit(f"Skill not found: {args.name}")
    print(f"name: {skill.name}")
    print(f"source: {SOURCE_LABELS[skill.source]}")
    print(f"source_ref: {skill.source_ref or skill.path.parent.resolve()}")
    print(f"stages: {', '.join(skill.stages)}")
    print(f"path: {skill.path}")
    print("")
    print(skill.content)
    return 0


def _handle_skill_preferences(args: argparse.Namespace) -> int:
    registry = SkillRegistry(args.repo_root)
    if args.reset:
        registry.reset_preferences()
    assert registry.preference_path is not None
    print(registry.preference_path.read_text() if registry.preference_path.exists() else "")
    return 0


def _handle_skill_default(args: argparse.Namespace) -> int:
    registry = SkillRegistry(args.repo_root)
    if args.reset:
        registry.clear_default(args.stage)
    else:
        registry.set_default(args.stage, args.skills)
    assert registry.preference_path is not None
    print(registry.preference_path.read_text())
    return 0


def _handle_verify_stage_result(args: argparse.Namespace) -> int:
    store = StateStore(args.state_root)
    summary = store.load_workflow_summary(args.session_id)

    if args.run_id:
        run = store.load_stage_run(args.run_id)
    else:
        expected_stage = _expected_submission_stage(summary)
        if expected_stage is None:
            raise SystemExit(f"Cannot verify a stage result while workflow is waiting in {summary.current_state}.")
        run = store.active_stage_run(args.session_id, stage=expected_stage)
        if run is None:
            raise SystemExit(f"No active stage run for {expected_stage}.")

    if run.session_id != args.session_id:
        raise SystemExit("Stage run session_id does not match --session-id.")
    if not run.stage_result and not run.candidate_bundle_path:
        raise SystemExit(f"Stage run {run.run_id} has no submitted candidate result.")

    result = store.load_stage_run_result(run)
    contract = build_stage_contract(
        repo_root=args.repo_root,
        state_store=store,
        session_id=args.session_id,
        stage=run.stage,
    )

    if args.dry_run:
        if run.state not in {"SUBMITTED", "VERIFYING", "PASSED"}:
            raise SystemExit(f"Stage run {run.run_id} is {run.state}; expected SUBMITTED, VERIFYING, or PASSED.")
        gate_result, _normalized_result, judge_payload = _evaluate_stage_result_for_verification(
            args=args,
            store=store,
            summary=summary,
            contract=contract,
            result=result,
        )
        payload = {
            "session_id": args.session_id,
            "run_id": run.run_id,
            "stage": run.stage,
            "judge": args.judge,
            "gate_status": gate_result.status,
            "gate_reason": gate_result.reason,
            "missing_outputs": list(gate_result.missing_outputs),
            "missing_evidence": list(gate_result.missing_evidence),
            "findings": [f.to_dict() for f in gate_result.findings],
        }
        if judge_payload is not None:
            payload.update(judge_payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if gate_result.status == "PASSED" else 1

    if run.state != "SUBMITTED":
        raise SystemExit(f"Stage run {run.run_id} is {run.state}; expected SUBMITTED.")

    verifying_run = store.update_stage_run(run, state="VERIFYING")
    try:
        gate_result, normalized_result, judge_payload = _evaluate_stage_result_for_verification(
            args=args,
            store=store,
            summary=summary,
            contract=contract,
            result=result,
        )
    except SystemExit:
        store.update_stage_run(verifying_run, state="SUBMITTED")
        raise

    if gate_result.status == "PASSED":
        stage_record = store.record_stage_result(args.session_id, normalized_result)
        session = store.load_session(args.session_id)
        updated_summary = StageMachine().advance(summary=summary, stage_result=normalized_result)
        artifact_key = _artifact_key_for_stage_result(normalized_result)
        updated_summary.artifact_paths[artifact_key] = str(stage_record.artifact_path)
        updated_summary.artifact_paths.update(stage_record.supplemental_artifact_paths)
        store.save_workflow_summary(session, updated_summary)
        store.update_stage_run(
            verifying_run,
            state="PASSED",
            gate_result=gate_result,
            blocked_reason="",
            artifact_paths={
                artifact_key: str(stage_record.artifact_path),
                **stage_record.supplemental_artifact_paths,
            },
        )
        for finding in normalized_result.findings:
            store.apply_learning(finding)
        print(f"run_id: {verifying_run.run_id}")
        print(f"gate_status: {gate_result.status}")
        _print_judge_payload(judge_payload)
        _print_summary(updated_summary)
        return 0

    session = store.load_session(args.session_id)
    updated_summary = replace(summary, blocked_reason=gate_result.reason if gate_result.status == "BLOCKED" else "")
    store.save_workflow_summary(session, updated_summary)
    store.update_stage_run(
        verifying_run,
        state=gate_result.status,
        gate_result=gate_result,
        blocked_reason=gate_result.reason if gate_result.status == "BLOCKED" else "",
    )
    print(f"run_id: {verifying_run.run_id}")
    print(f"gate_status: {gate_result.status}")
    _print_judge_payload(judge_payload)
    if gate_result.reason:
        print(f"gate_reason: {gate_result.reason}")
    _print_summary(updated_summary)
    return 1


def _evaluate_stage_result_for_verification(
    *,
    args: argparse.Namespace,
    store: StateStore,
    summary: WorkflowSummary,
    contract,
    result: StageResultEnvelope,
):
    if args.judge == "off":
        gate_result, normalized_result = evaluate_candidate(
            session=store.load_session(args.session_id),
            contract=contract,
            result=result,
            acceptance_contract=store.load_acceptance_contract(args.session_id),
        )
        return gate_result, normalized_result, None

    from .gate_evaluator import GateEvaluator, NoopJudge
    from .openai_sandbox_judge import OpenAISandboxJudge, OpenAISandboxJudgeUnavailable
    from .stage_policies import default_policy_registry

    judge = (
        OpenAISandboxJudge(
            model=args.model,
            docker_image=args.docker_image,
            api_key=args.openai_api_key,
            base_url=args.openai_base_url,
            proxy_url=args.openai_proxy_url,
            user_agent=args.openai_user_agent,
            oa_header=_resolve_openai_oa_header(args),
        )
        if args.judge == "openai-sandbox"
        else NoopJudge()
    )
    session = store.load_session(args.session_id)
    try:
        evaluation = GateEvaluator(judge=judge).evaluate(
            session=session,
            policy=_policy_for_stage_result(result, default_policy_registry()),
            contract=contract,
            result=result,
            original_request_summary=session.request,
            approved_product_definition_summary=_approved_product_definition_summary(summary=summary, result=result),
            approved_acceptance_matrix=_load_acceptance_matrix(args.acceptance_matrix),
        )
    except OpenAISandboxJudgeUnavailable as exc:
        raise SystemExit(str(exc))

    return (
        _gate_result_from_evaluation(evaluation),
        evaluation.result,
        {
            "decision": _gate_decision_to_dict(evaluation.decision),
            "judge_result": _judge_result_to_dict(evaluation.judge_result),
        },
    )


def _gate_result_from_evaluation(evaluation) -> GateResult:
    decision = evaluation.decision
    if decision.outcome == "pass":
        status = "PASSED"
    elif decision.outcome == "blocked":
        status = "BLOCKED"
    else:
        status = "FAILED"
    return GateResult(
        status=status,
        reason=decision.reason,
        missing_outputs=list(decision.missing_outputs),
        missing_evidence=list(decision.missing_evidence),
        findings=list(decision.findings),
        checked_at=evaluation.hard_gate_result.checked_at,
    )


def _print_judge_payload(payload: dict[str, object] | None) -> None:
    if payload is None:
        return
    decision = payload["decision"]
    judge_result = payload["judge_result"]
    if isinstance(decision, dict):
        print(f"decision_outcome: {decision['outcome']}")
    if isinstance(judge_result, dict):
        print(f"judge_verdict: {judge_result['verdict']}")
        print(f"judge_confidence: {judge_result['confidence']}")


def _resolve_openai_oa_header(args: argparse.Namespace) -> str:
    return args.openai_oa or args.openai_user_agent


def _handle_record_human_decision(args: argparse.Namespace) -> int:
    store = StateStore(args.state_root)
    session = store.load_session(args.session_id)
    if session.initiator == "agent":
        raise SystemExit(
            "Human decisions are reserved for human-initiated sessions. "
            "Agent sessions must wait for a human operator to intervene."
        )
    summary = store.load_workflow_summary(args.session_id)
    updated_summary = StageMachine().apply_human_decision(
        summary=summary,
        decision=args.decision,
        target_stage=args.target_stage,
    )
    store.save_workflow_summary(session, updated_summary)
    execution_context_path = _save_next_execution_context_if_needed(
        args=args,
        store=store,
        session=session,
        summary=updated_summary,
    )
    store.set_human_decision(args.session_id, updated_summary.human_decision)
    store.record_event(
        args.session_id,
        kind="workflow_state_changed",
        stage=updated_summary.current_stage,
        state=updated_summary.current_state,
        actor="runtime",
        status=updated_summary.human_decision,
        message=(
            f"Workflow moved to {updated_summary.current_stage} / "
            f"{updated_summary.current_state} after human decision."
        ),
    )
    _print_summary(updated_summary)
    if execution_context_path is not None:
        print(f"execution_context: {execution_context_path}")
    return 0


def _save_next_execution_context_if_needed(
    *,
    args: argparse.Namespace,
    store: StateStore,
    session,
    summary: WorkflowSummary,
) -> Path | None:
    stage = _expected_submission_stage(summary)
    if stage is not None:
        contract = build_stage_contract(
            repo_root=args.repo_root,
            state_store=store,
            session_id=args.session_id,
            stage=stage,
        )
        context = build_stage_execution_context(
            repo_root=args.repo_root,
            state_store=store,
            session_id=args.session_id,
            stage=stage,
            contract=contract,
        )
        execution_context_path = store.save_execution_context(context)
        summary.artifact_paths["execution_context"] = str(execution_context_path)
        store.save_workflow_summary(session, summary)
        return execution_context_path
    return None


def _artifact_key_for_stage_result(result: StageResultEnvelope) -> str:
    return artifact_key_for(result.stage)


def _policy_for_stage_result(result: StageResultEnvelope, registry):
    return registry.get(result.stage)


def _handle_record_feedback(args: argparse.Namespace) -> int:
    store = StateStore(args.state_root)
    session = None
    updated_summary = None
    if args.apply_rework:
        session = store.load_session(args.session_id)
        summary = store.load_workflow_summary(args.session_id)
        updated_summary = StageMachine().apply_human_decision(
            summary=summary,
            decision="rework",
            target_stage=args.target_stage,
        )

    finding = Finding(
        source_stage=args.source_stage,
        target_stage=args.target_stage,
        issue=args.issue,
        severity=args.severity,
        lesson=args.lesson,
        proposed_context_update=args.context_update,
        proposed_contract_update=args.contract_update,
        evidence=args.evidence,
        evidence_kind=args.evidence_kind,
        required_evidence=list(args.required_evidence),
        completion_signal=args.completion_signal,
    )
    feedback_path = store.record_feedback(args.session_id, finding)
    print(f"recorded_feedback: {feedback_path}")
    if updated_summary is not None and session is not None:
        store.save_workflow_summary(session, updated_summary)
        store.set_human_decision(args.session_id, updated_summary.human_decision)
        store.record_event(
            args.session_id,
            kind="workflow_state_changed",
            stage=updated_summary.current_stage,
            state=updated_summary.current_state,
            actor="human",
            status=updated_summary.human_decision,
            message=(
                f"Workflow moved to {updated_summary.current_stage} / "
                f"{updated_summary.current_state} after feedback-triggered rework."
            ),
        )
        _print_summary(updated_summary)
    return 0


def _handle_review(args: argparse.Namespace) -> int:
    store = StateStore(args.state_root)
    print(store.read_review(session_id=args.session_id))
    return 0


def _handle_status(args: argparse.Namespace) -> int:
    store = StateStore(args.state_root)
    session_id = args.session_id or store.latest_session_id()
    if not session_id:
        raise SystemExit("No workflow session exists yet.")

    if args.json:
        snapshot = build_panel_snapshot(store, session_id, repo_root=args.repo_root)
        print(json.dumps(snapshot, indent=2))
        return 0

    if args.verbose:
        summary = store.load_workflow_summary(session_id)
        _print_summary(summary)
        if summary.current_state in WAIT_STATES:
            print("next_action: record-human-decision")
            return 0
        active_run = store.active_stage_run(session_id)
        if active_run is not None:
            print(f"run_id: {active_run.run_id}")
            print(f"run_stage: {active_run.stage}")
            print(f"run_status: {active_run.state}")
            print(f"contract_id: {active_run.contract_id}")
            if active_run.required_outputs:
                print(f"required_outputs: {', '.join(active_run.required_outputs)}")
            if active_run.required_evidence:
                print(f"required_evidence: {', '.join(active_run.required_evidence)}")
            if active_run.state == "RUNNING":
                print("next_action: submit-stage-result")
            elif active_run.state == "SUBMITTED":
                print("next_action: verify-stage-result")
            else:
                print("next_action: wait")
            return 0
        expected_stage = _expected_submission_stage(summary)
        if expected_stage is None:
            print("next_action: none")
            return 0
        contract = build_stage_contract(
            repo_root=args.repo_root,
            state_store=store,
            session_id=session_id,
            stage=expected_stage,
        )
        print(f"next_stage: {expected_stage}")
        print(f"contract_id: {contract.contract_id}")
        if contract.required_outputs:
            print(f"required_outputs: {', '.join(contract.required_outputs)}")
        if contract.evidence_requirements:
            print(f"required_evidence: {', '.join(contract.evidence_requirements)}")
        print("next_action: acquire-stage-run")
        return 0

    snapshot = build_panel_snapshot(store, session_id, repo_root=args.repo_root)
    overview = snapshot["overview"]
    print(f"project: {overview['project']}")
    print(f"role: {overview['role']}")
    print(f"status: {overview['status']}")
    print(f"detail: {overview['detail']}")
    print(f"session_id: {session_id}")
    print(f"panel: agent-team panel --session-id {session_id}")
    return 0


def _handle_panel(args: argparse.Namespace) -> int:
    store = StateStore(args.state_root)

    if args.json:
        session_id = args.session_id or store.latest_session_id()
        if not session_id:
            raise SystemExit("No workflow session exists yet.")
        print(json.dumps(build_panel_snapshot(store, session_id, repo_root=args.repo_root), indent=2))
        return 0

    from .web_server import run_console_server

    run_console_server(
        store=store,
        default_session_id=args.session_id,
        repo_root=args.repo_root,
        host=args.host,
        port=args.port,
        open_browser=args.open_browser,
        default_route="/projects",
    )
    return 0


def _print_summary(summary: WorkflowSummary) -> None:
    print(f"session_id: {summary.session_id}")
    print(f"current_state: {summary.current_state}")
    print(f"current_stage: {summary.current_stage}")
    print(f"acceptance_status: {summary.acceptance_status}")
    print(f"human_decision: {summary.human_decision}")


def _load_acceptance_matrix(path: Path | None) -> list[dict[str, object]]:
    if path is None:
        return []
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise SystemExit("--acceptance-matrix must point to a JSON array.")
    return [dict(item) for item in payload]


def _approved_product_definition_summary(*, summary: WorkflowSummary, result: StageResultEnvelope) -> str:
    if result.stage == "ProductDefinition":
        return result.artifact_content[:4000]
    product_definition_path = summary.artifact_paths.get("product_definition")
    if product_definition_path and Path(product_definition_path).exists():
        return Path(product_definition_path).read_text()[:4000]
    return ""


def _gate_decision_to_dict(decision) -> dict[str, object]:
    return {
        "outcome": decision.outcome,
        "target_stage": decision.target_stage,
        "reason": decision.reason,
        "missing_outputs": list(decision.missing_outputs),
        "missing_evidence": list(decision.missing_evidence),
        "findings": [finding.to_dict() for finding in decision.findings],
        "judge_verdict": decision.judge_verdict,
        "judge_confidence": decision.judge_confidence,
        "judge_trace_id": decision.judge_trace_id,
        "derived_status": decision.derived_status,
    }


def _judge_result_to_dict(judge_result) -> dict[str, object] | None:
    if judge_result is None:
        return None
    return {
        "verdict": judge_result.verdict,
        "target_stage": judge_result.target_stage,
        "confidence": judge_result.confidence,
        "reasons": list(judge_result.reasons),
        "missing_evidence": list(judge_result.missing_evidence),
        "findings": [finding.to_dict() for finding in judge_result.findings],
        "trace_id": judge_result.trace_id,
    }


def _expected_submission_stage(summary: WorkflowSummary) -> str | None:
    if summary.current_state == "Intake":
        return "Route"
    if summary.current_state in WORKFLOW_STAGES:
        return summary.current_state
    return None


def _should_refresh_workspace_metadata(command: str) -> bool:
    return True
