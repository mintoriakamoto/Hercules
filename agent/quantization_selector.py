"""Quantization strategy selector based on task category and complexity."""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from agent.routing_types import ModelTier, TaskCategory, ReasoningComplexity


class QuantizationType(str, Enum):
    """Quantization formats for model inference."""

    FP32 = "fp32"
    FP16 = "fp16"
    INT8 = "int8"
    NF4 = "nf4"
    Q4_0 = "q4_0"


class KVCacheQuantization(str, Enum):
    """KV-Cache quantization strategies."""

    NONE = "none"
    Q8_0 = "q8_0"
    Q4_0 = "q4_0"
    Q2_K = "q2_k"


@dataclass
class QuantizationConfig:
    """Configuration for model and KV-cache quantization."""

    model_quantization: QuantizationType
    kv_cache_quantization: KVCacheQuantization
    context_window: int
    expected_throughput: str
    memory_per_model: str
    models_per_40gb: int
    quality_impact: str


class QuantizationSelector:
    """Select quantization with a quality-first bias.

    Complexity still exists so packing can scale down when a job is
    actually simple, but defaults keep more bits than the original
    throughput-first matrix.
    """

    QUANTIZATION_MATRIX = {
        (TaskCategory.READ, ReasoningComplexity.SIMPLE): QuantizationConfig(
            model_quantization=QuantizationType.INT8,
            kv_cache_quantization=KVCacheQuantization.Q8_0,
            context_window=4096,
            expected_throughput="150-250 tok/s",
            memory_per_model="4-6GB",
            models_per_40gb=6,
            quality_impact="Low (~1-2%)",
        ),
        (TaskCategory.ANALYZE, ReasoningComplexity.SIMPLE): QuantizationConfig(
            model_quantization=QuantizationType.INT8,
            kv_cache_quantization=KVCacheQuantization.Q8_0,
            context_window=4096,
            expected_throughput="150-250 tok/s",
            memory_per_model="4-6GB",
            models_per_40gb=6,
            quality_impact="Low (~1-2%)",
        ),
        (TaskCategory.CODE, ReasoningComplexity.MODERATE): QuantizationConfig(
            model_quantization=QuantizationType.FP16,
            kv_cache_quantization=KVCacheQuantization.NONE,
            context_window=8192,
            expected_throughput="50-80 tok/s",
            memory_per_model="20-32GB",
            models_per_40gb=1,
            quality_impact="None",
        ),
        (TaskCategory.ANALYZE, ReasoningComplexity.MODERATE): QuantizationConfig(
            model_quantization=QuantizationType.FP16,
            kv_cache_quantization=KVCacheQuantization.NONE,
            context_window=8192,
            expected_throughput="50-80 tok/s",
            memory_per_model="20-32GB",
            models_per_40gb=1,
            quality_impact="None",
        ),
        (TaskCategory.REASONING, ReasoningComplexity.COMPLEX): QuantizationConfig(
            model_quantization=QuantizationType.FP16,
            kv_cache_quantization=KVCacheQuantization.NONE,
            context_window=16384,
            expected_throughput="40-70 tok/s",
            memory_per_model="20-32GB",
            models_per_40gb=1,
            quality_impact="None",
        ),
        (TaskCategory.RESEARCH, ReasoningComplexity.COMPLEX): QuantizationConfig(
            model_quantization=QuantizationType.FP16,
            kv_cache_quantization=KVCacheQuantization.NONE,
            context_window=16384,
            expected_throughput="40-70 tok/s",
            memory_per_model="20-32GB",
            models_per_40gb=1,
            quality_impact="None",
        ),
        (TaskCategory.RESEARCH, ReasoningComplexity.CRITICAL): QuantizationConfig(
            model_quantization=QuantizationType.FP32,
            kv_cache_quantization=KVCacheQuantization.NONE,
            context_window=32000,
            expected_throughput="10-20 tok/s",
            memory_per_model="40GB",
            models_per_40gb=1,
            quality_impact="None",
        ),
        (TaskCategory.SECURITY, ReasoningComplexity.CRITICAL): QuantizationConfig(
            model_quantization=QuantizationType.FP32,
            kv_cache_quantization=KVCacheQuantization.NONE,
            context_window=32000,
            expected_throughput="10-20 tok/s",
            memory_per_model="40GB",
            models_per_40gb=1,
            quality_impact="None",
        ),
    }

    DEFAULT_BY_TIER = {
        ModelTier.FAST_CHEAP: QuantizationConfig(
            model_quantization=QuantizationType.INT8,
            kv_cache_quantization=KVCacheQuantization.Q8_0,
            context_window=4096,
            expected_throughput="150-250 tok/s",
            memory_per_model="4-6GB",
            models_per_40gb=6,
            quality_impact="Low (~1-2%)",
        ),
        ModelTier.BALANCED: QuantizationConfig(
            model_quantization=QuantizationType.FP16,
            kv_cache_quantization=KVCacheQuantization.NONE,
            context_window=8192,
            expected_throughput="50-80 tok/s",
            memory_per_model="20-32GB",
            models_per_40gb=1,
            quality_impact="None",
        ),
        ModelTier.CAPABLE: QuantizationConfig(
            model_quantization=QuantizationType.FP16,
            kv_cache_quantization=KVCacheQuantization.NONE,
            context_window=16384,
            expected_throughput="40-70 tok/s",
            memory_per_model="20-32GB",
            models_per_40gb=1,
            quality_impact="None",
        ),
        ModelTier.EXTENDED: QuantizationConfig(
            model_quantization=QuantizationType.FP32,
            kv_cache_quantization=KVCacheQuantization.NONE,
            context_window=32000,
            expected_throughput="10-20 tok/s",
            memory_per_model="40GB",
            models_per_40gb=1,
            quality_impact="None",
        ),
    }

    @staticmethod
    def select_quantization(
        task_category: TaskCategory,
        reasoning_complexity: Optional[ReasoningComplexity] = None,
        model_tier: Optional[ModelTier] = None,
    ) -> QuantizationConfig:
        if reasoning_complexity is None:
            if task_category == TaskCategory.READ:
                reasoning_complexity = ReasoningComplexity.SIMPLE
            elif task_category in (TaskCategory.ANALYZE, TaskCategory.CODE):
                reasoning_complexity = ReasoningComplexity.MODERATE
            elif task_category in (TaskCategory.REASONING, TaskCategory.RESEARCH):
                reasoning_complexity = ReasoningComplexity.COMPLEX
            elif task_category == TaskCategory.SECURITY:
                reasoning_complexity = ReasoningComplexity.CRITICAL
            else:
                reasoning_complexity = ReasoningComplexity.MODERATE

        key = (task_category, reasoning_complexity)
        if key in QuantizationSelector.QUANTIZATION_MATRIX:
            return QuantizationSelector.QUANTIZATION_MATRIX[key]

        if model_tier is not None:
            return QuantizationSelector.DEFAULT_BY_TIER.get(
                model_tier, QuantizationSelector.DEFAULT_BY_TIER[ModelTier.BALANCED]
            )

        return QuantizationSelector.DEFAULT_BY_TIER[ModelTier.BALANCED]

    @staticmethod
    def get_config_summary(config: QuantizationConfig) -> str:
        return (
            f"Model: {config.model_quantization.value} | "
            f"KV-Cache: {config.kv_cache_quantization.value} | "
            f"Context: {config.context_window} tokens | "
            f"Throughput: {config.expected_throughput} | "
            f"Memory: {config.memory_per_model} | "
            f"Quality Impact: {config.quality_impact}"
        )

    @staticmethod
    def get_40gb_capacity_summary() -> str:
        return (
            "40GB GPU Capacity Summary (quality-first):\n"
            "  FAST_CHEAP (INT8 + q8_0):  6 models × 6GB\n"
            "  BALANCED/CAPABLE (FP16):   1 model × 20-32GB\n"
            "  EXTENDED (FP32):           1 model × 40GB\n"
        )

    @staticmethod
    def get_qwen_single_gpu_config() -> QuantizationConfig:
        return QuantizationConfig(
            model_quantization=QuantizationType.INT8,
            kv_cache_quantization=KVCacheQuantization.Q8_0,
            context_window=256000,
            expected_throughput="high prefill, quality-first decode",
            memory_per_model="20-28GB",
            models_per_40gb=1,
            quality_impact="Low (~1-2%)",
        )

    @staticmethod
    def get_single_gpu_deployment_string() -> str:
        return (
            "# Single-GPU quality-first Qwen 3.8 27B\n"
            "hercules --yolo \\\n"
            "  --model qwen-3.8-27b \\\n"
            "  --quantization int8 \\\n"
            "  --kv-quantization q8_0 \\\n"
            "  --context-window 256000\n"
        )
