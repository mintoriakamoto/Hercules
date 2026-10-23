"""Consciousness Trace: Record and replay conscious moments"""

import time
from collections import deque
from typing import Dict, List


class ConsciousnessTrace:
    """
    Record all conscious moments for debugging and analysis.

    Can replay: "What was the agent thinking?" at any point in time.
    """

    def __init__(self, max_moments: int = 5000):
        self.moments = deque(maxlen=max_moments)
        self.decisions = []
        self.memory_consolidations = []

    def record_conscious_moment(self, moment: Dict) -> None:
        """Log a moment of unified consciousness"""

        self.moments.append({
            'timestamp': time.time(),
            'moment': moment,
        })

    def record_decision(self, cycle: int, decision: Dict) -> None:
        """Log a conscious decision"""

        self.decisions.append({
            'cycle': cycle,
            'timestamp': time.time(),
            'decision': decision,
        })

    def get_consciousness_narrative(self, last_n_seconds: int = 60) -> str:
        """
        Narrative: "Here's what I was conscious of in last N seconds."
        """

        cutoff = time.time() - last_n_seconds
        recent = [m for m in self.moments if m['timestamp'] > cutoff]

        narrative = []

        for moment in recent:
            moment_data = moment['moment']
            narrative.append(
                f"[{moment['timestamp']:.2f}] "
                f"Moment recorded (coherence: {moment_data.get('coherence', 'unknown')})"
            )

        return "\n".join(narrative) if narrative else "No recent conscious moments"

    def export_consciousness(self) -> Dict:
        """Export full consciousness trace for analysis"""

        return {
            'moments': list(self.moments),
            'decisions': self.decisions,
            'memory_consolidations': self.memory_consolidations,
            'total_duration_seconds': (
                list(self.moments)[-1]['timestamp'] - list(self.moments)[0]['timestamp']
                if self.moments else 0
            ),
        }
