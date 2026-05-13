---
name: write-large-file
description: Write large files reliably using chunked bash append (>> heredoc)
version: 1.0.0
category: Shell & Environment
license: MIT
metadata:
  audience: general
  workflow: local
---

# Write Large File Skill

When creating files longer than ~150 lines (reports, reviews, documentation, generated code), write them in chunks using bash `>>` with heredocs instead of a single Write tool call. This avoids timeouts and context issues with large file creation.

## When to Use

- File content exceeds ~150 lines
- Generating reports, review documents, analysis summaries
- Creating any structured document with multiple sections
- Writing generated code files

## Technique

1. **First chunk**: Use `>` (overwrite) to create the file
2. **Subsequent chunks**: Use `>>` (append) to add sections
3. **Each chunk**: ~50-100 lines, split at natural section boundaries
4. **Verify**: `wc -l` after the last chunk to confirm

## Pattern

```bash
# Chunk 1: Create file with header and first section
cat > ./tmp/output.md << 'HEREDOC_END'
# Document Title

## Section 1

Content for the first section goes here...
HEREDOC_END

# Chunk 2: Append next section
cat >> ./tmp/output.md << 'HEREDOC_END'

## Section 2

Content for the second section...
HEREDOC_END

# Chunk 3: Append final section
cat >> ./tmp/output.md << 'HEREDOC_END'

## Section 3

Final content...
HEREDOC_END

# Verify
wc -l ./tmp/output.md
```

## Rules

- Always use a **quoted heredoc delimiter** (`<< 'HEREDOC_END'`) to prevent variable expansion and special character issues
- Keep chunks between 50-100 lines each — small enough to be reliable, large enough to be efficient
- Split at **natural boundaries** (section headers, function definitions, logical breaks)
- Use `>` only for the first chunk, `>>` for all subsequent chunks
- Run `wc -l` after the final chunk to verify the complete file was written
- Choose a heredoc delimiter that won't appear in the content (`HEREDOC_END` is the recommended default; if content contains that string, use something unique like `HEREDOC_END_2`)
