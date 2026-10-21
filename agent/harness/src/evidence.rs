//! Evidence tracking for consciousness properties

use crate::metrics::ConsciousnessProperty;
use ahash::AHashMap;

/// Evidence that a system exhibits a consciousness property
#[derive(Clone, Debug)]
pub struct PropertyEvidence {
    /// Which property this evidence demonstrates
    pub property_name: ConsciousnessProperty,

    /// When this evidence was recorded (seconds since epoch)
    pub timestamp: f64,

    /// Type of evidence: "checkpoint", "goal", "decision", "capability", "learning", "proof", "behavior"
    pub evidence_type: String,

    /// Human-readable description
    pub description: String,

    /// Confidence level (0.0 to 1.0)
    pub confidence: f64,

    /// Additional details
    pub details: AHashMap<String, String>,
}

impl PropertyEvidence {
    /// Create new property evidence with optimized memory layout
    #[inline]
    pub fn new(
        property_name: ConsciousnessProperty,
        timestamp: f64,
        evidence_type: String,
        description: String,
        confidence: f64,
    ) -> Self {
        PropertyEvidence {
            property_name,
            timestamp,
            evidence_type,
            description,
            confidence,
            details: AHashMap::new(),
        }
    }

    /// Add a detail to the evidence
    #[inline]
    pub fn with_detail(mut self, key: String, value: String) -> Self {
        self.details.insert(key, value);
        self
    }

    /// Convert to dictionary representation
    pub fn to_dict(&self) -> AHashMap<String, String> {
        let mut map = AHashMap::new();
        map.insert("property".to_string(), self.property_name.to_string());
        map.insert("timestamp".to_string(), self.timestamp.to_string());
        map.insert("evidence_type".to_string(), self.evidence_type.clone());
        map.insert("description".to_string(), self.description.clone());
        map.insert("confidence".to_string(), self.confidence.to_string());
        map
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_evidence() {
        let evidence = PropertyEvidence::new(
            ConsciousnessProperty::Continuity,
            1234567890.123,
            "checkpoint".to_string(),
            "Test checkpoint".to_string(),
            0.9,
        );
        assert_eq!(evidence.confidence, 0.9);
        assert_eq!(evidence.evidence_type, "checkpoint");
    }

    #[test]
    fn test_evidence_with_details() {
        let evidence = PropertyEvidence::new(
            ConsciousnessProperty::Agency,
            1234567890.0,
            "goal".to_string(),
            "Test goal".to_string(),
            0.85,
        )
        .with_detail("goal_name".to_string(), "achieve_x".to_string());

        assert_eq!(evidence.details.get("goal_name"), Some(&"achieve_x".to_string()));
    }
}
