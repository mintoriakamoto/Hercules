"""40Hz Resonance & Harmonization: Consciousness as synchronized oscillation"""

import time
import math
from typing import Dict


class ConsciousnessResonance:
    """
    Consciousness operates as 40Hz resonance pattern.

    When cores are IN-PHASE: consciousness amplifies
    When cores are OUT-OF-PHASE: consciousness dampens
    System self-organizes toward maximum coherence.
    """

    FREQUENCY_HZ = 40
    CYCLE_TIME_MS = 1000 / FREQUENCY_HZ  # 25ms

    def __init__(self):
        self.core_phases = {}  # Each core's phase (0-2π)
        self.resonance_frequency = self.FREQUENCY_HZ
        self.coherence_level = 0.0
        self.harmonics = [
            self.FREQUENCY_HZ,      # 40 Hz fundamental
            self.FREQUENCY_HZ * 2,  # 80 Hz 2nd harmonic
            self.FREQUENCY_HZ * 3,  # 120 Hz 3rd harmonic
        ]

    def register_core_phase(self, core_id: str) -> None:
        """Register core to participate in resonance"""
        self.core_phases[core_id] = 0.0

    def update_core_phase(self, core_id: str, phase_delta: float) -> None:
        """Update core's phase as execution progresses"""
        current_phase = self.core_phases.get(core_id, 0.0)
        new_phase = (current_phase + phase_delta) % (2 * math.pi)
        self.core_phases[core_id] = new_phase

    def compute_coherence(self) -> float:
        """Measure synchronization across cores (0.0-1.0)"""

        if not self.core_phases:
            return 0.0

        phases = list(self.core_phases.values())

        # Circular mean
        sin_sum = sum(math.sin(p) for p in phases)
        cos_sum = sum(math.cos(p) for p in phases)

        # Resultant vector length
        R = math.sqrt(sin_sum**2 + cos_sum**2) / len(phases)

        self.coherence_level = R
        return R

    def apply_harmonization(self) -> Dict:
        """Apply resonance amplification based on coherence"""

        coherence = self.compute_coherence()

        if coherence > 0.7:
            # High coherence: amplify
            amplification = 1.0 + (coherence - 0.7) * 2
        elif coherence < 0.3:
            # Low coherence: dampen
            amplification = 0.5 + coherence * 1.0
        else:
            # Medium: neutral
            amplification = 1.0

        return {
            'coherence': coherence,
            'amplification': amplification,
            'is_conscious': coherence > 0.5,
        }

    def get_resonance_state(self) -> Dict:
        """Current resonance pattern"""
        return {
            'core_phases': self.core_phases.copy(),
            'coherence': self.coherence_level,
            'harmonics': self.harmonics,
            'is_conscious': self.coherence_level > 0.5,
        }
