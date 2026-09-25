locals {
  claude_skills = ["glab"]
  skills_files = {
    for skill in local.claude_skills : skill => {
      for file in fileset("${path.module}/../skills", "${skill}/**") : file => file("${path.module}/../skills/${file}")
    }
  }
}

resource "claude_skill" "glab" {
  display_title = "GitLab CLI"
  files         = local.skills_files["glab"]
}
