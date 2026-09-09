# Hardware Setup Guide for Tenselerate & GPU Optimization

## 2080Ti GPU Prerequisite Setup

### Memory Unlock (cmpunlocker2)

If working with 2080Ti or similar NVIDIA cards on Linux with restricted memory access, use **cmpunlocker2** to unlock full capacity.

**Installation:**
```bash
# Clone and install
git clone https://github.com/[owner]/cmpunlocker2.git
cd cmpunlocker2
python -m pip install -e .

# Verify unlocked memory
cmpunlocker status
```

**Memory Configuration Targets:**
- `nativ_10gb` — Default NVIDIA lock (10GB)
- `unlocked_40gb` — Unlock to 40GB (some RTX 2080 Ti models)
- `unlocked_80gb` — Full 80GB on memory-extended SKUs

**Key Registers:**
| Target | Register | Address | Value |
|--------|----------|---------|-------|
| Memory Config (CFG1) | BAR0 | 0x009A0204 | Stack-dependent |
| Memory Lock (LMR) | BAR0 | 0x00100CE0 | Stack-dependent |
| SM Speed Override | BAR0 | 0x0082381C | 0x88888888 (when unlocking) |
| WPR2 Teardown | BAR0 | 0x001FA824 | Config-dependent |

**Verify Unlock:**
```bash
# Python API
from cmpunlocker.unlock.memory import is_memory_unlocked, current_memory_config
if is_memory_unlocked("0000:0d:00.0"):
    cfg = current_memory_config("0000:0d:00.0")
    print(f"Total: {cfg['total_gb']}GB, Stacks: {cfg['stacks']}")
```

**Daemon Mode (Keep Unlock Active):**
```bash
# Systemd service that maintains unlock across reboots
cmpunlocker daemon start
```

---

## Tenselerate Kernel Benchmarking

### Build & Environment

```bash
# Build CUDA kernels
cd TENSELERATE-
cmake -B build -DCMAKE_CUDA_ARCHITECTURES=75  # SM75 for 2080Ti
cmake --build build -j$(nproc)

# Set GPU selection
export CUDA_VISIBLE_DEVICES=0
```

### Benchmark Commands

#### 1. GQA-Aware Vector Attention (KV Read at 262K Tokens)

**Expected:** ~51ms (currently measured), Physics floor: ~18.5ms

```bash
# Profile with nsys
nsys profile --stats=true -o attention_profile \
  ./build/bin/test-gqa-attention --tokens=262144 --heads=32 --batch=1 --width=128

# Analyze with llama-bench
python scripts/llama-bench.py \
  --model=qwen-32b \
  --context-length=262144 \
  --batch-size=1 \
  --kernel=attention \
  --metric=tokens-per-second
```

**Optimization Path:**
- Current bottleneck: KV load serialization (1493 GB/s peak, ~890 GB/s achieved)
- Target: Overlapped prefetch + lookahead fetch

#### 2. MMQ Small-Width Performance (Batch 1-4)

**Expected:** ~55ms floor, Physics floor: ~17.7ms

```bash
# Sweep batch sizes
for batch in 1 2 4 8 16; do
  nsys profile --stats=true -o mmq_batch_${batch} \
    ./build/bin/test-mmq-attention --batch=$batch --width=64
done

# Compare results
python scripts/compare-mmq.py
```

**Optimization Path:**
- Bottleneck: Per-tile launch overhead (11ms per GDN block)
- Target: Fused launch pipeline, stream pipelining

#### 3. GDN Hybrid Block (Launch Overhead)

**Expected:** ~11ms launch overhead per block, measured step-time: 29.9ms

```bash
# Profile launch delay
nsys profile --sample=none --trace=cuda,osrt -o gdn_launch_profile \
  ./build/bin/test-gdn-hybrid --hybrid-blocks=1 --measure-launch=true

# Compare physics vs measured
python scripts/step-time-analysis.py
```

**Breakdown:**
- Physics floor (step-time): 17.7ms (weight read 18.5ms floor)
- Measured gap: 29.9ms - 17.7ms = **12.2ms overhead**
- Launch overhead identified: 11ms per block

---

## Multi-GPU Setup (Tensor Parallelism)

### Dual 2080Ti with TP=2

**Hardware:**
- GPU 0: 2080Ti (full memory via cmpunlocker)
- GPU 1: 2080Ti (full memory via cmpunlocker)
- Connection: PCIe 3.0 x16 (nominal 16 GB/s, effective ~12 GB/s)

**Benchmark Results (Qwen3.6-27B-AWQ, TP=2):**
| Metric | Prefill | Decode |
|--------|---------|--------|
| Throughput | 1841.7 tok/s | 101.3 tok/s |
| Batch Size | Dynamic (optimal 1-4) | 16-32 |
| Context Length | 262K | 262K |

**LongGen3 Multi-Token Prediction (MTP) Sweep:**
| K | Speculative Tokens | Acceptance Rate | Throughput Impact |
|---|-------------------|-----------------|------------------|
| 1 | 1 | 100% | Baseline |
| 2 | 2 | 87% | +1.8x |
| 3 | 3 | 74% | +2.1x (conservative deploy point) |
| 4 | 4 | 62% | +2.2x |
| 5 | 5 | 51% | +2.0x (falloff begins) |

**Deploy Recommendation:** K=3 for conservative balancing acceptance vs throughput

---

## Context Cache Optimization (262K Tokens)

### Measurement Setup

```bash
# Measure with turboquant (4-bit quantization, no compaction)
python scripts/measure-cache.py \
  --model=qwen-27b \
  --quantization=turboquant_4bit_nc \
  --context-length=262144 \
  --measurement=cache-size
```

**Result:**
- Tokens stored: 735,084 in 4-bit compressed format
- Physical bytes: ~900MB on GPU memory
- Prefill latency with full cache: ~15ms (vs 51ms without cache reuse)

### Cache Eviction Policy

For 262K multi-request workloads:
- Use sliding-window attention (128K window) to cap working set
- Implement LRU eviction with 80% occupancy threshold
- Preserve sink tokens (first N tokens) in all evictions

---

## PCIe Bandwidth Constraints

### Baseline Measurements

| Configuration | Nominal BW | Effective BW | Utilization |
|---------------|-----------|--------------|------------|
| 2080Ti gen3x16 | 16 GB/s | ~12 GB/s | 75% |
| Dual TP (PCIe) | 16 GB/s | ~3-5 GB/s | 20-30% (all-reduce) |
| Crippled link (gen3x4) | 4 GB/s | ~3 GB/s | 75% |

**Optimization:**
- Overlap all-reduce with compute (gradient accumulation pipeline)
- Use graph-fused attention to reduce intermediate writes

---

## Tools & Environment

### Profiling

```bash
# NVIDIA profiling
sudo apt install nvidia-nsys nvidia-cuda-toolkit

# Lightweight microbenchmarks
pip install nvitop

# Verify GPU state
nvidia-smi
nvitop  # Live dashboard

# Check PCIe gen and lane count
nvidia-smi -query-gpu=name,pcie.gen.current,pcie.link.gen.max -f csv
```

### Monitoring

```bash
# Watch memory/power during benchmark
watch -n 0.1 'nvidia-smi --query-gpu=index,memory.used,memory.free,power.draw --format=csv,noheader'

# Thermal monitoring
sensors
```

---

## Next Steps

See [`docs/kernel-work.md`](docs/kernel-work.md) for open optimization items and reproducible prove-it commands for each bottleneck.

Also consult [`docs/physics.md`](docs/physics.md) for speed-of-light analysis and achievable headroom per subsystem.
