terraform {
  required_providers {
    claude = {
      source  = "registry.terraform.io/erran/claude"
      version = "~> 0.1.4"
    }
  }
}

# Use workload identity federation to authenticate Tofu with Claude API in CI:
provider "claude" {
  federation_rule_id = var.federation_rule_id
  organization_id    = var.organization_id
  service_account_id = var.service_account_id
  workspace_id       = var.workspace_id
}
