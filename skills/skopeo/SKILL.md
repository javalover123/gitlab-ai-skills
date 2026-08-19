---
name: skopeo
description: "Interrogate container images and registries with skopeo — read manifests, configs, layers, platforms, and tags over the network without pulling the image or running a daemon. Use when asked about an image's digest, platforms, labels, entrypoint, layers, size, or available tags, instead of reaching for docker pull / docker inspect."
version: 0.1.0
license: MIT
category: Shell & Environment
compatibility: opencode
user-invocable: true
metadata:
  audience: developers
  workflow: containers
  keywords: container, image, registry, manifest, digest, tags, oci
allowed-tools:
  - Read
  - Bash(skopeo inspect *)
  - Bash(skopeo list-tags *)
  - Bash(skopeo manifest-digest *)
  - Bash(skopeo login --get-login *)
  - Bash(skopeo --version)
  - Bash(jq *)
---

# skopeo — read image metadata straight from a registry

`skopeo` answers questions about container images by talking to the registry
directly (https://github.com/podman-container-tools/skopeo#commands). No pull, no
daemon, no local storage: a question about a 2 GB image costs one HTTP round trip
for a few KB of JSON. Output is already machine-readable, so pipe it to `jq`
rather than parsing prose.

**This skill is read-only.** It covers `inspect`, `list-tags`, and
`manifest-digest` only. It does NOT cover `copy`, `sync`, or `delete` — if asked
to move, mirror, or remove an image, say that this skill doesn't do that and get
explicit confirmation before running any mutating skopeo command.

## Two standing rules

1. **Always pass `--override-os linux`.** skopeo defaults to the host OS when
   picking an instance out of a manifest index, so on darwin a Linux-only image
   (i.e. almost all of them) fails outright: `no image found in image index for
   architecture "arm64", variant "v8", OS "darwin"`. There is no env-var
   equivalent, so the flag goes on every call.
2. **Always pass `--no-tags` unless tags are the actual question.** By default
   `inspect` inlines the repository's entire tag list into every response. On
   `library/alpine` that is 4751 bytes vs 771 with `--no-tags` — 6× — and repos
   with thousands of tags are far worse. Use `list-tags` when you want tags.

Put both flags *after* the subcommand (`skopeo inspect --override-os linux …`).
They are persistent flags so either position works, but this position keeps the
command matching the `Bash(skopeo inspect *)` allowlist entry above.

## Which command answers which question

| Question | Command |
| --- | --- |
| Digest, labels, env, layer sizes, created date | `skopeo inspect --override-os linux --no-tags docker://IMG` |
| Entrypoint, cmd, user, workdir, build history | `skopeo inspect --config --override-os linux docker://IMG` |
| Which platforms does this image support | `skopeo inspect --raw docker://IMG` + `jq` |
| What tags exist in this repo | `skopeo list-tags docker://REPO` |
| Digest of a manifest file already on disk | `skopeo manifest-digest FILE` |
| Am I authenticated to this registry | `skopeo login --get-login REGISTRY` |

`IMG` is a transport-prefixed reference. `docker://` is the registry; local
alternatives include `containers-storage:`, `docker-archive:`, `oci:`,
`oci-archive:`, and `dir:`. Bare names are not accepted — the transport prefix is
mandatory.

For `--format` templates, platform enumeration, image size, and per-platform
inspection, see [references/recipes.md](references/recipes.md).

## Digest semantics — the subtle one

`.Digest` is the digest of the **top-level object at that reference**, which for
a multi-arch tag is the index. It does not change with `--override-arch`:
`--override-arch amd64` and `--override-arch s390x` both report
`sha256:d9e853e8…` for `alpine:3.20`, matching `manifest-digest` of the raw
index. So:

- Pinning a tag for reproducible deploys → `--format '{{.Digest}}'`. Correct,
  and stays multi-arch.
- Wanting the per-platform manifest digest → it is only in `--raw`'s
  `.manifests[].digest`. Do not expect `--override-arch` to surface it.

## Errors and exit codes

Exit `0` on success, non-zero otherwise — but the split is not tidy: `inspect`
failing to resolve an image instance and `manifest unknown` exit `2`, while
`list-tags`, `manifest-digest`, bad flags, and an unparseable reference
(`unknown transport "alpine"`) exit `1`. Read the message, not just the code.
There is also no distinct "empty result" code, so check the payload: a readable
repo yields `0` and a `Tags` array that may be short or empty.

| stderr message | Meaning |
| --- | --- |
| `no image found in image index for … OS "darwin"` | Rule 1 was skipped; add `--override-os linux` |
| `manifest unknown` | Repo is readable, that tag/digest isn't in it |
| `requested access to the resource is denied` | Repo is missing **or** private and you're unauthenticated — registries deliberately conflate these, so don't report "does not exist" from this alone |
| `unauthorized: authentication required` | Credentials needed or expired; `skopeo login REGISTRY` |

## Auth

Assume the user is already authenticated. skopeo reads, in order, `--authfile`,
`$REGISTRY_AUTH_FILE`, `$XDG_RUNTIME_DIR/containers/auth.json`,
`~/.config/containers/auth.json`, then `~/.docker/config.json` — so an existing
`docker login`, `podman login`, or `skopeo login` already works.

**Never put credentials in a command line.** No `--creds user:password`, no
`--password`; they land in shell history and in the transcript. On an auth
failure, report it and ask the user to run the login themselves — suggest they
type `! skopeo login REGISTRY` so the interactive prompt works. `--no-creds`
forces an anonymous read; `skopeo login --get-login REGISTRY` checks identity
without leaking anything (non-zero + `not logged into REGISTRY` when absent).
