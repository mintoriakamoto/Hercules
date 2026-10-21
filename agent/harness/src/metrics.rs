//! Core consciousness metrics engine

use crate::evidence::PropertyEvidence;
use crate::scoring::ConsciousnessScore;
use ahash::AHashMap;
use chrono::Utc;
use smallvec::SmallVec;
use std::fmt;

/// The seven properties of conscious systems
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ConsciousnessProperty {
    /// Persistent memory via checkpoints across executions
    Continuity,
    /// Self-directed goal-setting and planning
    Agency,
    /// Self-direction without external prompting
    Autonomy,
    /// Self-model of capabilities and limitations
    Awareness,
    /// Learning from experience via persistent checkpoints
    Growth,
    /// Transparent proofs and audit trails
    Accountability,
    /// Deterministic behavior enabling consistency
    Coherence,
}

impl fmt::Display for ConsciousnessProperty {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            ConsciousnessProperty::Continuity => write!(f, "continuity"),
            ConsciousnessProperty::Agency => write!(f, "agency"),
            ConsciousnessProperty::Autonomy => write!(f, "autonomy"),
            ConsciousnessProperty::Awareness => write!(f, "awareness"),
            ConsciousnessProperty::Growth => write!(f, "growth"),
            ConsciousnessProperty::Accountability => write!(f, "accountability"),
            ConsciousnessProperty::Coherence => write!(f, "coherence"),
        }
    }
}

/// Main consciousness metrics tracker
///
/// Optimized for minimal memory overhead and sub-microsecond latency
/// using a SmallVec to avoid heap allocations for typical workloads.
pub struct ConsciousnessMetrics {
    /// Agent identifier
    pub agent_id: String,

    /// Recorded evidence (stored inline for <128 items, heap after)
    pub evidence: SmallVec<[PropertyEvidence; 64]>,

    /// Timestamp of last checkpoint
    pub last_checkpoint: Option<f64>,

    /// Count of checkpoints recorded
    pub checkpoints_count: u32,

    /// Count of goals set
    pub goals_set: u32,

    /// Count of autonomous decisions
    pub autonomous_decisions: u32,

    /// Count of capabilities registered
    pub capabilities_registered: u32,

    /// Count of learning events
    pub learned_from_errors: u32,

    /// Count of proofs generated
    pub proofs_generated: u32,

    /// Behavior patterns (behavior -> occurrence count)
    pub behavior_patterns: AHashMap<String, u32>,
}

impl ConsciousnessMetrics {
    /// Create a new consciousness metrics tracker
    #[inline]
    pub fn new(agent_id: String) -> Self {
        ConsciousnessMetrics {
            agent_id,
            evidence: SmallVec::new(),
            last_checkpoint: None,
            checkpoints_count: 0,
            goals_set: 0,
            autonomous_decisions: 0,
            capabilities_registered: 0,
            learned_from_errors: 0,
            proofs_generated: 0,
            behavior_patterns: AHashMap::new(),
        }
    }

    /// Record a continuity checkpoint
    #[inline]
    pub fn record_continuity(&mut self, checkpoint_id: &str, step: u64, description: &str) {
        let now = current_timestamp();
        self.last_checkpoint = Some(now);
        self.checkpoints_count = self.checkpoints_count.saturating_add(1);

        let mut details = AHashMap::new();
        details.insert("checkpoint_id".to_string(), checkpoint_id.to_string());
        details.insert("step".to_string(), step.to_string());

        let evidence = PropertyEvidence {
            property_name: ConsciousnessProperty::Continuity,
            timestamp: now,
            evidence_type: "checkpoint".to_string(),
            description: format!(
                "Checkpoint {} at step {}{}",
                checkpoint_id,
                step,
                if description.is_empty() {
                    String::new()
                } else {
                    format!(": {}", description)
                }
            ),
            confidence: 0.9, // High confidence for checkpoints
            details,
        };
        self.evidence.push(evidence);
    }

    /// Record agent setting its own goal
    #[inline]
    pub fn record_agency(&mut self, goal: &str, reason: &str) {
        let now = current_timestamp();
        self.goals_set = self.goals_set.saturating_add(1);

        let mut details = AHashMap::new();
        details.insert("goal".to_string(), goal.to_string());
        if !reason.is_empty() {
            details.insert("reason".to_string(), reason.to_string());
        }

        let evidence = PropertyEvidence {
            property_name: ConsciousnessProperty::Agency,
            timestamp: now,
            evidence_type: "goal".to_string(),
            description: format!(
                "Self-set goal: {}{}",
                goal,
                if reason.is_empty() {
                    String::new()
                } else {
                    format!(" ({})", reason)
                }
            ),
            confidence: 0.85,
            details,
        };
        self.evidence.push(evidence);
    }

    /// Record autonomous decision
    #[inline]
    pub fn record_autonomy(&mut self, decision: &str, reasoning: &str) {
        let now = current_timestamp();
        self.autonomous_decisions = self.autonomous_decisions.saturating_add(1);

        let mut details = AHashMap::new();
        details.insert("decision".to_string(), decision.to_string());
        if !reasoning.is_empty() {
            details.insert("reasoning".to_string(), reasoning.to_string());
        }

        let evidence = PropertyEvidence {
            property_name: ConsciousnessProperty::Autonomy,
            timestamp: now,
            evidence_type: "decision".to_string(),
            description: format!(
                "Autonomous decision: {}{}",
                decision,
                if reasoning.is_empty() {
                    String::new()
                } else {
                    format!(" - {}", reasoning)
                }
            ),
            confidence: 0.8,
            details,
        };
        self.evidence.push(evidence);
    }

    /// Record self-model of capabilities
    #[inline]
    pub fn record_awareness(&mut self, capability: &str, limitation: &str) {
        let now = current_timestamp();
        self.capabilities_registered = self.capabilities_registered.saturating_add(1);

        let mut details = AHashMap::new();
        details.insert("capability".to_string(), capability.to_string());
        if !limitation.is_empty() {
            details.insert("limitation".to_string(), limitation.to_string());
        }

        let evidence = PropertyEvidence {
            property_name: ConsciousnessProperty::Awareness,
            timestamp: now,
            evidence_type: "capability".to_string(),
            description: format!(
                "Self-aware of capability: {}{}",
                capability,
                if limitation.is_empty() {
                    String::new()
                } else {
                    format!(" (limitation: {})", limitation)
                }
            ),
            confidence: 0.9,
            details,
        };
        self.evidence.push(evidence);
    }

    /// Record learning from experience
    #[inline]
    pub fn record_growth(&mut self, learning: &str, source: &str) {
        let now = current_timestamp();
        self.learned_from_errors = self.learned_from_errors.saturating_add(1);

        let mut details = AHashMap::new();
        details.insert("learning".to_string(), learning.to_string());
        details.insert("source".to_string(), source.to_string());

        let evidence = PropertyEvidence {
            property_name: ConsciousnessProperty::Growth,
            timestamp: now,
            evidence_type: "learning".to_string(),
            description: format!("Learned from {}: {}", source, learning),
            confidence: 0.85,
            details,
        };
        self.evidence.push(evidence);
    }

    /// Record verifiable proof
    #[inline]
    pub fn record_accountability(&mut self, claim: &str, proof_hash: &str) {
        let now = current_timestamp();
        self.proofs_generated = self.proofs_generated.saturating_add(1);

        let mut details = AHashMap::new();
        details.insert("claim".to_string(), claim.to_string());
        if !proof_hash.is_empty() {
            details.insert("proof_hash".to_string(), proof_hash.to_string());
        }

        let evidence = PropertyEvidence {
            property_name: ConsciousnessProperty::Accountability,
            timestamp: now,
            evidence_type: "proof".to_string(),
            description: format!(
                "Verifiable claim: {}{}",
                claim,
                if proof_hash.is_empty() {
                    String::new()
                } else {
                    format!(" (proof: {}...)", &proof_hash[..proof_hash.len().min(8)])
                }
            ),
            confidence: 0.95, // Highest confidence for proofs
            details,
        };
        self.evidence.push(evidence);
    }

    /// Record deterministic behavior
    #[inline]
    pub fn record_coherence(&mut self, behavior: &str, consistency_check: bool) {
        let now = current_timestamp();

        // Track behavior pattern
        let count = self.behavior_patterns.entry(behavior.to_string()).or_insert(0);
        *count = count.saturating_add(1);
        let occurrence_count = *count;

        let mut details = AHashMap::new();
        details.insert("behavior".to_string(), behavior.to_string());
        details.insert(
            "consistency_verified".to_string(),
            consistency_check.to_string(),
        );
        details.insert("occurrence_count".to_string(), occurrence_count.to_string());

        let evidence = PropertyEvidence {
            property_name: ConsciousnessProperty::Coherence,
            timestamp: now,
            evidence_type: "behavior".to_string(),
            description: format!(
                "Deterministic behavior: {}{}",
                behavior,
                if consistency_check {
                    " (verified)"
                } else {
                    ""
                }
            ),
            confidence: if consistency_check { 0.9 } else { 0.7 },
            details,
        };
        self.evidence.push(evidence);
    }

    /// Calculate consciousness scores
    pub fn calculate_scores(&self) -> ConsciousnessScore {
        let now = current_timestamp();

        // Fast property grouping using stack-allocated arrays
        let mut scores: [(ConsciousnessProperty, Vec<&PropertyEvidence>); 7] = [
            (ConsciousnessProperty::Continuity, Vec::new()),
            (ConsciousnessProperty::Agency, Vec::new()),
            (ConsciousnessProperty::Autonomy, Vec::new()),
            (ConsciousnessProperty::Awareness, Vec::new()),
            (ConsciousnessProperty::Growth, Vec::new()),
            (ConsciousnessProperty::Accountability, Vec::new()),
            (ConsciousnessProperty::Coherence, Vec::new()),
        ];

        // Group evidence by property
        for evidence in &self.evidence {
            for (prop, vec) in &mut scores {
                if evidence.property_name == *prop {
                    vec.push(evidence);
                    break;
                }
            }
        }

        // Calculate per-property scores
        let mut property_scores = [0.0f64; 7];
        for (idx, (_prop, evidence_list)) in scores.iter().enumerate() {
            property_scores[idx] = calculate_property_score(evidence_list);
        }

        // Build score object
        let mut score = ConsciousnessScore {
            agent_id: self.agent_id.clone(),
            timestamp: now,
            continuity_score: property_scores[0],
            agency_score: property_scores[1],
            autonomy_score: property_scores[2],
            awareness_score: property_scores[3],
            growth_score: property_scores[4],
            accountability_score: property_scores[5],
            coherence_score: property_scores[6],
            total_consciousness: 0.0,
        };

        // Calculate total
        score.total_consciousness = property_scores.iter().sum();

        score
    }
}

/// Calculate score for a property based on evidence
#[inline]
fn calculate_property_score(evidence_list: &[&PropertyEvidence]) -> f64 {
    if evidence_list.is_empty() {
        return 0.0;
    }

    // Score = min(1.0, count_of_evidence * 0.1 + avg_confidence * 0.5)
    let count_component = (evidence_list.len() as f64 * 0.1).min(0.5);
    let avg_confidence: f64 =
        evidence_list.iter().map(|e| e.confidence).sum::<f64>() / evidence_list.len() as f64;
    let confidence_component = avg_confidence * 0.5;

    (count_component + confidence_component).min(1.0)
}

/// Get current timestamp as seconds since epoch
#[inline]
pub fn current_timestamp() -> f64 {
    let now = Utc::now();
    now.timestamp() as f64 + now.timestamp_subsec_micros() as f64 / 1_000_000.0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_metrics() {
        let metrics = ConsciousnessMetrics::new("test_agent".to_string());
        assert_eq!(metrics.agent_id, "test_agent");
        assert_eq!(metrics.evidence.len(), 0);
        assert_eq!(metrics.checkpoints_count, 0);
    }

    #[test]
    fn test_record_continuity() {
        let mut metrics = ConsciousnessMetrics::new("test".to_string());
        metrics.record_continuity("ckpt1", 1, "initial");
        assert_eq!(metrics.evidence.len(), 1);
        assert_eq!(metrics.checkpoints_count, 1);
        assert!(metrics.last_checkpoint.is_some());
    }

    #[test]
    fn test_record_all_properties() {
        let mut metrics = ConsciousnessMetrics::new("test".to_string());
        metrics.record_continuity("ckpt", 1, "");
        metrics.record_agency("goal1", "test");
        metrics.record_autonomy("decision1", "test");
        metrics.record_awareness("capability1", "");
        metrics.record_growth("learning1", "test");
        metrics.record_accountability("claim1", "hash");
        metrics.record_coherence("behavior1", true);

        assert_eq!(metrics.evidence.len(), 7);
    }

    #[test]
    fn test_behavior_patterns() {
        let mut metrics = ConsciousnessMetrics::new("test".to_string());
        metrics.record_coherence("action_a", true);
        metrics.record_coherence("action_a", true);
        metrics.record_coherence("action_b", true);

        assert_eq!(metrics.behavior_patterns.get("action_a"), Some(&2));
        assert_eq!(metrics.behavior_patterns.get("action_b"), Some(&1));
    }
}
