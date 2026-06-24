resource "claude_skill" "glab" {
  display_title = "GitLab CLI"

  files = {
    "skills/glab/SKILL.md"   = file("${path.module}/../skills/glab/SKILL.md")
    "skills/glab/scripts.py" = file("${path.module}/../skills/glab/scripts.py")
  }
}
