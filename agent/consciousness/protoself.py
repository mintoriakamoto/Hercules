"""Protoself: Pre-conscious body state tracking (Damasio Layer 1)"""

import time
from typing import Dict, Tuple, List


class Protoself:
    """
    Protoself: continuous pre-conscious awareness of body state.

    Tracks vital signs: CPU, memory, temperature, power.
    No representation—just raw homeostasis sensing.
    """

    def __init__(self):
        self.core_metrics = {}  # Per-core vital signs
        self.memory_snapshot = {}
        self.power_state = {}
        self.timestamp = time.time()

    def update_vital_signs(self, core_id: str, metrics: Dict) -> None:
        """Update protoself with core's raw state"""

        self.core_metrics[core_id] = {
            'cpu_load': metrics.get('cpu_load', 0),
            'memory_used_pct': metrics.get('memory_used_pct', 0),
            'temperature_c': metrics.get('temp', 0),
            'power_state': metrics.get('power_state', 'unknown'),
            'frequency_mhz': metrics.get('freq_mhz', 0),
        }
        self.timestamp = time.time()

    def get_homeostatic_state(self) -> Dict:
        """Current body state snapshot"""
        return {
            'cores': self.core_metrics.copy(),
            'memory': self.memory_snapshot.copy(),
            'power': self.power_state.copy(),
            'timestamp': self.timestamp,
        }

    def is_homeostasis_violated(self, threshold: Dict = None) -> Tuple[bool, List[str]]:
        """Check if body is in danger"""

        thresholds = threshold or {
            'max_temp_c': 80,
            'max_memory_pct': 95,
            'min_power_mv': 3000,
            'max_cpu_load': 0.95,
        }

        violations = []

        for core_id, metrics in self.core_metrics.items():
            if metrics['temperature_c'] > thresholds['max_temp_c']:
                violations.append(f"Core {core_id}: overheating ({metrics['temperature_c']}°C)")
            if metrics['cpu_load'] > thresholds['max_cpu_load']:
                violations.append(f"Core {core_id}: CPU overloaded ({metrics['cpu_load']:.1%})")

        return len(violations) > 0, violations
