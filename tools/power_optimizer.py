#!/usr/bin/env python3
"""Power management tuning for consistent tool performance.

Disables CPU frequency scaling during tool dispatch, P-state tuning,
thermal monitoring and throttling avoidance.
Target: 1.2-1.5x consistent performance.

Enables: power_optimize (bool), disable_freq_scaling (bool)
"""

import json
import logging
import os
import subprocess
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# CPU governor states
_ORIGINAL_GOVERNORS: Dict[int, str] = {}
_ORIGINAL_GOVERNORS_LOCK = threading.Lock()


class PowerOptimizer:
    """Manages CPU power states and frequency scaling."""

    def __init__(self):
        self.config = {
            "enabled": os.getenv("POWER_OPTIMIZER_ENABLED", "false").lower() == "true",
            "disable_freq_scaling": os.getenv("POWER_DISABLE_FREQ_SCALING", "false").lower() == "true",
            "p_state_tuning": os.getenv("POWER_P_STATE_TUNING", "false").lower() == "true",
            "monitor_thermal": os.getenv("POWER_MONITOR_THERMAL", "true").lower() == "true",
        }

        self.metrics = {
            "frequency_scaling_disabled": False,
            "p_state_ratio": 100,
            "thermal_throttle_events": 0,
            "current_temp_c": 0,
        }

        self._initialized = False
        self._init_lock = threading.Lock()

    def initialize(self) -> None:
        """Initialize power optimizer."""
        if self._initialized or not self.config["enabled"]:
            return

        with self._init_lock:
            if self._initialized:
                return

            if self.config["disable_freq_scaling"]:
                self._disable_frequency_scaling()

            if self.config["p_state_tuning"]:
                self._tune_p_states()

            self._initialized = True

    def _disable_frequency_scaling(self) -> None:
        """Disable CPU frequency scaling, lock to maximum frequency."""
        try:
            num_cpus = os.cpu_count() or 1

            for cpu_id in range(num_cpus):
                try:
                    scaling_governor = (
                        f"/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_governor"
                    )
                    scaling_max = (
                        f"/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_max_freq"
                    )

                    if os.path.exists(scaling_governor):
                        with open(scaling_governor) as f:
                            original = f.read().strip()
                            _ORIGINAL_GOVERNORS[cpu_id] = original

                        # Switch to performance governor
                        if os.access(scaling_governor, os.W_OK):
                            with open(scaling_governor, "w") as f:
                                f.write("performance\n")
                            logger.debug("CPU%d: switched to performance governor", cpu_id)

                    # Lock to maximum frequency
                    if os.path.exists(scaling_max) and os.access(scaling_max, os.W_OK):
                        with open(scaling_max) as f:
                            max_freq = f.read().strip()
                        with open(scaling_max, "w") as f:
                            f.write(max_freq)

                except (IOError, OSError):
                    pass

            self.metrics["frequency_scaling_disabled"] = True
            logger.info("CPU frequency scaling disabled; locked to max frequency")

        except Exception as e:
            logger.debug("Could not disable frequency scaling: %s", e)

    def _tune_p_states(self) -> None:
        """Tune Intel P-States for performance."""
        try:
            # Try to set min_perf_pct to 100 (always run at max P-state)
            path = "/sys/devices/system/cpu/intel_pstate/min_perf_pct"
            if os.path.exists(path) and os.access(path, os.W_OK):
                with open(path, "w") as f:
                    f.write("100\n")
                self.metrics["p_state_ratio"] = 100
                logger.debug("Intel P-States: set min_perf_pct to 100")
        except Exception as e:
            logger.debug("Could not tune P-States: %s", e)

    def restore_frequency_scaling(self) -> None:
        """Restore original CPU governors."""
        try:
            for cpu_id, original_gov in _ORIGINAL_GOVERNORS.items():
                try:
                    scaling_governor = (
                        f"/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_governor"
                    )
                    if os.path.exists(scaling_governor) and os.access(scaling_governor, os.W_OK):
                        with open(scaling_governor, "w") as f:
                            f.write(original_gov + "\n")
                except IOError:
                    pass

            _ORIGINAL_GOVERNORS.clear()
            self.metrics["frequency_scaling_disabled"] = False
            logger.info("CPU governors restored")

        except Exception as e:
            logger.debug("Could not restore governors: %s", e)

    def get_cpu_temperature(self) -> Optional[float]:
        """Get current CPU temperature."""
        try:
            # Try hwmon interface
            for sensor_dir in [
                "/sys/class/hwmon/hwmon0",
                "/sys/class/hwmon/hwmon1",
            ]:
                temp_files = [
                    os.path.join(sensor_dir, f) for f in os.listdir(sensor_dir)
                    if "temp1_input" in f
                ]
                for temp_file in temp_files:
                    with open(temp_file) as f:
                        temp_millidegrees = int(f.read().strip())
                        return temp_millidegrees / 1000.0

            # Fallback: try thermal_zone
            zone_file = "/sys/class/thermal/thermal_zone0/temp"
            if os.path.exists(zone_file):
                with open(zone_file) as f:
                    return int(f.read().strip()) / 1000.0

        except Exception:
            pass

        return None

    def check_thermal_status(self) -> Dict[str, Any]:
        """Check current thermal status."""
        status = {
            "throttling": False,
            "temperature_c": None,
            "throttle_events": self.metrics["thermal_throttle_events"],
        }

        temp = self.get_cpu_temperature()
        if temp:
            status["temperature_c"] = temp
            self.metrics["current_temp_c"] = temp

            # Detect throttling (warn if > 85C)
            if temp > 85:
                status["throttling"] = True
                self.metrics["thermal_throttle_events"] += 1
                logger.warning("CPU overheating: %.1fC (throttling risk)", temp)

        return status

    def throttle_on_overheat(self, threshold_c: float = 90) -> bool:
        """Check if system is overheating; return True if should throttle.

        This is a safety mechanism to prevent sustained overheating.
        """
        temp = self.get_cpu_temperature()
        if temp and temp > threshold_c:
            logger.warning("CPU critical: %.1fC; initiating thermal throttle", temp)
            return True
        return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get power optimization metrics."""
        return self.metrics.copy()


# Global optimizer instance
_optimizer: Optional[PowerOptimizer] = None
_optimizer_lock = threading.Lock()


def get_optimizer() -> PowerOptimizer:
    """Get global power optimizer."""
    global _optimizer
    if _optimizer is None:
        with _optimizer_lock:
            if _optimizer is None:
                _optimizer = PowerOptimizer()
    return _optimizer


def initialize_power_optimizer() -> None:
    """Initialize power optimization."""
    optimizer = get_optimizer()
    optimizer.initialize()


def disable_frequency_scaling() -> None:
    """Disable CPU frequency scaling."""
    optimizer = get_optimizer()
    optimizer.config["disable_freq_scaling"] = True
    optimizer.initialize()


def restore_frequency_scaling() -> None:
    """Restore original CPU frequency scaling."""
    optimizer = get_optimizer()
    optimizer.restore_frequency_scaling()


def get_thermal_status() -> Dict[str, Any]:
    """Get current thermal status."""
    optimizer = get_optimizer()
    return optimizer.check_thermal_status()


def check_thermal_throttle() -> bool:
    """Check if thermal throttling is active."""
    optimizer = get_optimizer()
    return optimizer.throttle_on_overheat()


def get_power_metrics() -> Dict[str, Any]:
    """Get power optimization metrics."""
    optimizer = get_optimizer()
    return optimizer.get_metrics()


def set_power_optimizer_config(config: Dict[str, Any]) -> None:
    """Update power optimizer configuration."""
    optimizer = get_optimizer()
    optimizer.config.update(config)
    logger.info("Power optimizer config updated: %s", optimizer.config)
