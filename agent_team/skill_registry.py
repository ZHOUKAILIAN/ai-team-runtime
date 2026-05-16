from __future__ import annotations

import os
from html import escape
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .harness_paths import default_state_root, resolve_state_root
from .packaged_assets import ASSET_ROOT
from .workflow import STAGES, normalize_stage


SOURCE_ORDER = {"builtin": 0, "personal": 1, "project": 2}
SOURCE_LABELS = {"builtin": "built-in", "personal": "personal", "project": "project"}
SOURCE_SCOPES = {"builtin": "global", "personal": "global", "project": "project"}


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    description: str
    content: str
    source: str
    path: Path
    source_ref: str = ""
    stages: tuple[str, ...] = STAGES
    delivery: str = "prompt"
    sandbox_files: tuple[str, ...] = ()
    env_vars: tuple[str, ...] = ()

    def supports_stage(self, stage: str) -> bool:
        return stage in self.stages


@dataclass(slots=True)
class SkillPreferences:
    initialized: bool = False
    last: dict[str, list[str]] = field(default_factory=lambda: {stage.lower(): [] for stage in STAGES})
    frequent: dict[str, dict[str, int]] = field(default_factory=lambda: {stage.lower(): {} for stage in STAGES})
    defaults: dict[str, list[str]] = field(default_factory=lambda: {stage.lower(): [] for stage in STAGES})

    @property
    def is_first_time(self) -> bool:
        return not self.initialized and not any(
            self.last.get(stage.lower()) or self.defaults.get(stage.lower()) for stage in STAGES
        )

    def selected_for(self, stage: str) -> list[str]:
        key = stage.lower()
        return list(self.defaults.get(key) or self.last.get(key, []))

    def format_last(self, stage: str) -> str:
        selected = self.selected_for(stage)
        return ", ".join(selected) if selected else "none"


@dataclass(slots=True)
class SkillRegistry:
    repo_root: Path
    preference_path: Path | None = None

    def __post_init__(self) -> None:
        self.repo_root = self.repo_root.resolve()
        if self.preference_path is None:
            self.preference_path = default_state_root(repo_root=self.repo_root) / "skill-preferences.yaml"

    def list_skills(self, stage: str | None = None, source: str | None = None) -> list[Skill]:
        skills_by_name: dict[str, Skill] = {}
        for skill in self._discover_all():
            if stage and not skill.supports_stage(_normalize_stage(stage)):
                continue
            if source and skill.source != source:
                continue
            existing = skills_by_name.get(skill.name)
            if existing is None or SOURCE_ORDER[skill.source] > SOURCE_ORDER[existing.source]:
                skills_by_name[skill.name] = skill

        prefs = self.load_preferences()
        stage_key = _normalize_stage(stage).lower() if stage else ""
        frequent = prefs.frequent.get(stage_key, {})
        return sorted(
            skills_by_name.values(),
            key=lambda skill: (
                -frequent.get(skill.name, 0),
                -SOURCE_ORDER[skill.source],
                skill.name,
            ),
        )

    def get_skill(self, name: str, stage: str | None = None) -> Skill | None:
        for skill in self.list_skills(stage=stage):
            if skill.name == name:
                return skill
        return None

    def resolve_enabled(self, selected_by_stage: dict[str, list[str]]) -> dict[str, list[Skill]]:
        enabled: dict[str, list[Skill]] = {}
        for stage, names in selected_by_stage.items():
            stage_name = _normalize_stage(stage)
            stage_skills: list[Skill] = []
            for name in names:
                skill = self.get_skill(name, stage=stage_name)
                if skill is not None:
                    stage_skills.append(skill)
            enabled[stage_name] = stage_skills
        return enabled

    def load_preferences(self) -> SkillPreferences:
        assert self.preference_path is not None
        path = self._load_preference_path()
        if not path.exists():
            return SkillPreferences()
        return _parse_preferences(path.read_text())

    def save_preferences(self, preferences: SkillPreferences) -> None:
        assert self.preference_path is not None
        self.preference_path.parent.mkdir(parents=True, exist_ok=True)
        self.preference_path.write_text(_render_preferences(preferences))

    def record(self, stage: str, selected: Iterable[str], *, update_last: bool = True) -> None:
        preferences = self.load_preferences()
        key = _normalize_stage(stage).lower()
        selected_list = list(selected)
        preferences.initialized = True
        if update_last:
            preferences.last[key] = selected_list
        frequent = preferences.frequent.setdefault(key, {})
        for name in selected_list:
            frequent[name] = frequent.get(name, 0) + 1
        self.save_preferences(preferences)

    def reset_preferences(self) -> None:
        self.save_preferences(SkillPreferences())

    def set_default(self, stage: str, skills: Iterable[str]) -> None:
        preferences = self.load_preferences()
        preferences.defaults[_normalize_stage(stage).lower()] = list(skills)
        self.save_preferences(preferences)

    def clear_default(self, stage: str) -> None:
        preferences = self.load_preferences()
        preferences.defaults[_normalize_stage(stage).lower()] = []
        self.save_preferences(preferences)

    def _discover_all(self) -> list[Skill]:
        skills: list[Skill] = []
        skills.extend(_discover_skill_root(_builtin_skill_root(), source="builtin"))
        for root in _personal_skill_roots():
            skills.extend(_discover_skill_root(root, source="personal"))
        for stage in STAGES:
            skills.extend(_discover_skill_root(self.repo_root / stage / "skills", source="project", stage=stage))
        return skills

    def _load_preference_path(self) -> Path:
        assert self.preference_path is not None
        if self.preference_path.exists():
            return self.preference_path
        legacy_path = resolve_state_root(repo_root=self.repo_root) / "skill-preferences.yaml"
        return legacy_path if legacy_path.exists() else self.preference_path


def skill_injection_text(skills: list[Skill], *, asset_root: str = ".agent-team/skills") -> str:
    if not skills:
        return ""
    parts = ["<enabled_skills>"]
    for skill in skills:
        parts.append(f'<skill name="{escape(skill.name, quote=True)}">')
        source_ref = skill.source_ref or str(skill.path.parent.resolve())
        parts.append(f"<source_type>{escape(skill.source)}</source_type>")
        parts.append(f"<source_ref>{escape(source_ref)}</source_ref>")
        if skill.delivery == "sandbox":
            parts.append("<delivery>sandbox</delivery>")
            parts.append(f"<asset_root>{escape(f'{asset_root}/{skill.name}/')}</asset_root>")
            if skill.env_vars:
                env_vars = "".join(f"<env_var>{escape(value)}</env_var>" for value in skill.env_vars)
                parts.append(f"<required_environment_variables>{env_vars}</required_environment_variables>")
        else:
            parts.append(f"<delivery>{escape(skill.delivery)}</delivery>")
        parts.append("<content>")
        parts.append(_xml_cdata(skill.content))
        parts.append("</content>")
        parts.append("</skill>")
    parts.append("</enabled_skills>")
    return "\n".join(parts).strip()


def _xml_cdata(value: str) -> str:
    return "<![CDATA[" + value.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def skill_scope(source: str) -> str:
    return SOURCE_SCOPES.get(source, source)


def _discover_skill_root(root: Path, *, source: str, stage: str | None = None) -> list[Skill]:
    if not root.exists():
        return []
    skills: list[Skill] = []
    for skill_file in sorted(root.glob("*/SKILL.md")):
        skill = _read_skill(skill_file, source=source, stage=stage)
        if skill is not None:
            skills.append(skill)
    return skills


def _read_skill(path: Path, *, source: str, stage: str | None = None) -> Skill | None:
    raw = path.read_text()
    metadata, body = _split_frontmatter(raw)
    name = metadata.get("name") or path.parent.name
    description = metadata.get("description", "")
    stages = _metadata_list(metadata.get("stages") or metadata.get("stage"))
    if not stages:
        stages = [stage] if stage else list(STAGES)
    return Skill(
        name=name,
        description=description,
        content=body.strip(),
        source=source,
        source_ref=_skill_source_ref(metadata, path),
        path=path,
        stages=tuple(_normalize_stage(item) for item in stages),
        delivery=metadata.get("delivery", "prompt"),
        sandbox_files=tuple(_metadata_list(metadata.get("sandbox_files"))),
        env_vars=tuple(_metadata_list(metadata.get("env_vars"))),
    )


def _split_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    metadata: dict[str, str] = {}
    current_key = ""
    current_values: list[str] = []
    for line in parts[1].splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current_key:
            current_values.append(stripped[2:].strip())
            metadata[current_key] = ",".join(current_values)
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            current_key = key.strip()
            current_values = []
            metadata[current_key] = value.strip().strip('"')
    return metadata, parts[2]


def _metadata_list(value: str | None) -> list[str]:
    if not value:
        return []
    stripped = value.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]
    return [item.strip().strip('"').strip("'") for item in stripped.split(",") if item.strip()]


def _skill_source_ref(metadata: dict[str, str], path: Path) -> str:
    for key in ("source_ref", "source_url", "source_uri", "source_link", "origin", "repository", "repo_url", "url"):
        value = metadata.get(key, "").strip()
        if not value:
            continue
        if "://" in value or value.startswith("git@"):
            return value
        candidate = Path(value).expanduser()
        if candidate.is_absolute():
            return str(candidate)
        return str((path.parent / candidate).resolve())
    return str(path.parent.resolve())


def _builtin_skill_root() -> Path:
    return Path(str(ASSET_ROOT.joinpath("skills")))


def _personal_skill_roots() -> list[Path]:
    roots: list[Path] = []
    for env_name in ("AGENT_TEAM_SKILL_PATH",):
        raw = os.environ.get(env_name, "")
        roots.extend(Path(item).expanduser() for item in raw.split(os.pathsep) if item)
    return roots


def _normalize_stage(stage: str) -> str:
    return normalize_stage(stage)


def _parse_preferences(raw: str) -> SkillPreferences:
    preferences = SkillPreferences()
    current_stage = ""
    current_section = ""
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 0 and ":" in stripped and not stripped.endswith(":"):
            key, value = stripped.split(":", 1)
            if key.strip() == "initialized":
                preferences.initialized = value.strip().lower() == "true"
            continue
        if indent == 0 and stripped.endswith(":"):
            current_stage = stripped[:-1]
            preferences.last.setdefault(current_stage, [])
            preferences.frequent.setdefault(current_stage, {})
            preferences.defaults.setdefault(current_stage, [])
            current_section = ""
            continue
        if indent == 2 and ":" in stripped:
            section, value = stripped.split(":", 1)
            current_section = section.strip()
            values = _metadata_list(value.strip())
            if current_section in {"last", "defaults"} and values:
                getattr(preferences, current_section)[current_stage].extend(values)
            continue
        if not current_stage or not current_section:
            continue
        if current_section in {"last", "defaults"} and stripped.startswith("- "):
            getattr(preferences, current_section)[current_stage].append(stripped[2:].strip())
        elif current_section == "frequent" and ":" in stripped:
            name, count = stripped.split(":", 1)
            try:
                preferences.frequent[current_stage][name.strip()] = int(count.strip())
            except ValueError:
                preferences.frequent[current_stage][name.strip()] = 0
    return preferences


def _render_preferences(preferences: SkillPreferences) -> str:
    lines = [
        "# Agent Team skill preferences. Automatically maintained; safe to edit.",
        f"initialized: {'true' if preferences.initialized else 'false'}",
        "",
    ]
    for stage in STAGES:
        key = stage.lower()
        lines.append(f"{key}:")
        for section in ("last", "defaults"):
            lines.append(f"  {section}:")
            for name in getattr(preferences, section).get(key, []):
                lines.append(f"    - {name}")
        lines.append("  frequent:")
        for name, count in sorted(preferences.frequent.get(key, {}).items()):
            lines.append(f"    {name}: {count}")
        lines.append("")
    return "\n".join(lines)
