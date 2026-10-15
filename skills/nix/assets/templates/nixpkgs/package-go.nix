# pkgs/by-name/ex/example/package.nix
# A Go program built with buildGoModule. buildGoPackage was removed.
{
  lib,
  buildGoModule,
  fetchFromGitHub,
  versionCheckHook,
  nix-update-script,
}:

buildGoModule (finalAttrs: {
  pname = "example";
  version = "1.2.3";

  src = fetchFromGitHub {
    owner = "example";
    repo = "example";
    tag = "v${finalAttrs.version}";
    hash = lib.fakeHash;
  };

  # Hash of the fetched module set. Use lib.fakeHash, build, paste the hash
  # from the error. `null` means "use the committed vendor/ directory", so it
  # isn't a way to make the build print a hash.
  vendorHash = lib.fakeHash;

  __structuredAttrs = true;

  # Without this every package in the module builds, test helpers included.
  subPackages = [ "cmd/example" ];

  ldflags = [ "-X main.version=${finalAttrs.version}" ];

  # Tests run by default. Skip by name and say why; -skip takes a regex.
  # checkFlags = [ "-skip=^TestNeedsNetwork$" ];

  doInstallCheck = true;
  nativeInstallCheckInputs = [ versionCheckHook ];

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "Tool that does a thing";
    homepage = "https://github.com/example/example";
    changelog = "https://github.com/example/example/releases/tag/${finalAttrs.src.tag}";
    license = lib.licenses.mit;
    maintainers = [ ];
    mainProgram = "example";
  };
})
