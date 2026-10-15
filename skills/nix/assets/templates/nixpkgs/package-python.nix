# pkgs/by-name/ex/example-cli/package.nix
# A Python application: run it, don't import it. Libraries go in
# pkgs/development/python-modules/<pname>/default.nix and are registered in
# python-packages.nix. Commit subjects for either use the package set
# prefix, for example `python3Packages.foo: 1.0 -> 1.1`.
{
  lib,
  python3Packages,
  fetchFromGitHub,
  versionCheckHook,
}:

python3Packages.buildPythonApplication (finalAttrs: {
  pname = "example-cli";
  version = "1.2.3";
  # Builds from pyproject.toml. The older `format = "pyproject"` is superseded.
  pyproject = true;

  src = fetchFromGitHub {
    owner = "example";
    repo = "example-cli";
    tag = "v${finalAttrs.version}";
    hash = lib.fakeHash;
  };

  __structuredAttrs = true;

  # Whatever pyproject.toml's [build-system] table asks for.
  build-system = with python3Packages; [ hatchling ];

  # Runtime dependencies from [project] dependencies.
  dependencies = with python3Packages; [
    click
    rich
  ];

  nativeCheckInputs = [ python3Packages.pytestCheckHook ];

  # buildPythonApplication turns doInstallCheck on, so this hook runs
  # `example-cli --version` after install.
  nativeInstallCheckInputs = [ versionCheckHook ];

  # Imports each module in its own phase; it catches a broken closure.
  pythonImportsCheck = [ "example_cli" ];

  # Python builders attach nix-update-script as passthru.updateScript by
  # default, so there's nothing to add for it.

  meta = {
    description = "Command-line tool that does a thing";
    homepage = "https://github.com/example/example-cli";
    changelog = "https://github.com/example/example-cli/releases/tag/${finalAttrs.src.tag}";
    license = lib.licenses.mit;
    maintainers = [ ];
    mainProgram = "example-cli";
  };
})
