# Native (emulated) vs cross builds — which is the reproducible artifact

When a flake targets multiple architectures (or a non-host ABI), you must decide
*how* each target is built: **natively** (built for the target, emulated under
QEMU on a foreign-arch builder) or **cross-compiled** (built on the host with a
cross-toolchain). They are not interchangeable.

## The rule

**Native is the default and the reproducible artifact. Cross is an opt-in
fast-iteration convenience.**

- **Cross-compiled binaries are not guaranteed byte-identical to natively-built
  ones.** Different code paths in the compiler/libc, host-tool leakage, and
  `build != host` conditionals all diverge. If your spec has a reproducibility
  requirement (two builds → identical output hash) or a parity goal against a
  previous native/crosstool-ng build, the **native** path is what satisfies it.
- **Native-for-foreign-arch needs emulation.** `import nixpkgs { localSystem =
  <target>; }` builds *for* the target; on a builder whose real CPU differs, Nix
  transparently runs the target compiler under `qemu-user-static` via
  `binfmt_misc`. Slower, but reproducible.
- **Cross is faster (no emulation)** — ideal for local test/iteration — but its
  output is not the authoritative artifact. Expose it separately.

## The trap: `crossSystem` that silently is (or isn't) cross

A common mistake is wiring `crossSystem` with `localSystem = system` (the
target), e.g. inside `flake-utils.lib.eachSystem`:

```nix
# ANTI-PATTERN — "always cross", even for the host arch:
crossPkgs = import nixpkgs {
  localSystem = system;                       # == target
  crossSystem = { config = tripleFor system; }; # == target triple
};
```

When `crossSystem`'s triple equals `localSystem`, nixpkgs **collapses it to a
native build** — so on the host arch you get native (fine), but the *intent* is
muddled and you cannot tell native from cross by inspecting outputs. Conversely,
if you force a genuine cross by giving a different triple, you've made the
*default* artifact non-reproducible.

## The pattern: one ABI overlay, two package sets

Build one shared overlay that pins the target ABI (custom libc, toolchain, etc.),
then apply it to **two** package sets — native (default) and cross (opt-in):

```nix
# nix/lib/default.nix  (per-system: `system` is the target)
let
  abiOverlay = final: prev: { /* e.g. glibc = pinnedGlibc228; */ };

  tripleFor = {
    "x86_64-linux"  = "x86_64-unknown-linux-gnu";
    "aarch64-linux" = "aarch64-unknown-linux-gnu";
  };

  # DEFAULT, reproducible: built natively for the target (qemu-emulated on a
  # foreign-arch builder). The artifact you ship + validate + cache + relocate.
  nativePkgs = import nixpkgs {
    localSystem = system;
    overlays = [ abiOverlay ];
  };

  # OPT-IN, fast iteration: a GENUINE cross. Fix the build host (the common
  # CI/dev arch) and cross-compile to the target. Collapses to native when
  # target == buildHost, so there is no needless cross on the host arch.
  crossBuildHost = "x86_64-linux";
  crossPkgs = import nixpkgs {
    localSystem = crossBuildHost;
    crossSystem = { config = tripleFor.${system}; };
    overlays = [ abiOverlay ];
  };
in { inherit nativePkgs crossPkgs; }
```

Key detail: **fix `crossBuildHost` to a concrete arch**, not `system`. That makes
the cross set a real cross-compile when `target != buildHost`, and lets nixpkgs
correctly collapse it to native when they match. Make `crossBuildHost`
overridable so an arm64 host can cross the other direction.

## Wiring the two paths into outputs

- `packages.<system>.<component>` / `toolchain` / image / `checks` → built from
  **`nativePkgs`** (the reproducible artifact; what consumers and the overlay
  get).
- Cross siblings → a **distinct** namespace, never the default `packages`:

  ```nix
  legacyPackages = crossPkgs // { cross = crossComponents; };
  # build a cross variant for iteration:  nix build .#legacyPackages.<sys>.cross.<c>
  ```

Drive both from the *same* component definitions (a `mkSet = pkgsSet: …` function
instantiated twice) so native and cross never drift. Have `mkDerivation`
wrappers default to the native set with a `targetPkgs ? nativePkgs` override.

## Verify you actually got it right

Don't trust the comments — check the derivations:

```bash
# Foreign arch: native and cross MUST differ (cross carries the target triple
# in its name; native does not).
nix eval --raw .#packages.aarch64-linux.<c>.drvPath
nix eval --raw .#legacyPackages.aarch64-linux.cross.<c>.drvPath   # → differs

# Host arch: cross MUST collapse to native (identical drvPath) — no needless
# cross-compilation on the host architecture.
nix eval --raw .#packages.x86_64-linux.<c>.drvPath
nix eval --raw .#legacyPackages.x86_64-linux.cross.<c>.drvPath    # → identical
```

The reproducibility gate itself is `nix build <native> --rebuild` (`--check`),
which rebuilds and fails on any non-bit-identical output.

## Document the build requirement

The native foreign-arch path is unbuildable without emulation. State it in an
ADR / README:

- **NixOS builder:** `boot.binfmt.emulatedSystems = [ "aarch64-linux" ];` (add
  `"x86_64-linux"` on arm hosts).
- **CI:** a multi-arch runner, or register `qemu-user-static` +
  `binfmt_misc` in the build container.
- The cross path needs none of this — that's why it's the recommended local
  inner loop, with CI producing the native artifact it ships.

## When cross-only is acceptable

If the project has **no** byte-reproducibility/parity requirement and emulation
is prohibitively slow (very large C/C++ trees, no multi-arch CI), cross-only is a
pragmatic choice — but make it an explicit, documented decision (an ADR), not an
accident of how `crossSystem` was wired.
