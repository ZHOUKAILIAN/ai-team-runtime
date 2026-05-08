import unittest


class StagePolicyTests(unittest.TestCase):
    def test_default_policy_registry_returns_product_definition_approval_policy(self) -> None:
        from agent_team.stage_policies import default_policy_registry

        policy = default_policy_registry().get("ProductDefinition")

        self.assertEqual(policy.stage, "ProductDefinition")
        self.assertIn("product-definition-delta.md", policy.required_outputs)
        self.assertEqual(policy.approval_rule, "requires_product_definition_approval")
        self.assertIn("l1_classification", [spec.name for spec in policy.evidence_specs])

    def test_policy_can_compile_to_stage_contract(self) -> None:
        from agent_team.stage_policies import default_policy_registry

        contract = default_policy_registry().build_contract(
            session_id="session-1",
            stage="Implementation",
            contract_id="contract-implementation",
            input_artifacts={"technical_design": ".agent-team/session/technical-design.md"},
            role_context="Implementation role context",
        )

        self.assertEqual(contract.stage, "Implementation")
        self.assertEqual(contract.required_outputs, ["implementation.md"])
        self.assertIn("self_code_review", contract.evidence_requirements)
        self.assertIn("self_verification", contract.evidence_requirements)
        self.assertIn("must_not_rewrite_upper_layer_truth_from_lower_layer", contract.forbidden_actions)
        self.assertEqual(contract.role_context, "Implementation role context")


if __name__ == "__main__":
    unittest.main()
