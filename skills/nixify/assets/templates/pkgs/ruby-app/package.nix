# Ruby app via bundlerEnv. Regenerate gemset.nix with `bundle lock && bundix`.
{ bundlerEnv, ruby_3_3 }:
bundlerEnv {
  name = "REPLACE_ME-gems";
  ruby = ruby_3_3;
  gemdir = ../../.;                 # dir with Gemfile, Gemfile.lock, gemset.nix
  groups = [ "default" "production" "development" "test" ];
  # gemConfig = pkgs.defaultGemConfig // { pg = a: { buildInputs = [ pkgs.postgresql ]; }; };
}
