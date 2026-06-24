module "glab_skill" {
  source = "./modules/custom_claude_skill"

  display_title = "GitLab CLI"
  skill_path    = "skills/glab"
}
