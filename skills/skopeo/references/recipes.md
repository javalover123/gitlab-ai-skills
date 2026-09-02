# skopeo recipes

Companion to [`../SKILL.md`](../SKILL.md). The two standing rules still apply to
everything here: pass `--override-os linux`, and pass `--no-tags` unless tags are
the question.

## Pull one field instead of a whole document

`--format` takes a Go template, and `{{json .X}}` emits JSON for non-scalars:

```
skopeo inspect --override-os linux --no-tags --format '{{.Digest}}' docker://alpine:3.20
skopeo inspect --override-os linux --no-tags --format '{{json .Labels}}' docker://alpine:3.20
```

## Enumerate the platforms in a manifest index

`--raw` returns the index verbatim; filter the `unknown/unknown` entries, which
are attestation manifests, not platforms:

```
skopeo inspect --raw docker://alpine:3.20 \
  | jq -r 'if .manifests then (.manifests[] | select(.platform.os != "unknown")
           | "\(.platform.os)/\(.platform.architecture)\(.platform.variant // "")  \(.digest)")
           else "single manifest, no index: \(.mediaType)" end'
```

The `if .manifests` guard matters: not every reference is an index. A
single-platform image returns a bare manifest with no `.manifests` key, and an
unguarded `.manifests[]` fails on it.

This is also the only place the per-platform manifest digest appears — see the
digest-semantics section in `SKILL.md`.

## Total download size, in bytes (compressed layers)

```
skopeo inspect --override-os linux --no-tags docker://alpine:3.20 \
  | jq '[.LayersData[].Size] | add'
```

## Inspect one specific platform rather than this host's architecture

```
skopeo inspect --override-os linux --override-arch amd64 --no-tags docker://alpine:3.20
```

## Notes

- `--raw` needs no `--override-os`: it returns bytes as stored without selecting
  an instance. Only instance-selecting reads hit the host-OS default.
- `--no-tags` still emits a `RepoTags` key, just empty — readers won't break.
- `manifest-digest` takes a *file*, not a reference; use `/dev/stdin` to pipe:
  `skopeo inspect --raw docker://IMG | skopeo manifest-digest /dev/stdin`.
- `--retry-times N` is worth adding on flaky or rate-limited registries; backoff
  is exponential unless `--retry-delay` is set.

## Verifying this skill

Verified against skopeo 1.24.0 (homebrew, darwin/arm64); `skopeo <cmd> --help` is
authoritative if anything here disagrees. Smoke test, no credentials needed: the
first `--format '{{.Digest}}'` call above should print one line, and should fail
with the darwin error if `--override-os linux` is dropped.
