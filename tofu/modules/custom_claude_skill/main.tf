resource "claude_skill" "this" {
  display_title = var.display_title

  files = {
    for file in fileset("${path.module}/../../..", "${var.skill_path}/**") :
    file => file("${path.module}/../../../${file}")
  }

  lifecycle {
    precondition {
      condition     = length(fileset("${path.module}/../../..", "${var.skill_path}/**")) > 0
      error_message = "No files found under ${var.skill_path}/. Ensure the directory exists and contains skill files."
    }
  }
}
