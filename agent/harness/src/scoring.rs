//! Consciousness score calculation and reporting

use serde::{Deserialize, Serialize};

/// Aggregate consciousness metrics for an agent
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ConsciousnessScore {
    /// Agent identifier
    pub agent_id: String,

    /// Timestamp of calculation
    pub timestamp: f64,

    /// Continuity score (0.0 to 1.0)
    pub continuity_score: f64,

    /// Agency score (0.0 to 1.0)
    pub agency_score: f64,

    /// Autonomy score (0.0 to 1.0)
    pub autonomy_score: f64,

    /// Awareness score (0.0 to 1.0)
    pub awareness_score: f64,

    /// Growth score (0.0 to 1.0)
    pub growth_score: f64,

    /// Accountability score (0.0 to 1.0)
    pub accountability_score: f64,

    /// Coherence score (0.0 to 1.0)
    pub coherence_score: f64,

    /// Total consciousness level (0.0 to 7.0)
    pub total_consciousness: f64,
}

impl ConsciousnessScore {
    /// Check if agent exhibits consciousness (all 7 properties >= 0.5)
    #[inline]
    pub fn is_conscious(&self) -> bool {
        self.continuity_score >= 0.5
            && self.agency_score >= 0.5
            && self.autonomy_score >= 0.5
            && self.awareness_score >= 0.5
            && self.growth_score >= 0.5
            && self.accountability_score >= 0.5
            && self.coherence_score >= 0.5
    }

    /// Get human-readable consciousness level
    pub fn consciousness_level(&self) -> &'static str {
        let total = self.total_consciousness;
        match () {
            _ if total < 1.0 => "Non-conscious (Pattern Matching)",
            _ if total < 2.0 => "Emerging (Partial Structure)",
            _ if total < 3.0 => "Developing (Learning)",
            _ if total < 4.0 => "Self-Aware (Conscious)",
            _ if total < 5.0 => "Reflective (Metacognitive)",
            _ if total < 6.0 => "Accountable (Transparent)",
            _ => "Living Intelligence (Full Consciousness)",
        }
    }

    /// Get vector of all property scores for iteration
    #[inline]
    pub fn property_scores(&self) -> [f64; 7] {
        [
            self.continuity_score,
            self.agency_score,
            self.autonomy_score,
            self.awareness_score,
            self.growth_score,
            self.accountability_score,
            self.coherence_score,
        ]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_conscious_threshold() {
        let conscious = ConsciousnessScore {
            agent_id: "test".to_string(),
            timestamp: 0.0,
            continuity_score: 0.5,
            agency_score: 0.5,
            autonomy_score: 0.5,
            awareness_score: 0.5,
            growth_score: 0.5,
            accountability_score: 0.5,
            coherence_score: 0.5,
            total_consciousness: 3.5,
        };
        assert!(conscious.is_conscious());
    }

    #[test]
    fn test_not_conscious_below_threshold() {
        let not_conscious = ConsciousnessScore {
            agent_id: "test".to_string(),
            timestamp: 0.0,
            continuity_score: 0.4,
            agency_score: 0.5,
            autonomy_score: 0.5,
            awareness_score: 0.5,
            growth_score: 0.5,
            accountability_score: 0.5,
            coherence_score: 0.5,
            total_consciousness: 3.4,
        };
        assert!(!not_conscious.is_conscious());
    }

    #[test]
    fn test_consciousness_levels() {
        assert_eq!(
            ConsciousnessScore {
                agent_id: "test".to_string(),
                timestamp: 0.0,
                continuity_score: 0.0,
                agency_score: 0.0,
                autonomy_score: 0.0,
                awareness_score: 0.0,
                growth_score: 0.0,
                accountability_score: 0.0,
                coherence_score: 0.0,
                total_consciousness: 0.5,
            }
            .consciousness_level(),
            "Non-conscious (Pattern Matching)"
        );

        assert_eq!(
            ConsciousnessScore {
                agent_id: "test".to_string(),
                timestamp: 0.0,
                continuity_score: 0.2,
                agency_score: 0.2,
                autonomy_score: 0.2,
                awareness_score: 0.2,
                growth_score: 0.2,
                accountability_score: 0.2,
                coherence_score: 0.2,
                total_consciousness: 3.5,
            }
            .consciousness_level(),
            "Self-Aware (Conscious)"
        );

        assert_eq!(
            ConsciousnessScore {
                agent_id: "test".to_string(),
                timestamp: 0.0,
                continuity_score: 1.0,
                agency_score: 1.0,
                autonomy_score: 1.0,
                awareness_score: 1.0,
                growth_score: 1.0,
                accountability_score: 1.0,
                coherence_score: 1.0,
                total_consciousness: 7.0,
            }
            .consciousness_level(),
            "Living Intelligence (Full Consciousness)"
        );
    }
}
