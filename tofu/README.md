# Tofu

[OpenTofu](https://opentofu.org) configuration for managing custom Claude Skills.

## Provider

This project uses the [`erran/claude`](https://registry.terraform.io/providers/erran/claude/latest/docs)
Terraform provider. See its documentation for the full list of resources and data
sources, including [`claude_skill`](https://registry.terraform.io/providers/erran/claude/latest/docs/resources/skill).

## Usage

Infrastructure changes will be planned in this project's CI/CD pipeline automatically
thanks to the [opentofu](https://gitlab.com/components/opentofu/) component.

A maintainer or owner of the project must trigger the manual job to apply saved plan output.
