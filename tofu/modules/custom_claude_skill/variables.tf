variable "display_title" {
  description = "The display title for the Claude skill."
  type        = string
}

variable "skill_path" {
  description = "Relative path (from the repository root) to the skill directory, e.g. \"skills/glab\"."
  type        = string
}
