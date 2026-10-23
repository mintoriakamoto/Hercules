# Heterogeneous Architecture Support Skill

**Purpose:** Integrate ARM, ESP32, RISC-V and other instruction set architectures into Hercules agent runtime. Unified deployment and coordination across heterogeneous hardware.

**Scope:** Cross-compilation, architecture abstraction, platform-specific dispatch, capability discovery, distributed execution across ISAs.

---

## Part 1: Architecture Abstraction Layer

### 1.1 Hardware Capability Descriptor

```python
# agent/architecture/capability_model.py

from enum import Enum
from dataclasses import dataclass
from typing import Set, Dict, Optional

class ISA(Enum):
    """Instruction Set Architectures."""
    X86_64 = "x86_64"
    ARM_V7 = "armv7"
    ARM_V8 = "armv8"  # ARMv8 64-bit
    ARM_THUMB = "thumb"
    RISCV_32 = "riscv32"
    RISCV_64 = "riscv64"
    ESP_XTENSA = "xtensa"  # ESP32 uses Xtensa ISA
    MIPS = "mips"

@dataclass
class HardwareProfile:
    """Describes a hardware platform's capabilities."""
    
    isa: ISA
    endianness: str  # "little" or "big"
    register_width: int  # 32 or 64
    max_memory_mb: int
    has_fpu: bool  # Floating point unit
    has_mmu: bool  # Memory management unit
    has_cache: bool
    cache_levels: int
    cache_line_size: int
    
    # Execution model
    max_concurrent_threads: int
    supports_vectorization: bool  # SIMD
    vector_width_bits: int  # 128, 256, 512
    
    # Extensions
    supported_extensions: Set[str]  # e.g., {"sve", "neon", "rvv"}
    
    # Peripherals (esp for embedded)
    has_gpio: bool
    has_spi: bool
    has_i2c: bool
    has_uart: bool
    has_adc: bool
    
    # Power constraints
    is_battery_powered: bool
    power_budget_mw: Optional[int]  # milliwatts
    
    def get_optimization_flags(self) -> str:
        """Return compiler flags for this architecture."""
        flags = {
            ISA.X86_64: "-march=x86-64 -mtune=generic",
            ISA.ARM_V8: "-march=armv8-a -mcpu=generic",
            ISA.ARM_V7: "-march=armv7-a -mtune=cortex-a9",
            ISA.RISCV_64: "-march=rv64imac -mtune=generic",
            ISA.ESP_XTENSA: "-mcpu=esp32 -march=xtensa-lx6",
        }
        return flags.get(self.isa, "")
    
    def is_compatible_with(self, other: 'HardwareProfile') -> bool:
        """Check if binaries from other ISA can run here."""
        # ARM v8 can run v7, but not vice versa
        compatibility = {
            ISA.ARM_V8: {ISA.ARM_V8, ISA.ARM_V7},
            ISA.ARM_V7: {ISA.ARM_V7},
            ISA.RISCV_64: {ISA.RISCV_64, ISA.RISCV_32},
            ISA.X86_64: {ISA.X86_64},
            ISA.ESP_XTENSA: {ISA.ESP_XTENSA},
        }
        return other.isa in compatibility.get(self.isa, set())

# Platform registry
PLATFORMS = {
    'x86_64_linux': HardwareProfile(
        isa=ISA.X86_64,
        endianness='little',
        register_width=64,
        max_memory_mb=65536,
        has_fpu=True,
        has_mmu=True,
        has_cache=True,
        cache_levels=3,
        cache_line_size=64,
        max_concurrent_threads=128,
        supports_vectorization=True,
        vector_width_bits=512,
        supported_extensions={'avx512', 'fma'},
        has_gpio=False,
        has_spi=False,
        has_i2c=False,
        has_uart=False,
        has_adc=False,
        is_battery_powered=False,
        power_budget_mw=None,
    ),
    
    'armv8_raspi5': HardwareProfile(
        isa=ISA.ARM_V8,
        endianness='little',
        register_width=64,
        max_memory_mb=8192,
        has_fpu=True,
        has_mmu=True,
        has_cache=True,
        cache_levels=3,
        cache_line_size=64,
        max_concurrent_threads=8,
        supports_vectorization=True,
        vector_width_bits=128,
        supported_extensions={'neon', 'sve'},
        has_gpio=True,
        has_spi=True,
        has_i2c=True,
        has_uart=True,
        has_adc=False,
        is_battery_powered=False,
        power_budget_mw=15000,
    ),
    
    'riscv64_sipeed': HardwareProfile(
        isa=ISA.RISCV_64,
        endianness='little',
        register_width=64,
        max_memory_mb=2048,
        has_fpu=True,
        has_mmu=True,
        has_cache=True,
        cache_levels=2,
        cache_line_size=64,
        max_concurrent_threads=4,
        supports_vectorization=True,
        vector_width_bits=128,
        supported_extensions={'rvv', 'b'},
        has_gpio=True,
        has_spi=True,
        has_i2c=True,
        has_uart=True,
        has_adc=False,
        is_battery_powered=False,
        power_budget_mw=5000,
    ),
    
    'esp32_embedded': HardwareProfile(
        isa=ISA.ESP_XTENSA,
        endianness='little',
        register_width=32,
        max_memory_mb=520,  # 320 SRAM + 200 flash
        has_fpu=False,
        has_mmu=False,
        has_cache=True,
        cache_levels=1,
        cache_line_size=32,
        max_concurrent_threads=2,
        supports_vectorization=False,
        vector_width_bits=0,
        supported_extensions={'windowed-abi'},
        has_gpio=True,
        has_spi=True,
        has_i2c=True,
        has_uart=True,
        has_adc=True,
        is_battery_powered=True,
        power_budget_mw=80,
    ),
}
```

### 1.2 Architecture-Agnostic Agent Interface

```python
# agent/architecture/portable_agent.py

from abc import ABC, abstractmethod
from typing import Any, Dict, List

class PortableAgent(ABC):
    """Agent interface that runs on any ISA."""
    
    def __init__(self, platform: HardwareProfile):
        self.platform = platform
        self.native_format = self._get_native_code_format()
    
    @abstractmethod
    def execute(self, task: str) -> Dict[str, Any]:
        """Execute task on this architecture."""
        pass
    
    @abstractmethod
    def compile_for_platform(self, code: str) -> bytes:
        """Cross-compile code to target ISA."""
        pass
    
    def _get_native_code_format(self) -> str:
        """Return native code format for this ISA."""
        formats = {
            ISA.X86_64: "x86_64_elf",
            ISA.ARM_V8: "arm64_elf",
            ISA.ARM_V7: "arm32_elf",
            ISA.RISCV_64: "riscv64_elf",
            ISA.ESP_XTENSA: "xtensa_elf",
        }
        return formats[self.platform.isa]
    
    def get_capability_set(self) -> Set[str]:
        """What this hardware can do."""
        capabilities = {
            'can_execute_code',
            'can_read_memory',
            'can_write_memory',
        }
        
        if self.platform.has_fpu:
            capabilities.add('floating_point')
        
        if self.platform.supports_vectorization:
            capabilities.add('vectorization')
        
        if self.platform.has_gpio:
            capabilities.update({
                'gpio_read',
                'gpio_write',
                'interrupt_handling',
            })
        
        if self.platform.has_adc:
            capabilities.add('analog_input')
        
        return capabilities
```

---

## Part 2: Cross-Compilation Pipeline

### 2.1 Toolchain Manager

```python
# agent/architecture/toolchain_manager.py

class ToolchainManager:
    """Manage cross-compilation toolchains for each ISA."""
    
    TOOLCHAINS = {
        ISA.X86_64: {
            'compiler': 'gcc-x86_64-linux-gnu',
            'flags': '-O2 -march=x86-64',
            'output_format': 'elf64-x86-64',
        },
        ISA.ARM_V8: {
            'compiler': 'aarch64-linux-gnu-gcc',
            'flags': '-O2 -march=armv8-a',
            'output_format': 'elf64-littleaarch64',
        },
        ISA.ARM_V7: {
            'compiler': 'arm-linux-gnueabihf-gcc',
            'flags': '-O2 -march=armv7-a -mfpu=neon',
            'output_format': 'elf32-littlearm',
        },
        ISA.RISCV_64: {
            'compiler': 'riscv64-unknown-elf-gcc',
            'flags': '-O2 -march=rv64imac',
            'output_format': 'elf64-littleriscv',
        },
        ISA.ESP_XTENSA: {
            'compiler': 'xtensa-esp32-elf-gcc',
            'flags': '-O2 -mcpu=esp32',
            'output_format': 'elf32-littlextensa',
        },
    }
    
    def compile_for_isa(self, source: str, target_isa: ISA) -> bytes:
        """Cross-compile source code to target ISA."""
        
        toolchain = self.TOOLCHAINS[target_isa]
        
        # Write source
        with open('/tmp/source.c', 'w') as f:
            f.write(source)
        
        # Compile
        cmd = [
            toolchain['compiler'],
            toolchain['flags'],
            '-o', '/tmp/output.elf',
            '/tmp/source.c'
        ]
        
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise CompilationError(result.stderr.decode())
        
        # Read binary
        with open('/tmp/output.elf', 'rb') as f:
            return f.read()
    
    def get_optimization_level(self, platform: HardwareProfile) -> str:
        """Get optimal compiler flags for platform."""
        
        if platform.is_battery_powered:
            return '-Os'  # Optimize for size
        
        if platform.power_budget_mw and platform.power_budget_mw < 1000:
            return '-Os'
        
        return '-O2'  # Default optimization

class CompilationError(Exception):
    pass
```

### 2.2 Binary Format Abstraction

```python
# agent/architecture/binary_format.py

class BinaryFormat:
    """Abstraction over different executable formats."""
    
    def __init__(self, isa: ISA, binary: bytes):
        self.isa = isa
        self.binary = binary
        self.metadata = self._parse_metadata()
    
    def _parse_metadata(self) -> Dict:
        """Extract metadata from binary."""
        
        if self.isa in [ISA.X86_64, ISA.ARM_V8, ISA.ARM_V7, ISA.RISCV_64]:
            return self._parse_elf()
        elif self.isa == ISA.ESP_XTENSA:
            return self._parse_esp_image()
    
    def _parse_elf(self) -> Dict:
        """Parse ELF binary."""
        import struct
        
        # ELF header
        magic = self.binary[:4]
        if magic != b'\x7fELF':
            raise ValueError("Not an ELF binary")
        
        ei_class = self.binary[4]  # 1=32-bit, 2=64-bit
        ei_data = self.binary[5]   # 1=little-endian, 2=big-endian
        
        return {
            'format': 'elf',
            'bits': 32 if ei_class == 1 else 64,
            'endianness': 'little' if ei_data == 1 else 'big',
            'size': len(self.binary),
        }
    
    def _parse_esp_image(self) -> Dict:
        """Parse ESP32 image format."""
        
        # ESP32 image format: magic byte 0xE9 + segments
        if self.binary[0] != 0xE9:
            raise ValueError("Not an ESP32 image")
        
        num_segments = self.binary[1]
        
        return {
            'format': 'esp_image',
            'segments': num_segments,
            'size': len(self.binary),
        }
    
    def can_run_on(self, platform: HardwareProfile) -> bool:
        """Check if binary can run on platform."""
        
        if self.isa != platform.isa:
            # Check compatibility
            return platform.is_compatible_with(HardwareProfile(isa=self.isa))
        
        return True
```

---

## Part 3: Distributed Execution Coordination

### 3.1 Multi-Architecture Task Dispatch

```python
# agent/architecture/distributed_dispatch.py

class DistributedDispatcher:
    """Route tasks to appropriate architecture."""
    
    def __init__(self, platforms: Dict[str, HardwareProfile]):
        self.platforms = platforms
        self.task_history = []
    
    def find_best_platform(self, task: str, constraints: Dict = None) -> str:
        """Find optimal platform for task."""
        
        constraints = constraints or {}
        
        # Score each platform
        scores = {}
        for platform_name, profile in self.platforms.items():
            score = 0
            
            # Capability matching
            if constraints.get('requires_fpu') and not profile.has_fpu:
                continue  # Incompatible
            
            if constraints.get('requires_gpio') and not profile.has_gpio:
                continue
            
            # Performance scoring
            if constraints.get('wants_performance'):
                score += profile.max_concurrent_threads * 10
                if profile.supports_vectorization:
                    score += 100
            
            # Power efficiency scoring
            if constraints.get('wants_efficiency'):
                if profile.is_battery_powered:
                    score += 50
                score += (1000 / (profile.power_budget_mw or 100))
            
            # Memory constraints
            if constraints.get('max_memory_mb'):
                if profile.max_memory_mb < constraints['max_memory_mb']:
                    continue
            
            scores[platform_name] = score
        
        if not scores:
            raise ValueError("No compatible platform found")
        
        return max(scores, key=scores.get)
    
    def dispatch_task(self, task: str, constraints: Dict = None):
        """Dispatch task to best platform."""
        
        best_platform = self.find_best_platform(task, constraints)
        platform_profile = self.platforms[best_platform]
        
        # Compile for target
        binary = self.compile_for_platform(task, platform_profile)
        
        # Execute
        result = self.execute_on_platform(best_platform, binary)
        
        # Log
        self.task_history.append({
            'task': task,
            'platform': best_platform,
            'result': result,
        })
        
        return result
    
    def execute_on_platform(self, platform_name: str, binary: bytes) -> Dict:
        """Execute binary on specific platform."""
        
        # Platform-specific execution
        executors = {
            'x86_64_linux': self._execute_x86_64,
            'armv8_raspi5': self._execute_arm,
            'riscv64_sipeed': self._execute_riscv,
            'esp32_embedded': self._execute_esp32,
        }
        
        executor = executors.get(platform_name)
        if not executor:
            raise ValueError(f"No executor for {platform_name}")
        
        return executor(binary)
    
    def _execute_esp32(self, binary: bytes) -> Dict:
        """Execute on ESP32 via serial."""
        import esptool
        
        # Flash binary
        esp = esptool.ESP32ROM.detect_port()
        esp.flash_bin(0x1000, binary)
        
        # Read output from serial
        output = self._read_serial_output(timeout=5)
        
        return {'output': output, 'platform': 'esp32'}
```

### 3.2 Inter-Architecture Communication

```python
# agent/architecture/ipc_bridge.py

class InterArchitectureBridge:
    """Communication between different ISA domains."""
    
    def __init__(self, platforms: Dict[str, HardwareProfile]):
        self.platforms = platforms
        self.shared_memory = {}  # Shared data structures
    
    def marshal_data(self, data: Any, source_isa: ISA, target_isa: ISA) -> bytes:
        """Convert data between ISA byte orders and formats."""
        
        # Detect endianness differences
        source_endian = self.platforms[source_isa].endianness
        target_endian = self.platforms[target_isa].endianness
        
        if isinstance(data, int):
            # Marshal integer with correct byte order
            if source_endian != target_endian:
                data = self._swap_endian(data)
        
        elif isinstance(data, bytes):
            # Already bytes, just swap if needed
            if source_endian != target_endian:
                data = bytes(reversed(data))
        
        return data
    
    def create_shared_memory_region(self, name: str, size: int) -> int:
        """Create memory region accessible from multiple architectures."""
        
        # Allocate in machine's native format
        memory = bytearray(size)
        self.shared_memory[name] = memory
        
        # Return address
        return id(memory)
    
    def write_to_shared_memory(self, region: str, offset: int, data: bytes):
        """Write to shared memory from any architecture."""
        
        if region not in self.shared_memory:
            raise ValueError(f"Region {region} not found")
        
        self.shared_memory[region][offset:offset+len(data)] = data
    
    def read_from_shared_memory(self, region: str, offset: int, size: int) -> bytes:
        """Read from shared memory from any architecture."""
        
        if region not in self.shared_memory:
            raise ValueError(f"Region {region} not found")
        
        return bytes(self.shared_memory[region][offset:offset+size])
```

---

## Part 4: Performance Optimization Per Architecture

### 4.1 Architecture-Specific Optimizations

```python
# agent/architecture/optimization_engine.py

class OptimizationEngine:
    """Tune code for specific architecture."""
    
    def optimize_for_platform(self, code: str, platform: HardwareProfile) -> str:
        """Rewrite code for optimal performance on platform."""
        
        if platform.isa == ISA.X86_64:
            return self._optimize_x86_64(code, platform)
        elif platform.isa in [ISA.ARM_V8, ISA.ARM_V7]:
            return self._optimize_arm(code, platform)
        elif platform.isa in [ISA.RISCV_64, ISA.RISCV_32]:
            return self._optimize_riscv(code, platform)
        elif platform.isa == ISA.ESP_XTENSA:
            return self._optimize_esp32(code, platform)
    
    def _optimize_x86_64(self, code: str, platform: HardwareProfile) -> str:
        """x86-64 specific optimizations."""
        
        optimizations = []
        
        # SIMD vectorization
        if platform.supports_vectorization:
            # Replace scalar loops with AVX/AVX2
            code = code.replace(
                'for (int i = 0; i < n; i++) arr[i] += 1;',
                '__m256 ones = _mm256_set1_ps(1.0); '
                'for (int i = 0; i < n; i += 8) '
                '  _mm256_storeu_ps(&arr[i], _mm256_add_ps(_mm256_loadu_ps(&arr[i]), ones));'
            )
            optimizations.append('SIMD vectorization')
        
        # Branch prediction hints
        code = code.replace(
            'if (likely_condition)',
            'if (__builtin_expect((likely_condition), 1))'
        )
        
        return code
    
    def _optimize_arm(self, code: str, platform: HardwareProfile) -> str:
        """ARM-specific optimizations."""
        
        if platform.has_fpu:
            # Use NEON vector instructions
            code = code.replace(
                'float calc(float a, float b)',
                'inline float calc(float a, float b) __attribute__((always_inline))'
            )
        
        # ARM thumb-2 mode for size
        if platform.isa == ISA.ARM_V7:
            code = '#pragma GCC target("thumb")\n' + code
        
        return code
    
    def _optimize_esp32(self, code: str, platform: HardwareProfile) -> str:
        """ESP32 power/memory optimization."""
        
        # Use IRAM for hot functions
        code = code.replace(
            'void hot_function()',
            'IRAM_ATTR void hot_function()'
        )
        
        # Place less-used code in flash
        code = code.replace(
            'void cold_function()',
            'FLASH_ATTR void cold_function()'
        )
        
        # Reduce allocations
        optimizations = [
            'IRAM: interrupt handlers, frequently called code',
            'FLASH: initialization code, rarely called functions',
            'RTC SRAM: persistent data across deep sleep',
        ]
        
        return code
```

---

## Part 5: Integration with Hercules Agent

### 5.1 Agent Architecture Extensions

```python
# run_agent.py additions

class AIAgent:
    def __init__(self, ...):
        # ... existing init ...
        
        # Add heterogeneous support
        self.platforms = self._detect_available_platforms()
        self.dispatcher = DistributedDispatcher(self.platforms)
        self.bridge = InterArchitectureBridge(self.platforms)
    
    def _detect_available_platforms(self) -> Dict[str, HardwareProfile]:
        """Auto-detect available hardware."""
        
        detected = {}
        
        # Check for local CPU
        if platform.machine() == 'x86_64':
            detected['x86_64_linux'] = PLATFORMS['x86_64_linux']
        elif platform.machine() == 'aarch64':
            detected['armv8_raspi5'] = PLATFORMS['armv8_raspi5']
        
        # Check for connected ESP32
        try:
            import esptool
            if esptool.ESP32ROM.detect_port():
                detected['esp32_embedded'] = PLATFORMS['esp32_embedded']
        except:
            pass
        
        # Check for RISC-V board (e.g., via SSH)
        # ...
        
        return detected
    
    def dispatch_tool(self, tool_name: str, args: Dict):
        """Route tool execution across architectures."""
        
        # Determine where to run
        platform = self.dispatcher.find_best_platform(tool_name)
        
        # Compile tool for platform
        binary = self.dispatcher.compile_for_platform(tool_name, self.platforms[platform])
        
        # Execute
        return self.dispatcher.execute_on_platform(platform, binary)
```

---

## Part 6: Invocation & Deployment

### 6.1 Multi-ISA Deployment Example

```bash
#!/bin/bash
# scripts/deploy_heterogeneous.sh

# Detect platforms
python3 -c "
from agent.architecture.capability_model import PLATFORMS
import json

platforms = {}
# Add detection logic...

print(json.dumps(platforms, indent=2))
" > /tmp/platforms.json

# Compile for each platform
for platform in $(jq -r 'keys[]' /tmp/platforms.json); do
  echo "Compiling for $platform..."
  python3 scripts/cross_compile.py --target=$platform --output=build/$platform
done

# Deploy to each platform
for platform in x86_64_linux armv8_raspi5 riscv64_sipeed esp32_embedded; do
  if [ -f "build/$platform/hercules.elf" ]; then
    scripts/deploy_$platform.sh build/$platform/hercules.elf
  fi
done

# Verify distributed system
python3 -c "
from agent.architecture.distributed_dispatch import DistributedDispatcher

dispatcher = DistributedDispatcher(platforms)
result = dispatcher.dispatch_task('heartbeat', {'wants_efficiency': True})
print(f'System healthy: {result}')
"
```

---

## Success Criteria

✅ **Code runs unchanged on multiple ISAs** — architecture abstraction layer  
✅ **Automatic platform detection** — deploy once, runs everywhere  
✅ **Efficient cross-compilation** — native performance on each target  
✅ **Inter-architecture communication** — share data across ISA boundaries  
✅ **Optimal for each platform** — ARM gets NEON, x86 gets AVX, ESP32 gets power efficiency  

---

**Pattern Source:** LLVM's architecture abstraction, Docker multi-platform builds, Rust's target architecture system. Heterogeneous computing requires clean ISA abstraction layer + distributed dispatch.
