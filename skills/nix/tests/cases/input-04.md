# Test Case: New project with no existing Nix

Starting a new Go HTTP service (`go.mod`, one `cmd/server` package, Go 1.23). The team uses plain
`go build` and `go test` today and a Makefile. Set up Nix for reproducible builds and a dev
environment, keeping the day-to-day workflow the same. There are no existing Nix files.
