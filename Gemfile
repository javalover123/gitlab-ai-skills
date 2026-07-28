# Gemfile for the danger-review CI job.
#
# The danger-review CI component generates a Gemfile on the fly when the repo
# doesn't provide one ([[ -f "Gemfile" ]] || bundle init && bundle add
# gitlab-dangerfiles). Without a lockfile that resolution floats to the latest
# gems, so the job broke the moment the `git` gem published 5.0.0
# (2026-07-28): danger 9.6.0 declares `git >= 1.13` with no upper bound, but
# git 5.0.0 redefines Git::Base in a way danger's scm_source/git_repo.rb can't
# load, failing with "Base is not a class (TypeError)".
#
# Pin `git` below 5 until danger ships a release compatible with it.
# See https://github.com/danger/danger for upstream progress.

source "https://rubygems.org"

gem "gitlab-dangerfiles"
gem "git", "< 5"
