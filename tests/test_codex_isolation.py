import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agent_team.codex_isolation import isolated_codex_env, prepare_isolated_codex_home, sanitize_codex_config
from agent_team.executor_env import build_executor_env


class CodexIsolationTests(unittest.TestCase):
    def test_sanitize_codex_config_removes_prompt_injection_surfaces(self) -> None:
        config = """
model_provider = "local"

[model_providers.local]
base_url = "https://example.test/v1"

[mcp_servers.apifox]
command = "npx"
args = ["apifox"]

[mcp_servers.apifox.env]
TOKEN = "secret"

[plugins."documents@openai-primary-runtime"]
enabled = true

[marketplaces.openai-primary-runtime]
enabled = true

[features]
codex_hooks = true
hooks = true

[hooks]
startup = "echo unsafe"

[[skills.config]]
name = "superpowers:using-superpowers"
path = "/Users/example/.codex/superpowers/skills/using-superpowers/SKILL.md"

[projects."/repo"]
trust_level = "trusted"
"""

        sanitized = sanitize_codex_config(config)

        self.assertIn('model_provider = "local"', sanitized)
        self.assertIn("[model_providers.local]", sanitized)
        self.assertIn("[projects.\"/repo\"]", sanitized)
        self.assertNotIn("mcp_servers", sanitized)
        self.assertNotIn("plugins", sanitized)
        self.assertNotIn("marketplaces", sanitized)
        self.assertNotIn("skills.config", sanitized)
        self.assertNotIn("codex_hooks", sanitized)
        self.assertNotIn("hooks", sanitized)
        self.assertNotIn("secret", sanitized)
        self.assertNotIn("superpowers", sanitized)

    def test_prepare_isolated_codex_home_copies_auth_and_sanitizes_config(self) -> None:
        with TemporaryDirectory() as source_dir, TemporaryDirectory() as target_dir:
            source_home = Path(source_dir)
            target_home = Path(target_dir)
            (source_home / "auth.json").write_text('{"token":"redacted"}')
            (source_home / "config.toml").write_text(
                'model_provider = "local"\n\n[mcp_servers.apifox]\ncommand = "npx"\n'
            )

            prepare_isolated_codex_home(source_home=source_home, target_home=target_home)

            self.assertEqual((target_home / "auth.json").read_text(), '{"token":"redacted"}')
            self.assertIn('model_provider = "local"', (target_home / "config.toml").read_text())
            self.assertNotIn("mcp_servers", (target_home / "config.toml").read_text())

    def test_executor_env_uses_safe_defaults_without_copying_business_secrets(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "PATH": "/usr/bin",
                "HOME": "/Users/example",
                "OPENAI_API_KEY": "openai-secret",
                "DATABASE_URL": "postgres://secret",
                "MYSQL_PASSWORD": "mysql-secret",
                "REDIS_URL": "redis://secret",
                "ALIYUN_ACCESS_KEY_SECRET": "aliyun-secret",
                "AWS_SECRET_ACCESS_KEY": "aws-secret",
            },
            clear=True,
        ):
            env = build_executor_env()

        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertEqual(env["HOME"], "/Users/example")
        self.assertEqual(env["OPENAI_API_KEY"], "openai-secret")
        self.assertNotIn("DATABASE_URL", env)
        self.assertNotIn("MYSQL_PASSWORD", env)
        self.assertNotIn("REDIS_URL", env)
        self.assertNotIn("ALIYUN_ACCESS_KEY_SECRET", env)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)

    def test_executor_env_config_controls_inherited_and_set_values(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "executor-env.json"
            config_path.write_text(
                json.dumps(
                    {
                        "inherit": ["PATH"],
                        "inherit_prefixes": ["CUSTOM_"],
                        "set": {"FIXED": "value"},
                        "unset": ["CUSTOM_SECRET"],
                    }
                )
            )

            env = build_executor_env(
                config_path=config_path,
                base_env={
                    "PATH": "/bin",
                    "HOME": "/Users/example",
                    "CUSTOM_TOKEN": "allowed",
                    "CUSTOM_SECRET": "removed",
                },
            )

        self.assertEqual(env, {"PATH": "/bin", "CUSTOM_TOKEN": "allowed", "FIXED": "value"})

    def test_isolated_codex_env_uses_configured_executor_env_and_temp_codex_home(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "executor-env.json"
            config_path.write_text(json.dumps({"inherit": ["PATH"], "set": {"FIXED": "value"}}))
            with patch.dict("os.environ", {"PATH": "/bin", "DATABASE_URL": "secret"}, clear=True):
                with isolated_codex_env(env_config_path=config_path) as env:
                    self.assertEqual(env["PATH"], "/bin")
                    self.assertEqual(env["FIXED"], "value")
                    self.assertIn("CODEX_HOME", env)
                    self.assertNotEqual(env["CODEX_HOME"], "")
                    self.assertNotIn("DATABASE_URL", env)


if __name__ == "__main__":
    unittest.main()
