# Ruby harness builder

Genesis-side orchestration gem for Ruby projects. Smaller than the
Rust / Go / Python variants because Ruby's role in genesis is usually
as the *implementation* language with the harness itself in Python or
shell — pure-Ruby genesis is uncommon. But when the project is Ruby-
primary (Rails app, Sinatra service, Sidekiq worker fleet), this is
the scaffold.

## Gem layout

```
<project>-genesis/
├── Gemfile
├── <project>-genesis.gemspec
├── README.md
├── exe/
│   └── <project>-genesis             # CLI entry
└── lib/<project>/genesis/
    ├── version.rb
    ├── cli.rb                        # outer loop + CLI
    ├── state.rb                      # .iteratotron/state.json IO + atomic-rename
    ├── bootstrap.rb                  # Phase 0
    ├── gap_analysis.rb               # Phase 1
    ├── plan.rb                       # Phase 2
    ├── inner_loop.rb                 # Phase 3
    ├── constitution_check.rb         # gates each iteratotron dispatch
    ├── streaming.rb                  # claude -p stream-json consumer
    ├── adversarial_review.rb         # Phase 7
    ├── harness_runner.rb             # Tier-1/2/3 invocation
    │                                 #  ↳ flake.nix present ⇒ gates via
    │                                 #    `nix develop --command` (pinned ruby
    │                                 #    + rubocop). See implementation-nix.md
    │                                 #    § "Gate-execution contract".
    ├── done_predicate.rb             # Phase 4
    └── slsa.rb                       # in-toto + cosign attestation
```

## Gemspec essentials

```ruby
# <project>-genesis.gemspec
Gem::Specification.new do |spec|
  spec.name          = "<project>-genesis"
  spec.version       = "0.1.0"
  spec.required_ruby_version = ">= 3.2"

  spec.executables   = ["<project>-genesis"]

  spec.add_dependency "thor", "~> 1.3"
  spec.add_dependency "concurrent-ruby", "~> 1.3"
  spec.add_dependency "json"
  spec.add_dependency "sorbet-runtime"          # optional, but matches project's static type strategy

  spec.add_development_dependency "rspec", "~> 3.13"
  spec.add_development_dependency "mutant-rspec", "~> 0.13"     # mutation testing for the harness itself
  spec.add_development_dependency "rubocop", "~> 1.69"
  spec.add_development_dependency "brakeman"
end
```

## exe/genesis — CLI

```ruby
#!/usr/bin/env ruby
# frozen_string_literal: true

require "<project>/genesis/cli"
<Project>::Genesis::CLI.start(ARGV)
```

## lib/<project>/genesis/cli.rb

```ruby
# frozen_string_literal: true

require "thor"
require_relative "bootstrap"
require_relative "gap_analysis"
require_relative "plan"
require_relative "inner_loop"
require_relative "done_predicate"
require_relative "state"

module <Project>
  module Genesis
    class CLI < Thor
      class_option :parallel, type: :numeric, default: 2
      class_option :inner, type: :numeric, default: 3
      # 7-day default: a converging build-system / E2E run is measured in days.
      # Size to the workload (SKILL.md "Size the deadlines to the workload");
      # drop to 28_800 (8h) only for a pure fast-feedback project.
      class_option :time, type: :numeric, default: 604_800
      class_option :budget_usd, type: :numeric, default: 100.0
      class_option :resume, type: :string
      class_option :dry_run, type: :boolean, default: false

      desc "run", "drive the project from documentation to done predicate"
      def run
        state = if options[:resume]
                  State.resume(options[:resume])
                else
                  State.new_session(
                    parallel_outer: options[:parallel],
                    parallel_inner: options[:inner],
                    time_budget_seconds: options[:time],
                    cost_budget_usd: options[:budget_usd],
                  )
                end

        unless options[:resume]
          Bootstrap.run(state)
          GapAnalysis.run(state)
          Plan.run(state)
        end

        if options[:dry_run]
          puts "dry run — plan written, no dispatch"
          return
        end

        InnerLoop.run(state)
        DonePredicate.evaluate_and_attest(state)
      end
    end
  end
end
```

## lib/<project>/genesis/streaming.rb

Ruby's `Open3.popen3` is the equivalent of Rust's `Command` /
Go's `exec.Command`. The watchdog pattern is the same — detect the
`result` event inline, fire a grace timer, escalate SIGTERM → SIGKILL
targeting the nono PID (nono forwards the signal to claude). See
`references/nono-integration.md` for the full sandbox contract.

```ruby
# frozen_string_literal: true

require "json"
require "open3"
require "time"
require "fileutils"

module <Project>
  module Genesis
    module Streaming
      module_function

      # Run once at harness startup. Returns a hash:
      #   { nono_version:, network_profile:, permission_mode: }
      # See references/nono-integration.md for the preflight algorithm.
      def check_sandbox(allow_unsandboxed: false)
        version_out, _err, status = Open3.capture3("nono", "--version")
        unless status.success?
          if allow_unsandboxed
            warn <<~BANNER
              ┌─────────────────────────────────────────────────────┐
              │  RUNNING UNSANDBOXED — nono not found on PATH       │
              │  permission_mode = acceptEdits (NOT bypassPerms)    │
              │  Install: brew install nono                         │
              │           nix shell nixpkgs#nono                    │
              │           .deb from github.com releases             │
              └─────────────────────────────────────────────────────┘
            BANNER
            return { nono_version: nil, network_profile: nil, permission_mode: "acceptEdits" }
          end
          raise <<~MSG
            nono is required but not found on PATH.
            Install: brew install nono  |  nix shell nixpkgs#nono
                     or .deb from github.com releases
            Pass --allow-unsandboxed to proceed without the sandbox
            (keeps permission_mode=acceptEdits; not recommended for
            unattended loops).
          MSG
        end

        setup_out, _serr, _sstatus = Open3.capture3("nono", "setup", "--check-only")
        abi = setup_out[/landlock_abi:\s*(\d+)/, 1]&.to_i
        network_profile = if abi && abi >= 4
          "claude-code"
        else
          warn "[sandbox] Landlock ABI < 4 — dropping --network-profile claude-code"
          nil
        end

        { nono_version: version_out.strip, network_profile:, permission_mode: "bypassPermissions" }
      end

      # Prepend nono run --silent to a claude argv, deriving --allow entries
      # from the same allow_dirs that become --add-dir entries.
      # The --add-dir ↔ --allow invariant: nono-integration.md.
      def wrap_with_nono(claude_argv, allow_dirs:, read_dirs:, network_profile:)
        argv = ["nono", "run", "--silent"]
        argv += ["--network-profile", network_profile] if network_profile
        allow_dirs.each { |d| argv += ["--allow", d] }
        read_dirs.each  { |d| argv += ["--read",  d] }
        argv + ["--"] + claude_argv
      end

      def dispatch(prompt:, log_dir:, model:, add_dirs:, disallowed_tools:,
                   sandbox_verdict:,
                   max_turns: 80, max_budget_usd: 20.0, grace_secs: 30)
        FileUtils.mkdir_p(log_dir)
        log_path = File.join(log_dir, "#{Time.now.to_i}.jsonl")

        claude_argv = [
          "claude", "-p", prompt,
          "--output-format", "stream-json",
          "--verbose",
          "--include-partial-messages",
          "--permission-mode", sandbox_verdict[:permission_mode],
          "--model", model,
          "--max-turns", max_turns.to_s,
          "--max-budget-usd", max_budget_usd.to_s,
        ]
        add_dirs.each { |d| claude_argv.push("--add-dir", d) }
        disallowed_tools.each { |t| claude_argv.push("--disallowed-tools", t) }

        # Derive --allow from the same source as add_dirs + shared dotfile dirs.
        # The --add-dir ↔ --allow invariant: nono-integration.md.
        final_argv = if sandbox_verdict[:permission_mode] == "bypassPermissions"
          allow_dirs = add_dirs + %w[.bug-burndown .test-effectiveness .iteratotron]
          read_dirs  = [
            File.expand_path("~/.rbenv/shims"),
            File.expand_path("~/.gem"),
          ]
          wrap_with_nono(claude_argv,
            allow_dirs: allow_dirs,
            read_dirs: read_dirs,
            network_profile: sandbox_verdict[:network_profile])
        else
          claude_argv
        end

        result = nil
        # CLAUDE_BWRAP_TTY=0 forces --pipe in any bwrap wrapper on PATH.
        # nono preserves the parent env so this survives the sandbox wrap.
        env = { "CLAUDE_BWRAP_TTY" => "0" }
        # wait_thr.pid is the nono PID when sandboxed; nono forwards signals
        # to claude so the watchdog's Process.kill targets the right process.
        Open3.popen3(env, *final_argv) do |stdin, stdout, _stderr, wait_thr|
          stdin.close          # wrappers waiting on EOF need this
          watchdog_thread = nil

          File.open(log_path, "w") do |log|
            stdout.each_line do |line|
              log.write(line)              # tee BEFORE filtering
              log.flush
              if line.include?(%q("type":"result"))
                watchdog_thread ||= Thread.new do
                  sleep(grace_secs)
                  Process.kill(:TERM, wait_thr.pid) rescue nil
                  sleep(10)
                  Process.kill(:KILL, wait_thr.pid) rescue nil
                end
              end
            end
          end

          status = wait_thr.value
          watchdog_thread&.kill
          raise "subprocess failed: #{status.exitstatus}" unless status.success?

          result = parse_result(log_path)
        end
        { log_path: log_path, **result }
      end

      def parse_result(log_path)
        last_result = File.foreach(log_path).filter_map do |line|
          parsed = JSON.parse(line, symbolize_names: true) rescue nil
          parsed if parsed&.fetch(:type) == "result"
        end.last
        last_result || {}
      end
    end
  end
end
```

## inner_loop.rb (pseudocode)

```ruby
require "concurrent"

module <Project>
  module Genesis
    module InnerLoop
      module_function

      def run(state)
        until state.terminal? || state.budget_exhausted?
          dispatchable = state.select_dispatchable(state.budgets.parallel_outer)
          futures = dispatchable.map do |scope|
            Concurrent::Future.execute do
              check = ConstitutionCheck.run(scope)
              if check.pass?
                worktree = state.create_worktree(scope)
                prompt = render_iteratotron_prompt(scope, state)
                result = Streaming.dispatch(
                  prompt: prompt, log_dir: worktree.log_dir,
                  model: "haiku", add_dirs: state.add_dirs,
                  disallowed_tools: ["WebSearch"])
                state.record_cost(scope.id, :iteratotron, result)
                verdict = AdversarialReview.run(scope, worktree)
                case verdict.kind
                when :approved then state.merge_worktree(scope, worktree)
                when :insufficient then state.requeue_scope(scope, verdict.lessons)
                when :needs_human then state.park_for_human(scope, verdict.reason)
                end
                HarnessRunner.run_applicable_tiers(scope, state.harness_vector)
              else
                state.park_for_human(scope, check.violations)
              end
            end
          end
          futures.each(&:wait)
          InnerLoop.dispatch_burndown(state) if state.bug_queue.any?
          state.fsync!
        end
      end
    end
  end
end
```

## Caveat — Mutant license

Mutation testing of the genesis harness itself uses Mutant
(Markus Schirp). Mutant requires a commercial licence for non-OSS use.
For an open-source `<project>-genesis` gem, the OSS licence applies;
for a closed-source enterprise project, budget for Mutant's commercial
licence or skip mutation testing of the harness (not of the project
under test, which uses iterate's normal Tier-1 gates).

---

## lib/<project>/genesis/opencode_server.rb — opencode server driver (opencode-server backend)

Generated alongside `streaming.rb` when `agent_host: opencode-server` is selected.
Full skeleton with all HTTP+SSE contracts, lifecycle state machine, and the
`each_event` / `shutdown` implementations is in
`references/opencode-server-integration.md §6.3`. Uses only Ruby stdlib (`net/http`,
`json`, `uri`, `timeout`) — no new gem dependencies.

Add `opencode_server.rb` to the gem layout under `lib/<project>/genesis/` and
`require_relative "opencode_server"` from `inner_loop.rb`.

The `OpencodeServer` class surface (from the §6.3 skeleton):

```ruby
class OpencodeServer
  attr_reader :base_url, :password

  def self.launch(project_root:, port:, password:) → OpencodeServer
  def wait_healthy(budget_s)
  def create_session(title) → String
  def prompt_async(session, agent, text)
  def respond_permission(session, perm, decision)   # decision ∈ "once","always","reject"
  def todo_empty?(session) → Boolean
  def abort(session)
  def each_event { |kind, data| :stop | nil }       # SSE stream; run on its own thread
  def shutdown(grace_s = 10)
end
```

## Agent host backend switch

Add to `streaming.rb` (module constant):

```ruby
AGENT_HOSTS = %w[claude-stream opencode-server].freeze
```

Add `agent_host` (default `"claude-stream"`) and `opencode_server` (an
`OpencodeServer` or `nil`) to the `State` class.

Replace the `Streaming.dispatch(...)` call site in `inner_loop.rb`:

```ruby
case state.agent_host
when "claude-stream"
  # existing path — unchanged
  result = Streaming.dispatch(
    prompt: prompt, log_dir: worktree.log_dir,
    model: "haiku", add_dirs: state.add_dirs,
    disallowed_tools: ["WebSearch"], sandbox_verdict: state.sandbox_verdict
  )
  state.record_cost(scope.id, :iteratotron, result)

when "opencode-server"
  server  = state.opencode_server
  session = server.create_session(scope.title)
  server.prompt_async(session, "build", prompt)
  wait_session_complete(server, session)
end
```

Three-way completion detection (required by `opencode-server-integration.md §5`):

```ruby
def wait_session_complete(server, session_id)
  msg_complete = false
  idle         = false

  server.each_event do |kind, data|
    case kind
    when "message.updated"
      info = data["info"] || {}
      if info["sessionID"] == session_id &&
         info.dig("time", "completed") &&
         info["error"].nil?
        msg_complete = true
      end
    when "session.idle"
      idle = true if data["sessionID"] == session_id
    when "permission.updated"
      # match allowlist → server.respond_permission(session_id, data["id"], decision)
      # append every decision to the run manifest audit log
    when "session.error"
      raise "session error: #{data['error']}"
    end
    :stop if msg_complete && idle
  end

  # third leg of the AND: todo must be empty
  raise "todo non-empty after idle for #{session_id}" unless server.todo_empty?(session_id)
end
```

## lib/<project>/genesis/cli.rb — server lifecycle (agent_host: opencode-server)

Add to `CLI`:

```ruby
class_option :agent_host, type: :string, default: "claude-stream",
             desc: "agent host backend: claude-stream | opencode-server"
class_option :opencode_port, type: :numeric, default: 7654,
             desc: "port for opencode serve (opencode-server backend only)"
```

Server lifecycle in the `run` command:

```ruby
server = if options[:agent_host] == "opencode-server"
  password = ENV.fetch("OPENCODE_SERVER_PASSWORD") { SecureRandom.uuid }
  OpencodeServer.launch(
    project_root: Dir.pwd,
    port: options[:opencode_port],
    password: password,
  )
end

state.agent_host     = options[:agent_host]
state.opencode_server = server

begin
  InnerLoop.run(state)
  DonePredicate.evaluate_and_attest(state)
ensure
  # DISPOSE on every exit path — success, error, or exception
  server&.shutdown
end
```

**Python and Nix harnesses** do not gain the `opencode-server` backend in this
release. Document in the generated README; note as a follow-up.
