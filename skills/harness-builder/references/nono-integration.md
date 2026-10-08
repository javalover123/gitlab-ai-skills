# nono integration — sandbox contract for harness agent invocations

All harness-generated agent invocations go through `nono run`. This file is
the single source of truth for why, what the wrapper looks like, and how each
language wires it up. The per-language references document only the
language-specific argv plumbing — they link here for all policy rationale.

> **Default backend: a nono-sandboxed `opencode serve` instance.** The harness
> drives one project-scoped `opencode serve` per run (see
> `references/opencode-server-integration.md`); the boundary is applied **once**
> at server launch and inherited by every session, subagent, `bash` call, MCP
> server, and LSP. Use the dedicated **`opencode-serve` profile** documented in
> § "opencode server boundary" below — this is the primary, default sandbox
> contract. It codifies only the exact least-privilege set a headless
> `opencode serve` process needs, derived empirically (vulnmapper 2026-06-13:
> server launch, session create, and a live LLM stream all pass with zero path
> or network denials under this profile).
>
> The legacy per-invocation `claude -p` path (the `--network-profile claude-code`
> flag, the device-file and `claude-cli-nodejs` cache grants, the canonical
> wrapper in the next section) remains documented for reference, but it is **not**
> the default. Those grants are specific to the Claude Code TUI binary and are
> not relevant to a headless opencode server. New harnesses target the opencode
> server backend and the `opencode-serve` profile.

## The safety contract

> `bypassPermissions` is permitted **only** when `claude` is launched as a
> child of `nono run` with a derived-from-`--add-dir` allow-list. The
> preflight enforces this; the eval verifies it; the manifest records which
> boundary was actually in effect. Unwrapped invocations stay at `acceptEdits`.

Here's the reasoning. `bypassPermissions` removes the interactive permission
gate — exactly what an unattended looping harness needs. But without a
boundary underneath it, you've handed an autonomous multi-subagent loop
unrestricted access to the host. nono is that boundary: a kernel-enforced
(Landlock on Linux, Seatbelt on macOS) capability sandbox that's irreversible
once applied, with no agent-toggleable escape. Once nono has sandboxed the
Claude subprocess, bypass is safe — "bypass the prompt gate" is a different
thing from "bypass the kernel enforcer."

## Canonical wrapper command

Every Claude invocation in every generated harness uses this shape:

```bash
nono run --silent \
  [--network-profile claude-code] \
  --allow <worktree> --allow <logdir> \
  --allow .bug-burndown --allow .test-effectiveness \
  [--allow .iteratotron] [--allow .harness] \
  [--read <toolchain-dirs>...] \
  [--credential anthropic] \
  -- claude -p <prompt> \
       --output-format stream-json --verbose --include-partial-messages \
       --permission-mode bypassPermissions \
       --model <model> --max-turns <n> --max-budget-usd <n> \
       --add-dir <worktree> --add-dir <logdir> \
       --disallowed-tools WebSearch
```

`--silent` / `-s` suppresses nono's banner so the NDJSON stream on stdout stays
clean for the tee/parser. Always include it.

`--credential anthropic` reads `env://ANTHROPIC_API_KEY` and keeps the key out
of the sandboxed subprocess. Optional but tightens the policy.

### The `--add-dir` ↔ `--allow` invariant

Every directory passed to Claude via `--add-dir <D>` needs a matching
`nono --allow <D>`. nono's default-deny filesystem policy will EPERM Claude
the moment it tries to read or write any unlisted path.

Both lists come from the **same source variable** in the streaming helper.
The shared helpers (`wrap_with_nono`, `wrapWithNono`, `NonoTransport`, etc.)
take one `allow_dirs` parameter and emit both the `nono --allow <D>` flags
and the `claude --add-dir <D>` flags from it. If you're ever maintaining
the two lists separately, you've broken this invariant.

### Shared dotfile dirs

These four dirs need `--allow` on every harness run, regardless of project:

- `.bug-burndown/` — burndown session manifests and per-iteration state
- `.test-effectiveness/` — mutation/CRAP/coverage baseline, auto-gitignored
- `.iteratotron/` — genesis session state (implementation harnesses only)
- `.harness/` — runtime harness work dir (runtime harnesses only)

All are relative paths resolved from the harness working directory (the
worktree root). All are auto-gitignored on first write.

## Network policy

Pass `--network-profile claude-code`. Its `llm_apis` group covers
`api.anthropic.com`, which is the only egress the harness needs — WebSearch is
already blocked via `--disallowed-tools WebSearch`. The nono network proxy is
always-on even without the profile and blocks cloud-metadata endpoints
(`169.254.169.254`) in all configurations.

### Platform degradation

The network proxy + domain filtering requires **Linux 6.7+ (Landlock ABI
v4+)**. On older kernels, WSL2 (kernel 6.6 / ABI v3 as of mid-2026), and
macOS (Seatbelt can't filter by port):

**Drop `--network-profile`, run plain `nono run`.**

The filesystem sandbox still applies fully. `bypassPermissions` is still safe
because the filesystem boundary is universal — only the network egress
narrowing degrades. The preflight detects this automatically:

```
[sandbox] Landlock ABI v3 detected (kernel < 6.7 or WSL2)
[sandbox] network-profile unavailable — dropping --network-profile claude-code
[sandbox] filesystem sandbox active; permission_mode=bypassPermissions
```

macOS gets the same treatment (Seatbelt active, `--network-profile` dropped).

## Preflight algorithm

Run once per harness invocation, before any Claude subprocess is spawned.
Cache the result in a `SandboxVerdict` struct and thread it through to every
spawn site.

```
fn check_sandbox(allow_unsandboxed: bool) -> SandboxVerdict:
    verdict = SandboxVerdict { permission_mode: "acceptEdits", .. }

    // Step 1 — probe nono
    if run(["nono", "--version"]).failed:
        if allow_unsandboxed:
            log.warn("""
            ┌─────────────────────────────────────────────────────┐
            │  RUNNING UNSANDBOXED — nono not found on PATH       │
            │  permission_mode = acceptEdits (NOT bypassPerms)    │
            │  Install: brew install nono                         │
            │           nix shell nixpkgs#nono                    │
            │           .deb from github.com releases             │
            └─────────────────────────────────────────────────────┘
            """)
            return verdict          // acceptEdits, no nono wrap
        else:
            abort("""
            nono is required but not found on PATH.
            Install: brew install nono  |  nix shell nixpkgs#nono
                     or .deb from github.com releases
            Pass --allow-unsandboxed to proceed without the sandbox
            (keeps permission_mode=acceptEdits; not recommended for
            unattended loops).
            """)

    verdict.nono_version = parse_version(stdout)

    // Step 2 — check Landlock ABI
    setup = run(["nono", "setup", "--check-only"])
    if setup.landlock_abi >= 4:
        verdict.network_profile = Some("claude-code")
    else:
        verdict.network_profile = None
        log.warn("[sandbox] Landlock ABI < 4 — dropping --network-profile")

    verdict.permission_mode = "bypassPermissions"
    return verdict
```

The verdict is written to the session manifest immediately after the preflight
(see "Session manifest fields" below).

## Install instructions

```bash
# macOS
brew install nono

# Nix / NixOS
nix shell nixpkgs#nono          # one-off
# or add pkgs.nono to your devShell inputs / flake inputs (see implementation-nix.md)

# Debian / Ubuntu
# download .deb from github.com/nono releases
dpkg -i nono_<version>_amd64.deb
```

**nono is alpha (0.x).** Pin the version in your lockfile and re-test after
any bump — several flags have already changed across minor versions. There's
no `cargo install` path; the `nono` crate is an embeddable library, not a
standalone CLI binary.

## Signal / stdio / exit-code guarantees

nono passes stdin and stdout **straight through** to the child. Your existing
stream-json tee/parser sees the same NDJSON bytes it always did.

**Signals**: nono forwards OS signals to the child. `SIGTERM` sent to the
nono PID reaches Claude; `SIGKILL` sent to nono kills both. Your watchdog
works correctly as-is — it just needs to target the **nono PID** (the direct
child of the harness process) rather than a `claude` PID.

**Exit codes**: `0` = success; `1` = nono-level error (sandbox setup failure,
binary not found, etc.); any other code = the child's exit code propagated
verbatim. An unexpected exit `1` with no stream-json events usually means nono
setup failed rather than Claude failing.

**Process groups (Go harnesses)**: `Setpgid: true` on the nono subprocess
means `syscall.Kill(-pid, ...)` targets the whole group — nono + claude die
together. Keep it.

## Permission modes

The six valid values for `--permission-mode` per `claude --help`:
`acceptEdits`, `auto`, `bypassPermissions`, `default`, `dontAsk`, `plan`.

For harness use:
- `bypassPermissions` — the correct mode when inside `nono run`. No prompts,
  no stalls, kernel enforces the boundary.
- `acceptEdits` — the fallback when nono is absent (`--allow-unsandboxed`).
  Claude can reach anything its tools can reach; loop at your own risk.

### Stdio and stream-json alignment

Even inside nono, the PTY/pipe alignment rules apply if the host has a
`claude-bwrap` wrapper in PATH that intercepts the `claude` binary. nono
sandboxes the claude *process*, not any shell-level wrapper. The generated
harnesses set `CLAUDE_BWRAP_TTY=0` unconditionally on every spawn:

| Layer | Autonomous mode (what the harness sets) |
|---|---|
| `CLAUDE_BWRAP_TTY` | `0` — forces `--pipe` in any bwrap wrapper, even if it regressed to `--pty` |
| `claude` flags | `--output-format stream-json --verbose` (both required together) |
| Caller stdin | `Stdio::null()` / closed — wrappers waiting on EOF need this |
| Caller stdout | line-by-line NDJSON, tee to disk before filtering |

The `"type":"result"` event is the terminal event. After receiving it, fire
the grace timer (default 30 s) then SIGTERM → SIGKILL if the process hasn't
exited. See `references/runtime-gotchas.md` § "Bridge subprocess hangs after
stream-json result event".

## Per-language toolchain `--read` dirs

Claude Code is a Bun binary. Its device files (`/dev/tty`, `/dev/null`,
`/dev/urandom`) are covered by the built-in `claude-code` profile. You still
need `--read` for toolchain dirs accessed via PATH lookup:

| Language | Required `--read` dirs |
|---|---|
| Rust | `~/.cargo/bin`, `~/.rustup` |
| Go | `~/go/bin`, `~/sdk` |
| Python | `~/.pyenv/shims`, `~/.local/bin`, active venv `bin/` |
| Ruby | `~/.rbenv/shims`, `~/.gem` |
| Nix | `/nix/store` (covered by the `claude-code` profile's nix group) |

The per-language streaming helpers include these as defaults. Pass
`extra_read_dirs` to the helper for non-standard toolchain locations.

## opencode server boundary

When the harness drives an `opencode serve` instance (the server backend in
`references/opencode-server-integration.md`), the boundary is applied **once**
at server launch and inherited by every session, subagent, `bash` call, MCP
server, and LSP the server spawns. Do **not** use `--network-profile claude-code`
or any of the Claude Code device-file / `claude-cli-nodejs` grants here — those
are TUI-binary specifics. Use the `opencode-serve` profile instead.

### The `opencode-serve` profile

Ship this as a user profile at `~/.config/nono/profiles/opencode-serve.json`.
It extends `default` (which already carries all the `deny_*` credential /
shell-history / browser-data groups and the Linux system-read core) and adds
only what a headless opencode server actually touches:

```json
{
  "meta": {
    "name": "opencode-serve",
    "version": "0.1.0",
    "description": "Least-privilege sandbox for a headless `opencode serve` instance driven by a harness. Replaces the claude-code profile/network-profile for opencode. No TUI assumptions.",
    "author": "harness-builder"
  },
  "extends": "default",
  "groups": {
    "include": [
      "nix_runtime",
      "opencode_linux",
      "git_config"
    ]
  },
  "workdir": {
    "access": "readwrite"
  },
  "filesystem": {
    "allow": [
      "$HOME/.config/opencode",
      "$HOME/.local/share/opencode",
      "$HOME/.cache/opencode"
    ]
  },
  "network": {
    "network_profile": null
  }
}
```

What each grant is for, and why it's the minimum:

| Grant | Purpose |
|---|---|
| `workdir.access: readwrite` | The project root. `opencode serve` roots at its launch cwd (§2 of the server doc), and nono auto-shares the CWD when `--allow-cwd` is passed. Pass `--allow-cwd` at launch; for a worktree outside CWD, add `--allow <worktree>` instead. |
| group `nix_runtime` | Read access to `/nix/store`, `/run/current-system/sw`, and the nix profile dirs — needed on NixOS to resolve and exec the `opencode` binary and the Bun runtime, LSP servers (e.g. `gopls`), and `libstdc++.so.6`. On non-Nix hosts this group is harmless (paths simply don't exist); resolve the binary via `--read` of its real dir instead (nono prints the exact dir if exec is denied). |
| group `opencode_linux` | Read access to the `~/.opencode` install dir for installer-based opencode installs. **Grant the whole `~/.opencode` dir, not just `~/.opencode/bin`** — the running server reads `~/.opencode/package.json` (a version self-check) during **session creation**, so a `bin`-only grant makes `POST /session` fail with `EACCES … open '~/.opencode/package.json'` → HTTP 500 → every reviewer/burndown session create fails and the loop stalls. See "session-create 500 / EACCES" below. |
| group `git_config` | Read access to `~/.gitconfig` etc. so `git` tool calls inside sessions see the user's identity/ignore rules. |
| `filesystem.allow $HOME/.config/opencode` | Global config, agents, plugins (e.g. the completion-loop plugin). Writable because opencode may rewrite caches here. |
| `filesystem.allow $HOME/.local/share/opencode` | The SQLite session/message store (`opencode.db`), `auth.json`, and the server log dir. Confirm the path with `opencode db path` on the target. |
| `filesystem.allow $HOME/.cache/opencode` | Plugin/node_modules and model-list caches. |
| `network.network_profile: null` | Explicitly clears any inherited network-profile. opencode talks to whatever model provider the run configured (Anthropic, OpenAI, a GitLab Duo endpoint, a local model, …) — pinning the `claude-code` profile would wrongly restrict egress to `api.anthropic.com`. nono's always-on proxy still blocks cloud-metadata (`169.254.169.254`) with no profile. If you want to *narrow* egress to a known provider host, add it via `network.allow_domain` (profile) or `--allow-domain` (CLI) for that run and record it in the manifest — do not reintroduce `claude-code`. |

### Canonical opencode-server launch command

```bash
nono run --silent -p opencode-serve \
  --allow-cwd \
  [--allow <worktree-if-outside-cwd>] \
  --open-port <PORT> \
  [--allow-domain <provider-host>] \
  -- opencode serve --hostname 127.0.0.1 --port <PORT>
```

- `-p opencode-serve` selects the profile above; no per-call `--allow`/`--read`
  enumeration of opencode's own state dirs is needed — the profile carries them.
- `--open-port <PORT>` grants bidirectional loopback TCP on the harness-chosen
  port (connect + listen) so the harness HTTP/SSE client can reach the server.
  This must match the `opencode serve --port <PORT>` value (single source
  variable, same invariant as `--add-dir` ↔ `--allow`).
- Set the child **cwd to the project root** and put it in its **own process
  group** (see server doc §2/§3). Pass `OPENCODE_SERVER_PASSWORD` via env, never
  argv. The harness still sets `OPENCODE_DISABLE_AUTOUPDATE=1`.
- The `wrap_with_nono` helper, when building an opencode-server argv, emits
  exactly this shape: `["nono","run","--silent","-p","opencode-serve",
  "--allow-cwd","--open-port",PORT, ... ,"--","opencode","serve", ...]`. The
  port and any extra `--allow`/`--allow-domain` come from one source variable.

### session-create 500 / EACCES — the grants a bare profile misses (MANDATORY)

`POST /session` returning HTTP 500 is the single most common reason the whole
loop stalls: the reviewer and burndown bridges can't get a session, the reviewer
reports a **total outage**, and (per the global-fixpoint rule) the loop correctly
refuses to declare clean — but never makes progress. The profile grants
opencode's *state* dirs; it routinely misses three things the server touches at
session-create time. The driver's `DefaultAllowDirs` (the single source feeding
both `--add-dir` and nono `--allow`) must add all three, and `CreateSession`
**must capture the response body** so the cause is visible instead of a bare
`status 500`.

1. **`~/.opencode` install dir (read).** The server reads
   `~/.opencode/package.json` during session creation. Grant the whole
   `~/.opencode` dir. *Symptom:* `status 500: {"name":"UnknownError","data":
   {"message":"Error: EACCES: permission denied, open '~/.opencode/package.json'"}}`.

2. **`models.dev` egress.** At provider/session init the server fetches
   `https://models.dev/api.json` to resolve model metadata. Under the egress
   allowlist (provider hosts only) that 403s, the configured provider's models
   don't resolve, and `POST /session` 500s. Add `models.dev` to the egress
   domain list alongside the model-provider hosts. *Symptom (server log):*
   `Failed to fetch models.dev … status 403`.

3. **Config symlink targets.** Operators commonly symlink
   `~/.config/opencode/skills` (and sometimes `commands`/`agents`/`plugins`) to a
   checkout elsewhere (e.g. `~/.config/opencode/skills -> ~/code/AI/skills/...`).
   The profile grants `~/.config/opencode` — which covers the symlink *entry* but
   **not its target dir** — so the sandboxed server EACCESes when it follows the
   link to read a skill, and **bug-burndown / bugfix fail to load → the fix agent
   no-ops**. `DefaultAllowDirs` must resolve each of
   `skills`/`commands`/`agents`/`plugins`/`themes` under `~/.config/opencode` and
   grant any target that resolves *outside* the config dir. *Symptom:* sessions
   create OK but the burndown turn makes zero tool calls; server log shows
   `EACCES … skills/bug-burndown/SKILL.md` (or the skill is silently absent).

> **Capture the 500 body.** `CreateSession` (and any synchronous prompt path)
> must read the response body on a `>= 300` status and include it in the error —
> `fmt.Errorf("create session: status %d: %s", code, body)`. A bare "status 500"
> is undebuggable; the body carries the `EACCES`/`403`/store error that names the
> missing grant. This is the "don't discard the forensic record" rule applied to
> HTTP errors, and it is what turns a multi-hour blind stall into a one-line fix.

The general principle (same as the "grant the offending dir, don't strip the
config" rule): when the server EACCESes on a path it legitimately needs at
session-create, **grant that path** — don't isolate the config to dodge it.

### Preflight delta for the server backend

The preflight algorithm below is unchanged except: the network-profile ABI
branch is **not applicable** to the opencode profile (it sets
`network_profile: null`), so a Landlock ABI < 4 host does not downgrade the
opencode boundary — the filesystem sandbox and the always-on metadata block
still apply fully. Record `sandbox`, `permission_mode`, and the realized
`open_port` + any `allow_domain` hosts in the session manifest.

## opencode server boundary

When the harness drives an `opencode serve` instance (the default backend in
`references/opencode-server-integration.md`), the boundary is applied **once**
at server launch and inherited by every session, subagent, `bash` call, MCP
server, and LSP the server spawns. Do **not** use `--network-profile claude-code`
or any of the Claude Code device-file / `claude-cli-nodejs` grants here — those
are TUI-binary specifics. Use the `opencode-serve` profile instead.

### The `opencode-serve` profile

> **`opencode-serve` is a `-p` POLICY profile, NOT a `--network-profile`.**
> Launch with `nono run -p opencode-serve …`. Passing it as
> `--network-profile opencode-serve` is a silent, catastrophic bug: that flag
> expects a *network*-policy name, so nono applies **none** of the profile's
> filesystem/group grants. The server then runs without `/nix/store` (so LSP
> servers, the Bun runtime, and `libstdc++` don't resolve), without a coherent
> `~/.config/opencode` grant (so skills and plugins don't load), and the whole
> burndown/implementation half of the harness silently does nothing — exactly
> the vulnmapper 2026-06-13 failure. The `-p` profile is the boundary; only
> run-specific flags (`--allow-cwd`, `--open-port`, `--allow-domain`, an
> out-of-tree `--allow`) are added on top. Do **not** hand-roll a `--read` /
> `--allow` toolchain list to substitute for the profile — that drifts from the
> profile and re-creates the missing-`/nix/store` bug.
>
> **Pass the profile by ABSOLUTE PATH when the server runs under an isolated
> `XDG_CONFIG_HOME`.** The harness isolates *opencode's* config by setting
> `XDG_CONFIG_HOME=<project>/.harness/opencode-config` on the launched command
> — but that env is inherited by the `nono` wrapper too, and nono resolves a
> bare `-p <name>` from `$XDG_CONFIG_HOME/nono/profiles/`. The isolated dir has
> no `nono/profiles/`, so a bare name yields `nono: Profile not found:
> opencode-serve` and the server launches with no boundary/grants (vulnmapper
> 2026-06-13, second occurrence). nono's `-p` accepts `NAME_OR_PATH`; pass the
> **absolute path** to the operator's installed profile
> (`~/.config/nono/profiles/opencode-serve.json`, resolved via the operator's
> XDG before the harness overrides it for the child) so the lookup bypasses the
> isolated XDG profile-dir entirely. Isolate opencode's config, never nono's
> profile resolution. Keep the isolated config **under the project root** so
> `--allow-cwd` grants the server read access to its own `opencode.json` and
> the provisioned skills.

Ship this as a user profile at `~/.config/nono/profiles/opencode-serve.json`
(the canonical copy lives next to this doc at `references/opencode-serve.json`).
It extends `default` (which carries all the `deny_*` credential /
shell-history / browser-data groups and the Linux system-read core) and adds
only what a headless opencode server actually touches:

```json
{
  "meta": {
    "name": "opencode-serve",
    "version": "0.1.0",
    "description": "Least-privilege sandbox for a headless `opencode serve` instance driven by a harness. Replaces the claude-code profile/network-profile for opencode. No TUI assumptions.",
    "author": "harness-builder"
  },
  "extends": "default",
  "groups": {
    "include": ["nix_runtime", "opencode_linux", "git_config"]
  },
  "workdir": { "access": "readwrite" },
  "filesystem": {
    "allow": [
      "$HOME/.config/opencode",
      "$HOME/.local/share/opencode",
      "$HOME/.cache/opencode",
      "$HOME/.local/state/opencode"
    ]
  },
  "network": { "network_profile": null }
}
```

What each grant is for, and why it is the minimum:

| Grant | Purpose |
|---|---|
| `workdir.access: readwrite` (+ `--allow-cwd` at launch) | The project root. `opencode serve` roots at its launch cwd; nono auto-shares the CWD with `--allow-cwd`. For a worktree outside CWD, add `--allow <worktree>` from the same source variable. |
| group `nix_runtime` | Read `/nix/store`, `/run/current-system/sw`, nix profile dirs — needed on NixOS to resolve/exec the `opencode` binary, Bun, `libstdc++.so.6`, and **LSP servers (gopls, rust-analyzer, …)**. Harmless on non-Nix hosts (paths simply don't exist). |
| group `opencode_linux` | Read `~/.opencode/bin` for installer-based opencode installs. |
| group `git_config` | Read `~/.gitconfig` etc. so `git` tool calls inside sessions see the user's identity/ignore rules. |
| `allow $HOME/.config/opencode` | The operator's **real** global config: agents, plugins, **and ALL host skills + LSP definitions** (see opencode-server-integration.md § 4.1 — the server uses the real config so every skill and LSP is available, not a hand-picked subset). Writable because opencode rewrites caches here. |
| `allow $HOME/.local/share/opencode` | SQLite session/message store (`opencode.db`), `auth.json` (the model credential — auth lives here, not in config), and the server log dir. |
| `allow $HOME/.cache/opencode` | Plugin/node_modules and model-list caches — grant generously so all configured plugins/LSPs resolve. |
| `allow $HOME/.local/state/opencode` | Lock dir opencode `mkdir`s at startup (`locks/*.lock`); omitting it EACCESes and the server never reaches health (vulnmapper 2026-06-12). |
| `network.network_profile: null` | Clears any inherited network-profile. opencode talks to whatever provider the run configured (Anthropic, OpenAI, a GitLab Duo endpoint, a local model) — pinning `claude-code` would wrongly restrict egress to `api.anthropic.com`. nono's always-on proxy still blocks cloud-metadata (`169.254.169.254`) with no profile. To narrow egress to a known provider, add it via `--allow-domain <host>` and record it in the manifest. |

### Loosen capability, never secrets

The profile deliberately runs against the operator's **real** config so all
host skills, all configured LSPs, and the operator's agents are available (§4.1
of the server doc). That's a capability decision, not a secrets decision. The
two axes stay separate:

- **Loosen capability freely.** Grant the dirs that skills, LSP servers,
  plugins, and toolchains read or write. When a plugin or MCP server EPERMs on
  its cache (`~/.cache/uv`, `~/.npm`, a node_modules dir, an LSP's state dir),
  the fix is to **add that dir** to the profile's `filesystem.allow` (or a
  per-run `--allow`), not to strip the config. Widen until every configured
  skill and LSP resolves cleanly.
- **Keep the secret denies intact.** `default`'s `deny_*` groups (credentials,
  SSH keys, cloud tokens, shell history, browser data) and opencode's built-in
  `.env` deny stay on. Loosening capability never means granting `$HOME` at
  large or relaxing those groups. If a tool legitimately needs a credential,
  route it through `--credential`/env, never by widening a deny group.

So the audit question is not "is the config minimal?" but "can every host skill
and LSP load, while the `deny_*` groups still hold?". An over-isolated profile
(missing skills/LSPs, blanket-disabled LSP) is as much a bug as an over-broad
one (a relaxed `deny_*` group).

### Canonical opencode-server launch command

```bash
nono run --silent -p opencode-serve \
  --allow-cwd \
  [--allow <worktree-if-outside-cwd>] \
  --open-port <PORT> \
  [--allow-domain <provider-host>] \
  -- opencode serve --hostname 127.0.0.1 --port <PORT>
```

- `-p opencode-serve` selects the profile; no per-call enumeration of opencode's
  own state dirs is needed — the profile carries them.
- `--open-port <PORT>` grants bidirectional loopback TCP (connect + listen) and
  **must match** `opencode serve --port <PORT>` (single source variable, same
  invariant as `--add-dir` ↔ `--allow`).
- Set the child **cwd to the project root**, put it in its **own process group**,
  pass `OPENCODE_SERVER_PASSWORD` via env (never argv), and set
  `OPENCODE_DISABLE_AUTOUPDATE=1`.
- `wrap_with_nono`, when building an opencode-server argv, emits exactly this
  shape; the port and any extra `--allow` / `--allow-domain` come from one
  source variable.

### Preflight delta for the server backend

The network-profile ABI branch in the preflight is **not applicable** to the
opencode profile (it sets `network_profile: null`), so a Landlock ABI < 4 host
does not downgrade the opencode boundary — the filesystem sandbox and the
always-on metadata block still apply fully. Record `sandbox`, `permission_mode`,
the realized `open_port`, and any `allow_domain` hosts in the session manifest.

## Gotchas

**Debugging a denied path.** When a run hits EPERM, run this to see which
nono rule blocked it:

```bash
nono why --self --json
```

The output JSON has a `denied_by` field pointing at the specific policy rule.
Use it to decide whether to widen the allow list or fix the path reference.

**Disable Claude Code's own sandbox.** nono should be the one and only
boundary. Claude Code has a built-in sandbox that can conflict with nono.
Set `"allowUnsandboxedCommands": false` (or the equivalent for your Claude
Code version) so there's one mental model, not two.

**Version pinning.** Alpha software changes flags. Pin the version, confirm
the flags in this reference match what your installed version accepts, and
retest after bumps. `nono --help` is the ground truth; file an issue against
this skill if something has changed.

**Env-var survival.** nono preserves the parent process's env by default.
`BUG_BURNDOWN_HARNESS_DRIVEN=1`, `BUG_BURNDOWN_HARNESS_SESSION_ID=...`, and
`CLAUDE_BWRAP_TTY=0` all survive the nono wrap without extra flags.

## Session manifest fields

Every harness session manifest must include these fields so provenance tools
can verify what boundary was actually in effect:

```yaml
sandbox: "nono 0.4.2"             # or "none (--allow-unsandboxed)"
network_profile: "claude-code"    # or "none (Landlock ABI < 4)"
permission_mode: "bypassPermissions"   # or "acceptEdits"
```

For the burndown session manifest (`.bug-burndown/<id>/manifest.yaml`), these
fields land alongside the existing `session_id`, `start_time`, and `origin`
fields.

## How each reference uses this file

Don't restate the policy in a per-language reference — link here and document
only the language-specific argv plumbing.

- `implementation-rust.md` — `wrap_with_nono()` helper + Rust preflight wiring
- `implementation-go.md` — `wrapWithNono()` helper + Go preflight wiring
- `implementation-python.md` — `NonoTransport` SDK subclass + async preflight
- `implementation-ruby.md` — `wrap_with_nono()` module helper + preflight
- `implementation-nix.md` — `pkgs.nono` in flake inputs; pure-Nix genesis notes
- `runtime-rust-skeletons.md` — reviewer + burndown bridge wiring; CLI flag defaults
- `runtime-go-skeletons.md` — reviewer + burndown bridge wiring; CLI flag defaults
- `runtime-gotchas.md` — carries only a pointer stub; all sandbox content is here
