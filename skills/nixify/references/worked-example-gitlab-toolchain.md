# Worked example — gitlab-toolchain (replace a build system)

This is the canonical **build-system-replacement** case: a repo whose product is
the software it builds. Use it as the mental model for Stage 3.

> **Provenance caveat.** Much of the detail below comes from internal-leaning
> sources (the repo README on its `devel` branch, internal epics/MRs/Slack); the
> public repo is login-gated. Treat component lists, timings, and percentage
> targets as point-in-time and possibly-internal. The high-level architecture is
> well-corroborated. Re-verify against the live repo before acting.

## What it is

The home of **TBMS — "Toolchain Build Manager System"** — which builds the
**`gitlab-toolchain`**, organizationally the **Universal Build Toolchain
(UBT)**. Per its README: a monorepo of components "used to build the
gitlab-toolchain… A monorepo for all components was required given the specific
order of execution and interdependencies." Its product is "used by the rest of
GitLab for all of their dependencies."

It is a strategic replacement for omnibus-gitlab's monolithic, from-scratch,
per-OS compilation (the Chef-based `config/software/*.rb` software-definitions
model building into `/opt/gitlab`), and it supersedes the per-OS
`gitlab-omnibus-builder` images.

## What it builds

Build-time dependencies / runtimes / libraries for all of GitLab. Confirmed
components include: **GCC, glibc, binutils, m4, crosstool-ng, perl, OpenSSL,
zlib-ng, curl, cacerts, Go, Ruby, Python, PostgreSQL, jemalloc, popt, git,
patroni**, plus standard omnibus components.

## How it builds today (NOT Nix)

A bash-based, staged, container build system modeled on OS packagers:

- **Stages as OCI containers.** Stage 1 = static tools (e.g. curl) built once;
  Stage 2 = the glibc toolchain bootstrapped via **crosstool-ng** ("a system in
  a system", config `static228`); Stage 3 = compile the actual GitLab
  components.
- **Execution:** `build-chains → ./builder.sh → ./tbm.sh`. build-chains are
  plain-text files listing packages in build order (no parallelism yet).
- **TBM operations** (inspired by rpmbuild/dpkg-deb/ebuild/ports):
  `prep → fetch → unpak → patch → configure → build → dist → deploy → test`,
  with pre-/post- companion tasks.
- **Component spec notation:** `NAME`, `NAME@VARIANT`, `NAME-VERSION`,
  `NAME~SUB-VERSION@VARIANT`, with per-component `DEFAULT_VERSION`.
- **Layout:** `tbms/components/<c>/SOURCES/*.yaml`, `tbms/base/`,
  `tbms/VARIANTS/<v>/`, `build-chains/`, `builder.sh`/`tbm.sh`/`packager.sh`,
  `patches/<c>-<ver>/`, `gitlab-ci/`, `doc/adr`. Reproducible tarball outputs
  (`tar --sort=name --mtime=@$SOURCE_DATE_EPOCH --owner=0 --group=0
  --numeric-owner | gzip --no-name`), e.g. `popt-1.16-3ubt+crosstool.tgz`.
  Multiarch (amd64+arm64). Needs `yq 4.45+`.
- **CI timings (reported):** stage 1 ~50 min, stage 2 ~160 min, stage 3 up to
  ~12 h (the runner's 4 h timeout is a known pain point).

## The consumer contract (must preserve)

UBT must "produce per-component artifacts that Omnibus can consume without
changing the existing URL and SHA256 contract." The Omnibus consumer side does
not change. **Any Nix migration must keep emitting URL+SHA256 tarballs the
downstream already fetches.**

Stated goals: cut component build *combinations* from ~3,800 to ~320 (~92%) and
total build time ~90%. Status (as reported, Apr 2026): "highly functional POC,"
default branch `devel`. Known gaps it wants to fix: an explicit dependency graph
(currently "buried in script ordering"), uniform hardening flags, byte
reproducibility. FIPS/SLSA were out of near-term scope.

## How nixify re-expresses it

The migration is almost a category match for what Nix *is*:

1. **Each component → reuse nixpkgs' definition, override for the delta.** GCC,
   glibc, OpenSSL, Ruby, PostgreSQL, … mostly already exist in nixpkgs. **Prefer
   reusing nixpkgs' own definition (built against your pinned stdenv) over
   hand-writing a `stdenv.mkDerivation`** — nixpkgs already maintains the
   configure flags, multi-output splits, and fixups. Express only the delta the
   toolchain needs (pin a version + source, add a configure flag, carry a
   patch needed to build against the pinned libc) via `.overrideAttrs` /
   `.override` — i.e. *configure them as overlays*. A small helper
   (`reuseNixpkgs pkg { version?; src?; extraConfigureFlags?; extraPatches?; }`)
   keeps every component a one-liner-plus-delta. Hand-write a full derivation
   only when nixpkgs lacks the package. Note: nixpkgs' default `hardeningEnable`
   is usually a superset of a bespoke hardening profile, so reuse rarely weakens
   hardening — verify rather than assume.
2. **The dependency graph replaces build-chains.** Components reference each
   other through the `stdenv` fixpoint in an `overlays.default`. The ordering
   that was "buried in script sequence" *becomes* the derivation graph — the
   single biggest stated gap disappears for free.
3. **Stages 1–2 → a custom stdenv / bootstrap, built natively by default.** The
   crosstool-ng glibc toolchain stage maps to a pinned-libc overlay, expressed
   once and depended upon by everything downstream (see `references/c-cpp.md` on
   `overrideCC` / `wrapCCWith`). **Crucial:** crosstool-ng was a genuine *cross*
   build, but a Nix migration should make the **native (QEMU-emulated)** path the
   default reproducible artifact, since cross output isn't byte-identical to
   native and parity with the old artifact is the goal. Apply the libc overlay to
   *two* sets — `nativePkgs` (default, `localSystem = <target>`, emulated on a
   foreign-arch builder) and `crossPkgs` (opt-in, genuine cross from a fixed
   build host, for fast iteration) — and ship/validate/cache the native one.
   Watch the trap: `crossSystem` with `localSystem = system` does **not** give
   you a meaningful cross; verify drvPaths. Full pattern in
   `references/native-vs-cross.md`.
4. **Per-component caching is native.** Each derivation is independently cached
   and substitutable — directly delivering the per-component rebuild / publish
   goal, and shrinking the rebuild combinatorics without hand-rolled cache logic.
5. **Per-tool scoped outputs + overlay.** `packages.<system>.gcc`,
   `.ruby`, `.postgresql`, … plus `overlays.default` for consumers. See
   `references/scoped-outputs.md`.
6. **Preserve URL+SHA256.** Nix FOD outputs have content hashes; add a thin
   publish adapter that emits the reproducible tarballs (sorted tar +
   `SOURCE_DATE_EPOCH`, which Nix does automatically) and their SHA256s in the
   layout Omnibus already consumes. Consumers don't change.
7. **Validation via checks/VM tests.** Replace hand-rolled per-tool health checks
   with `pkgs.testers.testVersion` + link-against-expected-lib assertions +
   `runNixOSTest` that boots a tool and asserts it works. See
   `references/vm-tests.md`.

### Suggested layout

```
flake.nix                       # thin: inputs, custom stdenv, eachSystem, overlay
lib/
  bootstrap.nix                 # crosstool-ng-equivalent custom stdenv
pkgs/
  gcc/package.nix
  glibc/package.nix
  openssl/package.nix
  ruby/package.nix
  postgresql/package.nix
  …                             # one per component
publish/
  adapter.nix                   # emit URL+SHA256 tarballs for Omnibus
checks/
  <tool>-smoke.nix              # testVersion + link assertions
```

### Migration order (de-risked)

1. Pick a *leaf* component with no internal deps (e.g. `popt`, `m4`) → package
   it, validate the tarball+hash matches what Omnibus expects.
2. Walk up the graph (zlib-ng → OpenSSL → curl → …), validating the consumer
   contract at each step.
3. Tackle the toolchain bootstrap (glibc/GCC via custom stdenv) once leaves
   prove the contract adapter works.
4. Keep the old bash system running in parallel; cut over per-component as each
   is validated. The overlay makes a mixed old/new state expressible.
