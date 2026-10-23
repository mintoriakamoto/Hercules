# Multi-Architecture Build Guide for Hercules Desktop

This guide explains how to build Hercules Desktop for different CPU architectures and platforms.

## Supported Architectures

### macOS
- **x64** (Intel) — `npm run dist:mac:x64`
- **arm64** (Apple Silicon) — `npm run dist:mac:arm64`
- **universal** (both Intel + ARM) — `npm run dist:mac:universal`

### Windows
- **x64** (64-bit Intel) — `npm run dist:win:x64`
- **ia32** (32-bit Intel) — `npm run dist:win:ia32`
- **arm64** (Windows on ARM) — `npm run dist:win:arm64`

### Linux
- **x64** (64-bit Intel) — `npm run dist:linux:x64`
- **ia32** (32-bit Intel) — `npm run dist:linux:ia32`
- **armv7l** (32-bit ARM, e.g., Raspberry Pi) — `npm run dist:linux:armv7l`
- **arm64** (64-bit ARM, e.g., Apple Silicon VM, Raspberry Pi 4) — `npm run dist:linux:arm64`

## Build Commands

### Single-Architecture Builds

**macOS:**
```bash
npm run dist:mac:x64          # Intel Mac
npm run dist:mac:arm64        # Apple Silicon Mac
npm run dist:mac:universal    # Both architectures in one app
npm run dist:mac:dmg          # DMG installer (current arch)
npm run dist:mac:zip          # ZIP archive (current arch)
```

**Windows:**
```bash
npm run dist:win:x64          # 64-bit Windows
npm run dist:win:ia32         # 32-bit Windows
npm run dist:win:arm64        # Windows on ARM
npm run dist:win:nsis         # NSIS installer (current arch)
npm run dist:win:msi          # MSI installer (current arch)
```

**Linux:**
```bash
npm run dist:linux:x64        # 64-bit Linux (x86_64)
npm run dist:linux:ia32       # 32-bit Linux (i686)
npm run dist:linux:armv7l     # 32-bit ARM Linux
npm run dist:linux:arm64      # 64-bit ARM Linux

# Builds AppImage, deb, and rpm for specified architecture
```

### Multi-Architecture Builds

```bash
# Build all supported architectures for all platforms
npm run dist:all

# Build all platforms at once (requires proper build environment)
npm run builder -- -mwl -c.electronArch=x64,arm64
```

## Native Module Compilation

node-pty (terminal emulator) requires native compilation per architecture.

### Automatic (Recommended)

The build process automatically handles native compilation via `before-pack.mjs`, which:
1. Uses prebuilt binaries when available (from node-pty's prebuilds)
2. Falls back to local compilation if needed
3. Stages the correct binary for each target architecture

### Manual Rebuild

To manually rebuild node-pty for specific architectures:

```bash
npm run rebuild:native:x64      # 64-bit Intel
npm run rebuild:native:ia32     # 32-bit Intel
npm run rebuild:native:armv7l   # 32-bit ARM
npm run rebuild:native:arm64    # 64-bit ARM
```

## Cross-Platform Builds

Building for a different architecture than your current machine requires either:

### Option 1: Native Prebuilds (Recommended)
If node-pty has prebuilt binaries for your target, the build automatically uses them.

Check available prebuilds:
```bash
ls node_modules/node-pty/prebuilds/
```

### Option 2: Cross-Compilation
For architectures without prebuilds, you need a cross-compiler:

**Linux x64 → ARM64:**
```bash
sudo apt-get install g++-aarch64-linux-gnu
npm run rebuild:native:arm64
npm run dist:linux:arm64
```

**Linux x64 → ARMv7l:**
```bash
sudo apt-get install g++-arm-linux-gnueabihf
npm run rebuild:native:armv7l
npm run dist:linux:armv7l
```

**macOS x64 → ARM64:**
```bash
# macOS with Xcode supports universal builds natively
npm run dist:mac:universal
```

## Build Output

Artifacts are saved in `./release/`:

```
release/
├── Hercules-1.0.0-darwin-x64.dmg          # macOS Intel DMG
├── Hercules-1.0.0-darwin-arm64.dmg        # macOS Apple Silicon DMG
├── Hercules-1.0.0-win-x64.nsis            # Windows 64-bit installer
├── Hercules-1.0.0-win-ia32.nsis           # Windows 32-bit installer
├── Hercules-1.0.0-linux-x64.AppImage      # Linux 64-bit AppImage
├── hercules_1.0.0_amd64.deb               # Debian 64-bit package
├── hercules-1.0.0.x86_64.rpm              # RPM 64-bit package
├── Hercules-1.0.0-linux-arm64.AppImage    # Linux ARM64 AppImage
└── ...
```

## Troubleshooting

### "No prebuild found" Warning
If you see:
```
no prebuild found at prebuilds/{platform}-{arch}
```

**Solution:** Either:
1. Use prebuilt binaries: `npm install` (node-pty should have prebuilds)
2. Compile locally: `npm run rebuild:native:{arch}`

### "spawn-helper not found" Error
The spawn-helper executable is required on macOS/Linux for terminal spawning.

**Solution:** Ensure it's in the final package:
```bash
# Check if it exists
ls node_modules/node-pty/prebuilds/{platform}-{arch}/
```

### Cross-Compilation Failures
If you see compilation errors when building for a different architecture:

1. Ensure you have the cross-compiler installed:
   ```bash
   # For ARM64 on Linux x64
   sudo apt-get install g++-aarch64-linux-gnu make python3
   ```

2. Set the correct compiler flags:
   ```bash
   export CC=aarch64-linux-gnu-gcc
   export CXX=aarch64-linux-gnu-g++
   npm run rebuild:native:arm64
   ```

## CI/CD Integration

For automated multi-architecture builds in CI:

### GitHub Actions Example
```yaml
strategy:
  matrix:
    include:
      - os: macos-latest
        arch: x64
        cmd: npm run dist:mac:x64
      - os: macos-latest
        arch: arm64
        cmd: npm run dist:mac:arm64
      - os: windows-latest
        arch: x64
        cmd: npm run dist:win:x64
      - os: ubuntu-latest
        arch: x64
        cmd: npm run dist:linux:x64
      - os: ubuntu-latest
        arch: arm64
        cmd: npm run dist:linux:arm64

steps:
  - uses: actions/setup-node@v4
    with:
      node-version: '22'
  - run: npm ci
  - run: npm run ${{ matrix.cmd }}
```

## Performance Notes

- **macOS universal binaries** are ~2x the size of single-arch builds
- **Linux AppImage** is the most portable format for different distros
- **deb/rpm packages** are smaller but require installation
- **Pre-built binaries** (node-pty) are 10x faster than local compilation
- **ARM64 builds on x64** require cross-compiler (slower, requires manual setup)

## See Also

- `scripts/stage-native-deps.mjs` — Stages native dependencies per architecture
- `scripts/before-pack.mjs` — Electron-builder hook for native staging
- `scripts/rebuild-native.mjs` — Manual native module compilation
- [electron-builder Architecture Support](https://www.electron.build/configuration/build#arch)
- [node-pty Prebuilds](https://github.com/Microsoft/node-pty#prebuilds)
