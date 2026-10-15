# Test Case: Dated advice from an old PR

I found this snippet in an old blog post and a nixpkgs PR from a few years ago and want to reuse it
for a module option. Is it fine to copy?

```nix
options.services.foo.enable = lib.mkEnableOption "foo";
options.services.foo.extraArgs = lib.mkOption {
  type = lib.types.str;
  default = "";
  description = lib.mdDoc "Extra arguments for `foo`.";
};
config = lib.mkIf config.services.foo.enable {
  environment.systemPackages = lib.optionals pkgs.stdenv.isLinux [ pkgs.foo ];
};
```
