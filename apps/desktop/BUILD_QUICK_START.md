# Hercules Desktop Build Quick Start

## One-Command Builds

### For Your Current Machine
```bash
npm run dist                 # Builds everything for current machine
```

### For Specific Platforms

**macOS:**
```bash
npm run dist:mac:x64        # Intel Macs
npm run dist:mac:arm64      # Apple Silicon Macs
npm run dist:mac:universal  # Both Intel + ARM in one app
```

**Windows:**
```bash
npm run dist:win:x64        # 64-bit Windows
npm run dist:win:ia32       # 32-bit Windows
npm run dist:win:arm64      # Windows on ARM
```

**Linux:**
```bash
npm run dist:linux:x64      # 64-bit Linux
npm run dist:linux:ia32     # 32-bit Linux
npm run dist:linux:armv7l   # 32-bit ARM Linux
npm run dist:linux:arm64    # 64-bit ARM Linux
```

## Using the Makefile

```bash
# See all available targets
make -f Makefile.architectures help

# Build all platforms
make -f Makefile.architectures build-all

# Build specific platform
make -f Makefile.architectures build-all-mac
make -f Makefile.architectures build-all-win
make -f Makefile.architectures build-all-linux

# Build specific architecture
make -f Makefile.architectures build-mac-arm64
make -f Makefile.architectures build-linux-arm64
```

## Cross-Platform Building

Building for a different architecture than your current machine requires cross-compiler setup:

### Linux to ARM64
```bash
sudo apt-get install g++-aarch64-linux-gnu
npm run rebuild:native:arm64
npm run dist:linux:arm64
```

### Linux to ARMv7l
```bash
sudo apt-get install g++-arm-linux-gnueabihf
npm run rebuild:native:armv7l
npm run dist:linux:armv7l
```

### macOS to ARM64 (from Intel)
```bash
npm run dist:mac:universal
```

## Build Output

Artifacts are in `./release/`:
- `Hercules-*.dmg` — macOS installers
- `Hercules-*.nsis` — Windows installers
- `Hercules-*.AppImage` — Linux AppImage
- `hercules_*.deb` — Debian packages
- `hercules-*.rpm` — RPM packages

## Continuous Integration

GitHub Actions automatically builds for all platforms/architectures on push. See `.github/workflows/desktop-multiarch.yml`.

## Troubleshooting

**"No prebuild found"**: Install cross-compiler or use prebuilt binaries from npm.

**Build hangs on macOS**: May need notarization credentials (see `scripts/notarize.mjs`).

**Windows ARM64 not supported**: Requires Windows 11 ARM64 host or cross-compiler setup.

## See Also

- **[BUILD_ARCHITECTURES.md](./BUILD_ARCHITECTURES.md)** — Detailed architecture guide
- **[Makefile.architectures](./Makefile.architectures)** — Build targets
- **[scripts/stage-native-deps.mjs](./scripts/stage-native-deps.mjs)** — Native dependency staging
