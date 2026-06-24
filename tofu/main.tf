resource "claude_skill" "glab" {
  display_title = "GitLab CLI"

  files = {
    for file in fileset("${path.module}/..", "skills/glab/**") : file => file("${path.module}/../${file}")
  }
}
