# Tool Installation Guide

This guide covers installing and configuring tools for profiling Rust compilation memory usage.

## Required Tools

### 1. Rust Nightly Toolchain

**Via Nix (recommended):**

Add a `flake.nix` to your project (or extend an existing one), then run
`nix develop`:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    rust-overlay.url = "github:oxalica/rust-overlay";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, rust-overlay, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; overlays = [ (import rust-overlay) ]; };
        rustToolchain = pkgs.rust-bin.nightly.latest.default.override {
          extensions = [ "rust-src" ];
        };
      in {
        devShells.default = pkgs.mkShell {
          buildInputs = [ rustToolchain pkgs.heaptrack pkgs.cargo-llvm-lines pkgs.inferno ];
        };
      });
}
```

**Via rustup:**

```bash
# Install nightly
rustup toolchain install nightly

# Set as override for current directory
rustup override set nightly

# Verify
rustc --version
# Should show: rustc 1.XX.0-nightly (hash YYYY-MM-DD)
```

### 2. measureme Tools

Includes `crox`, `summarize`, and `inferno` for analyzing self-profile data.

**Via Nix:**

Add to flake.nix buildInputs:
```nix
pkgs.inferno
```

**Via cargo:**

```bash
cargo install inferno

# Clone measureme for crox
git clone https://github.com/rust-lang/measureme.git
cd measureme
cargo install --path crox
cargo install --path summarize
```

Binaries installed to `~/.cargo/bin/` (ensure it's in PATH).

### 3. heaptrack (Linux only)

**Via Nix:**

```nix
pkgs.heaptrack
```

**Via package manager:**

```bash
# Ubuntu/Debian
sudo apt install heaptrack

# Fedora
sudo dnf install heaptrack

# Arch
sudo pacman -S heaptrack
```

**macOS alternative:**

Heaptrack isn't available on macOS. Use Instruments instead:

```bash
# Profile with Instruments
instruments -t "Allocations" -D trace.trace cargo build --release

# Or use valgrind (less accurate)
brew install valgrind
valgrind --tool=massif cargo build --release
```

### 4. cargo-llvm-lines

**Via Nix:**

```nix
pkgs.cargo-llvm-lines
```

**Via cargo:**

```bash
cargo install cargo-llvm-lines
```

### 5. Chrome/Chromium (for trace visualization)

**Via Nix:**

```nix
pkgs.chromium
```

**Via package manager:**

```bash
# Ubuntu/Debian
sudo apt install chromium-browser

# Fedora
sudo dnf install chromium

# macOS
brew install --cask chromium
```

## Verification

After installation, verify all tools are available:

```bash
# Check nightly
rustc --version | grep nightly

# Check measureme tools
inferno --version
crox --help
summarize --help

# Check heaptrack (Linux)
heaptrack --version

# Check cargo-llvm-lines
cargo llvm-lines --help
```

## Configuration

### Environment Variables

For optimal profiling results:

```bash
# Disable incremental compilation (for accurate profiling)
export CARGO_INCREMENTAL=0

# Enable debug symbols in release builds (for profiling)
export CARGO_PROFILE_RELEASE_DEBUG=true

# Increase stack size if needed
export RUST_MIN_STACK=16777216  # 16MB
```

Add to shell profile (~/.bashrc, ~/.zshrc):

```bash
# Rust profiling environment
export CARGO_INCREMENTAL=0
export CARGO_PROFILE_RELEASE_DEBUG=true
```

### Cargo Configuration

Create or edit `~/.cargo/config.toml`:

```toml
[build]
# Use all CPU cores for compilation
jobs = 8  # Adjust based on your CPU

[profile.release]
# Enable debug symbols without debug overhead
debug = true
```

## Platform-Specific Notes

### Linux

All tools available. Heaptrack provides the most detailed memory profiling.

**SELinux/AppArmor:**

If running on hardened systems, you may need to allow ptrace:

```bash
# Temporary (until reboot)
sudo sysctl -w kernel.yama.ptrace_scope=0

# Permanent
echo 'kernel.yama.ptrace_scope = 0' | sudo tee -a /etc/sysctl.d/10-ptrace.conf
sudo sysctl -p /etc/sysctl.d/10-ptrace.conf
```

### macOS

Heaptrack unavailable. Use Instruments or valgrind as alternatives.

**Instruments:**

```bash
# Record allocation trace
instruments -t Allocations -D trace.trace cargo build --release

# Open in Instruments.app
open trace.trace
```

**Disable SIP for valgrind (not recommended):**

Valgrind requires SIP disabled on modern macOS. Consider using Linux VM instead.

### Windows

Limited support for memory profiling tools.

**Windows Performance Analyzer (WPA):**

See [rustc dev guide WPA section](https://rustc-dev-guide.rust-lang.org/profiling/wpa_profiling.html).

**WSL2 (recommended):**

Run profiling in WSL2 Ubuntu environment for full tool support:

```bash
# Install WSL2 Ubuntu
wsl --install -d Ubuntu

# Inside WSL2, follow Linux installation steps
```

## Troubleshooting

### "error: toolchain 'nightly' is not installed"

```bash
rustup toolchain install nightly
rustup override set nightly
```

### "command not found: crox"

Ensure `~/.cargo/bin` is in PATH:

```bash
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### "heaptrack: command not found" on macOS

Heaptrack is Linux-only. Use Instruments:

```bash
instruments -t Allocations -D trace.trace cargo build --release
open trace.trace
```

### "permission denied" when profiling

Add ptrace capability (Linux):

```bash
sudo sysctl -w kernel.yama.ptrace_scope=0
```

### Nix flake.lock conflicts

```bash
# Update flake inputs
nix flake update

# Or use specific nixpkgs revision
nix develop github:NixOS/nixpkgs/nixos-unstable
```

## References

- [measureme GitHub](https://github.com/rust-lang/measureme)
- [heaptrack GitHub](https://github.com/KDE/heaptrack)
- [cargo-llvm-lines GitHub](https://github.com/dtolnay/cargo-llvm-lines)
- [Rust Nightly Documentation](https://doc.rust-lang.org/nightly/)
