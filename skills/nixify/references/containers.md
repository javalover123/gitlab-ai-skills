# Containers — nix2container vs dockerTools

Expose container builds as **scoped outputs** (`packages.<system>.<name>-image`).
Two viable backends:

| Aspect | `dockerTools` (`buildLayeredImage` / `streamLayeredImage`) | **nlewo/nix2container** |
|---|---|---|
| Output | builds (or streams) a tarball image; auto-layered by closure | **archive-less**: emits JSON describing the image; does **not** write tarballs to the Nix store |
| Layer control | automatic layering; `streamLayeredImage` avoids materializing the full tarball | explicit `buildLayer { deps = [ … ]; }` — isolate app vs deps |
| Rebuild/push speed | re-pushes layers unless skopeo dedups | **fast**: skopeo skips already-pushed layers; this is the design goal |
| Reproducibility | deterministic; pinned inputs | deterministic; per-layer metadata |
| Extra flake input | none (nixpkgs-native) | yes (`nix2container`) |
| Registry push | `docker load` / skopeo; `streamLayeredImage` pipes | skopeo `copyToRegistry`-style |

## Recommendation

- **Push frequently to a registry / want fast iterate-push cycles →
  nix2container.** Layer skipping makes repeated pushes cheap.
- **Want zero extra inputs / nixpkgs-native →
  `dockerTools.streamLayeredImage`.** Streams without materializing a big tarball
  in the store.

## nix2container

```nix
# flake input
inputs.nix2container.url = "github:nlewo/nix2container";

# pkgs/myapp-image/package.nix  (called with the nix2container builder injected)
{ nix2container, myapp, cacert, runtimeDeps ? [ ] }:
nix2container.buildImage {
  name = "registry.example.com/myapp";
  tag = "latest";
  config = {
    Cmd = [ "${myapp}/bin/myapp" ];
    Env = [ "SSL_CERT_FILE=${cacert}/etc/ssl/certs/ca-bundle.crt" ];
  };
  # isolate the heavy runtime in its own layer for cache reuse:
  layers = [ (nix2container.buildLayer { deps = runtimeDeps; }) ];
  copyToRoot = [ cacert ];
}
```

## dockerTools.streamLayeredImage

```nix
{ dockerTools, myapp, cacert }:
dockerTools.streamLayeredImage {
  name = "myapp";
  tag = "latest";
  contents = [ myapp cacert ];
  config.Cmd = [ "${myapp}/bin/myapp" ];
}
# build then load: `nix build .#myapp-image && ./result | docker load`
```

## Common pitfalls

- **TLS:** put `cacert` in the image and set `SSL_CERT_FILE` /
  `NIX_SSL_CERT_FILE`, or outbound HTTPS fails with no CA bundle.
- **Layer strategy:** isolate the language runtime / `node_modules` / Python env
  / large deps in a dedicated layer so app-only changes don't invalidate it.
- **Non-root user / tmp dirs:** `dockerTools` images are minimal — add
  `dockerTools.fakeNss`, a writable `/tmp`, and a user if the app needs them.
- **Reproducibility:** both backends honor pinned inputs; avoid `tag = "latest"`
  for anything you need to pin — derive the tag from a content hash or version.
