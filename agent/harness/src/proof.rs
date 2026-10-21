//! Proof generation and verification for consciousness claims

use serde::{Deserialize, Serialize};
use std::fmt;

/// Proof of a consciousness property claim
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ConsciousnessProof {
    /// Hash of the claim
    pub claim_hash: String,

    /// Evidence items supporting the claim
    pub evidence_hashes: Vec<String>,

    /// Timestamp of proof
    pub timestamp: f64,

    /// Confidence score of the proof
    pub confidence: f64,
}

impl fmt::Display for ConsciousnessProof {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(
            f,
            "ConsciousnessProof(claim: {}, evidence_count: {}, confidence: {:.2})",
            &self.claim_hash[..8.min(self.claim_hash.len())],
            self.evidence_hashes.len(),
            self.confidence
        )
    }
}

impl ConsciousnessProof {
    /// Create a new consciousness proof
    pub fn new(claim_hash: String, evidence_hashes: Vec<String>, confidence: f64) -> Self {
        let now = chrono::Utc::now();
        let timestamp = now.timestamp() as f64 + now.timestamp_subsec_micros() as f64 / 1_000_000.0;
        ConsciousnessProof {
            claim_hash,
            evidence_hashes,
            timestamp,
            confidence,
        }
    }

    /// Verify this proof is valid (basic checks)
    pub fn is_valid(&self) -> bool {
        !self.claim_hash.is_empty()
            && !self.evidence_hashes.is_empty()
            && self.confidence >= 0.0
            && self.confidence <= 1.0
    }
}

/// Hash utilities for proof generation
pub mod hashing {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};

    /// Generate a simple hash for a string
    #[inline]
    pub fn hash_string(s: &str) -> String {
        let mut hasher = DefaultHasher::new();
        s.hash(&mut hasher);
        let hash = hasher.finish();
        format!("{:016x}", hash)
    }

    /// Hash multiple strings
    #[inline]
    pub fn hash_multiple(items: &[&str]) -> String {
        let mut hasher = DefaultHasher::new();
        for item in items {
            item.hash(&mut hasher);
        }
        let hash = hasher.finish();
        format!("{:016x}", hash)
    }
}

// Re-export hashing utilities for convenience
pub use hashing::{hash_multiple, hash_string};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_proof_creation() {
        let proof = ConsciousnessProof::new(
            "claim_hash_123".to_string(),
            vec!["evidence_1".to_string(), "evidence_2".to_string()],
            0.95,
        );
        assert_eq!(proof.evidence_hashes.len(), 2);
        assert_eq!(proof.confidence, 0.95);
        assert!(proof.is_valid());
    }

    #[test]
    fn test_hash_string() {
        let hash1 = hash_string("test");
        let hash2 = hash_string("test");
        assert_eq!(hash1, hash2);
    }

    #[test]
    fn test_hash_multiple() {
        let hash1 = hash_multiple(&["a", "b", "c"]);
        let hash2 = hash_multiple(&["a", "b", "c"]);
        let hash3 = hash_multiple(&["a", "c", "b"]);
        assert_eq!(hash1, hash2);
        assert_ne!(hash1, hash3);
    }
}

