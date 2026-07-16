# Documentation Standards

## Required Documentation

Every public or exported item must have documentation. No exceptions. This means:

- Functions and methods
- Types (structs, enums, classes, interfaces)
- Constants and exported variables
- Packages, modules, and crates

If it's public, someone will try to use it. And if they can't figure out what it does
from the docs, they'll either misuse it or skip it entirely.

## Documentation Content Requirements

### Functions

Start with a verb phrase describing what the function does. Then cover these areas as
relevant:

- **Parameters:** What each one means, valid ranges, defaults
- **Return value:** What it represents, possible error conditions
- **Errors:** When and why the function fails
- **Examples:** At least one usage example for non-trivial functions
- **Edge cases:** What happens with empty input, nil/null, zero values
- **Side effects:** File I/O, network calls, state mutations

### Packages and Modules

Package-level docs answer different questions than function docs:

- **Purpose:** What problem does this package solve?
- **When to use:** Under what circumstances would you import this?
- **Quick-start example:** Show the most common usage pattern
- **Main exports:** List the key types and functions you'll interact with

## Language-Specific Formats

### Go

Go doc comments start with the name of the thing being documented:

```go
// NormalizeVersion converts a version string to a canonical form.
// It handles common variations like leading "v" prefixes, missing
// patch versions, and pre-release suffixes.
//
// NormalizeVersion is idempotent — calling it twice on the same
// input produces the same result.
//
// Returns an error if the input can't be parsed as a version.
func NormalizeVersion(raw string) (string, error) {
```

Package comments go in a `doc.go` file or at the top of the primary source file:

```go
// Package version provides utilities for parsing, comparing, and
// normalizing software version strings across different ecosystems.
//
// Use this package when you need to compare versions from different
// sources (NVD, OSV, distro advisories) that may use different
// formatting conventions.
package version
```

### Rust

Rust uses `///` for item docs and `//!` for module docs. Use markdown headers for
structured sections:

```rust
/// Parses a CPE 2.3 formatted string into its component parts.
///
/// Handles both well-formed and common malformed CPE strings by
/// applying normalization rules before parsing.
///
/// # Examples
///
/// ```
/// let cpe = parse_cpe("cpe:2.3:a:vendor:product:1.0:*:*:*:*:*:*:*")?;
/// assert_eq!(cpe.vendor, "vendor");
/// ```
///
/// # Errors
///
/// Returns `CpeError::InvalidFormat` if the string doesn't start
/// with the `cpe:2.3:` prefix or has fewer than 11 components.
///
/// # Panics
///
/// This function doesn't panic.
pub fn parse_cpe(input: &str) -> Result<Cpe, CpeError> {
```

### Python

Use Google-style docstrings. They're readable as plain text and parse well with
Sphinx and other doc generators:

```python
def calculate_severity(cvss_score: float, exploit_available: bool) -> str:
    """Determine vulnerability severity from CVSS score and exploit status.

    Applies a modified severity scale that bumps the rating up one level
    when a public exploit exists, matching how most security teams
    actually triage vulnerabilities.

    Args:
        cvss_score: CVSS v3.1 base score (0.0 to 10.0).
        exploit_available: Whether a public exploit exists.

    Returns:
        Severity string: "critical", "high", "medium", "low", or "info".

    Raises:
        ValueError: If cvss_score is outside the 0.0-10.0 range.
    """
```

### C

Use Doxygen-style comments for functions declared in header files:

```c
/**
 * @brief Normalize a version string to canonical form.
 *
 * Strips leading "v" prefix, ensures three-part version (major.minor.patch),
 * and lowercases any pre-release suffix.
 *
 * @param dst    Destination buffer for normalized version.
 * @param dstsz  Size of destination buffer.
 * @param src    Input version string to normalize.
 * @return       Number of characters written, or -1 on error.
 *
 * @note The function is idempotent — normalizing an already-normalized
 *       string produces the same output.
 */
int
version_normalize(char *dst, size_t dstsz, const char *src);
```

### Nix

Nix doesn't have a formal doc comment system, but the convention is a comment block
above the function:

```nix
# buildPackageWithPatches — Builds a package from source with optional patches.
#
# Takes a package derivation and a list of patch files. Applies patches
# in order before running the build phase. Patches must apply cleanly
# against the unpacked source.
#
# Arguments:
#   pkg     — The base package derivation to patch
#   patches — List of paths to patch files
#   flags   — Additional configure flags (optional, defaults to [])
buildPackageWithPatches = { pkg, patches, flags ? [] }: ...
```

## Why Documentation Matters for Refactoring

Good docs aren't just for future readers. During refactoring, documentation serves
four specific purposes:

- **Enables AI tooling** — Doc-aware tools can suggest better refactorings when they understand intent
- **Catches design issues early** — If you can't explain what a function does in one sentence, it probably does too much
- **Improves review efficiency** — Reviewers can verify behavior against documented intent
- **Onboards contributors** — New developers can understand the codebase without archaeology
