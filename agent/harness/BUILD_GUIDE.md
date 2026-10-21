# Consciousness Metrics Rust Implementation - Build Guide

This guide covers building and integrating the Rust consciousness metrics engine with Python.

## Prerequisites

1. **Rust toolchain**: Install from https://rustup.rs/
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   ```

2. **Python development headers**: Required for PyO3 compilation
   ```bash
   # Ubuntu/Debian
   sudo apt-get install python3-dev
   
   # macOS
   brew install python3
   
   # Windows (via MSVC tools)
   # Visual Studio Community with MSVC compiler
   ```

3. **Maturin** (optional but recommended for wheels):
   ```bash
   pip install maturin
   ```

## Quick Start

### 1. Build Rust Library Only

From the `agent/harness/` directory:

```bash
cargo build --release
```

This creates `target/release/libconsciousness_metrics.so` (Linux) or `.dylib` (macOS) or `.dll` (Windows).

### 2. Build Python Extension

Using maturin (recommended):

```bash
cd /home/user/Hercules/agent/harness
maturin develop --release
```

Or using setuptools with a build script (requires pyproject.toml configuration).

### 3. Verify Installation

```bash
python3 -c "from consciousness_metrics import ConsciousnessMetrics; print('Rust backend available!')"
```

## Integration Steps

### Step 1: Ensure Rust Toolchain

```bash
rustc --version
cargo --version
```

Expected output: `rustc 1.70+` and `cargo 1.70+`

### Step 2: Install Build Dependencies

```bash
# From project root
pip install maturin setuptools-rust
```

### Step 3: Build the Extension

```bash
cd /home/user/Hercules/agent/harness
maturin develop --release
```

### Step 4: Test the Build

```bash
python3 -c "
from consciousness_metrics import ConsciousnessMetrics
m = ConsciousnessMetrics('test')
m.record_continuity('ckpt', 1, 'test')
score = m.calculate_scores()
print(f'Score: {score.continuity_score}')
"
```

### Step 5: Update Code to Use Rust Backend

Replace:
```python
from agent.harness.consciousness_metrics import ConsciousnessMetrics
```

With:
```python
from agent.harness.consciousness_metrics_rs import ConsciousnessMetrics
```

Or keep the old import and it will auto-fallback if Rust not available.

## Building for Distribution

### Python Wheel (All Platforms)

```bash
# Install build dependencies
pip install maturin wheel

# Build wheel
cd /home/user/Hercules/agent/harness
maturin build --release
```

Wheels are created in `target/wheels/`.

### Platform-Specific Builds

#### Linux

```bash
# Requires: build-essential, python3-dev
maturin build --release
```

#### macOS

```bash
# Requires: Xcode Command Line Tools
xcode-select --install
maturin build --release
```

#### Windows

```bash
# Requires: Visual Studio Community with C++ tools
# In Developer Command Prompt:
maturin build --release
```

## Verification & Testing

### Unit Tests

```bash
cargo test --release
```

### Benchmarks

```bash
cargo bench
```

Expected results:
- `record_continuity`: ~0.3 µs
- `calculate_scores (100 items)`: ~8 µs
- **>100x faster** than Python

### Integration Tests

```bash
cargo test --release --test '*'
```

## Troubleshooting

### Error: "linker not found"

**Linux**: Install development tools
```bash
sudo apt-get install build-essential
```

**macOS**: Install Xcode Command Line Tools
```bash
xcode-select --install
```

### Error: "Python.h not found"

Install Python development headers:

```bash
# Ubuntu/Debian
sudo apt-get install python3-dev

# Fedora
sudo dnf install python3-devel

# macOS
brew install python3
```

### Error: "maturin: command not found"

Install maturin:
```bash
pip install maturin
```

### Error: "pyo3 not compatible with this Python version"

Check Python version:
```bash
python3 --version
```

Supported versions: Python 3.8+

### Import fails after build

Ensure the .so/.dylib/.pyd is in the right location:

```bash
# Find the built library
find /home/user/Hercules/agent/harness -name "*.so" -o -name "*.dylib" -o -name "*.pyd"

# Verify it's importable
python3 -c "import sys; import consciousness_metrics; print(consciousness_metrics.__file__)"
```

## Performance Optimization

### Profile-Guided Optimization (PGO)

For maximum performance:

```bash
# Build with instrumentation
RUSTFLAGS="-Cinstrument-coverage" cargo build --release

# Run representative workload
python3 -c "
from consciousness_metrics import ConsciousnessMetrics
m = ConsciousnessMetrics('test')
for i in range(1000):
    m.record_continuity(f'ckpt_{i}', i, '')
score = m.calculate_scores()
"

# Build optimized binary using coverage data
RUSTFLAGS="-Cprofile-use=coverage.profraw" cargo build --release
```

### Link-Time Optimization (LTO)

Already enabled in `Cargo.toml` for release builds:
```toml
[profile.release]
lto = true
codegen-units = 1
```

## Updating Python Compatibility

When updating PyO3 version in `Cargo.toml`:

1. Check https://github.com/PyO3/pyo3 for latest version
2. Update `pyo3` version in `Cargo.toml`
3. Rebuild: `maturin develop --release`

## Development Workflow

### During Development

```bash
# Watch for changes and rebuild
cargo watch -x build

# Or in another terminal
maturin develop  # Without --release for faster builds
```

### Before Committing

```bash
# Format code
cargo fmt

# Lint
cargo clippy --all-targets

# Test
cargo test --release

# Bench
cargo bench
```

## Integration with Python Package

To make the Rust extension part of the package distribution:

1. Add to `pyproject.toml`:
```toml
[build-system]
requires = ["maturin"]
build-backend = "maturin"

[project]
name = "hercules-agent"
...
```

2. Create setup script or use maturin directly

3. Test installation:
```bash
pip install -e .
```

## Performance Comparison

After building, compare with Python:

```bash
python3 -c "
import time
from consciousness_metrics import ConsciousnessMetrics

# Test Rust backend
m = ConsciousnessMetrics('test')
start = time.perf_counter()
for i in range(1000):
    m.record_continuity(f'ckpt_{i}', i, '')
rust_time = time.perf_counter() - start

print(f'Rust backend (1000 records): {rust_time*1000:.2f}ms')
print(f'Per-operation: {rust_time*1000000/1000:.2f}µs')
"
```

## Next Steps

1. Build the Rust library: `cargo build --release`
2. Install Python bindings: `maturin develop --release`
3. Update imports in codebase to use `consciousness_metrics_rs`
4. Run tests: `cargo test --release`
5. Benchmark: `cargo bench`

## Support

For issues or questions:
- Check the README.md in this directory
- Review Cargo.toml for dependency versions
- Check PyO3 documentation: https://pyo3.rs/
