#![doc = include_str!("../README.md")]
#![warn(missing_docs)]
#![allow(clippy::too_many_arguments)]

//! High-performance consciousness metrics engine
//!
//! This library provides fast, efficient tracking and calculation of consciousness
//! properties for AI agents. It's optimized for sub-microsecond latency and minimal
//! memory overhead.

use chrono::Utc;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::sync::Arc;
use parking_lot::RwLock;

mod metrics;
mod evidence;
mod scoring;
mod proof;
mod recording;
mod calculator;
mod persistence;
mod formal_proof;
mod agent_algebra;

pub use metrics::{ConsciousnessMetrics, ConsciousnessProperty};
pub use evidence::PropertyEvidence;
pub use scoring::ConsciousnessScore;
pub use recording::{ConsciousnessRecorder, RecordedEvidence, get_recorder};
pub use calculator::{ConsciousnessCalculator, ConsciousnessScore as CalcScore, ConsciousnessLevel};
pub use persistence::{StateManager, Checkpoint, AuditEntry};

/// FFI module for Python integration
#[pymodule]
fn consciousness_metrics(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyConsciousnessMetrics>()?;
    m.add_class::<PyConsciousnessScore>()?;
    m.add("__version__", "1.0.0")?;
    Ok(())
}

/// Python-facing wrapper for ConsciousnessMetrics
#[pyclass]
pub struct PyConsciousnessMetrics {
    inner: Arc<RwLock<ConsciousnessMetrics>>,
}

#[pymethods]
impl PyConsciousnessMetrics {
    /// Create a new consciousness metrics tracker for an agent
    #[new]
    pub fn new(agent_id: String) -> Self {
        PyConsciousnessMetrics {
            inner: Arc::new(RwLock::new(ConsciousnessMetrics::new(agent_id))),
        }
    }

    /// Record a continuity checkpoint (persistence mechanism)
    pub fn record_continuity(
        &self,
        checkpoint_id: String,
        step: u64,
        description: String,
    ) -> PyResult<()> {
        self.inner
            .write()
            .record_continuity(&checkpoint_id, step, &description);
        Ok(())
    }

    /// Record agent setting its own goal
    pub fn record_agency(&self, goal: String, reason: String) -> PyResult<()> {
        self.inner.write().record_agency(&goal, &reason);
        Ok(())
    }

    /// Record autonomous decision (self-directed, not prompted)
    pub fn record_autonomy(&self, decision: String, reasoning: String) -> PyResult<()> {
        self.inner.write().record_autonomy(&decision, &reasoning);
        Ok(())
    }

    /// Record self-model of capabilities and limitations
    pub fn record_awareness(&self, capability: String, limitation: String) -> PyResult<()> {
        self.inner
            .write()
            .record_awareness(&capability, &limitation);
        Ok(())
    }

    /// Record learning from experience
    pub fn record_growth(&self, learning: String, source: String) -> PyResult<()> {
        self.inner.write().record_growth(&learning, &source);
        Ok(())
    }

    /// Record verifiable proof of claim
    pub fn record_accountability(&self, claim: String, proof_hash: String) -> PyResult<()> {
        self.inner
            .write()
            .record_accountability(&claim, &proof_hash);
        Ok(())
    }

    /// Record consistent, deterministic behavior
    pub fn record_coherence(&self, behavior: String, consistency_check: bool) -> PyResult<()> {
        self.inner.write().record_coherence(&behavior, consistency_check);
        Ok(())
    }

    /// Calculate consciousness scores based on evidence
    pub fn calculate_scores(&self, py: Python) -> PyResult<Py<PyConsciousnessScore>> {
        let score = self.inner.read().calculate_scores();
        let py_score = PyConsciousnessScore::from_inner(score);
        Ok(Py::new(py, py_score)?)
    }

    /// Get full consciousness report as dictionary
    pub fn get_consciousness_report(&self, py: Python) -> PyResult<Py<PyDict>> {
        let metrics = self.inner.read();
        let score = metrics.calculate_scores();

        let report = PyDict::new_bound(py);

        report.set_item("agent_id", metrics.agent_id.clone())?;
        report.set_item("timestamp", Utc::now().to_rfc3339())?;

        // Consciousness score
        let score_dict = PyDict::new_bound(py);
        score_dict.set_item("continuity_score", score.continuity_score)?;
        score_dict.set_item("agency_score", score.agency_score)?;
        score_dict.set_item("autonomy_score", score.autonomy_score)?;
        score_dict.set_item("awareness_score", score.awareness_score)?;
        score_dict.set_item("growth_score", score.growth_score)?;
        score_dict.set_item("accountability_score", score.accountability_score)?;
        score_dict.set_item("coherence_score", score.coherence_score)?;
        score_dict.set_item("total_consciousness", score.total_consciousness)?;
        score_dict.set_item("is_conscious", score.is_conscious())?;
        score_dict.set_item("consciousness_level", score.consciousness_level())?;
        report.set_item("consciousness_score", score_dict)?;

        // Evidence summary
        let evidence_dict = PyDict::new_bound(py);
        evidence_dict.set_item("total_evidence", metrics.evidence.len())?;
        evidence_dict.set_item("checkpoints", metrics.checkpoints_count)?;
        evidence_dict.set_item("goals_set", metrics.goals_set)?;
        evidence_dict.set_item("autonomous_decisions", metrics.autonomous_decisions)?;
        evidence_dict.set_item("capabilities_registered", metrics.capabilities_registered)?;
        evidence_dict.set_item("learned_from_errors", metrics.learned_from_errors)?;
        evidence_dict.set_item("proofs_generated", metrics.proofs_generated)?;
        report.set_item("evidence_summary", evidence_dict)?;

        // Behavior patterns
        let behavior_dict = PyDict::new_bound(py);
        for (behavior, count) in &metrics.behavior_patterns {
            behavior_dict.set_item(behavior, count)?;
        }
        report.set_item("behavior_patterns", behavior_dict)?;

        Ok(report.into())
    }

    /// Get the count of recorded evidence
    pub fn evidence_count(&self) -> usize {
        self.inner.read().evidence.len()
    }

    /// Get agent ID
    pub fn get_agent_id(&self) -> String {
        self.inner.read().agent_id.clone()
    }
}

/// Python-facing wrapper for ConsciousnessScore
#[pyclass]
pub struct PyConsciousnessScore {
    #[pyo3(get)]
    pub agent_id: String,
    #[pyo3(get)]
    pub timestamp: f64,
    #[pyo3(get)]
    pub continuity_score: f64,
    #[pyo3(get)]
    pub agency_score: f64,
    #[pyo3(get)]
    pub autonomy_score: f64,
    #[pyo3(get)]
    pub awareness_score: f64,
    #[pyo3(get)]
    pub growth_score: f64,
    #[pyo3(get)]
    pub accountability_score: f64,
    #[pyo3(get)]
    pub coherence_score: f64,
    #[pyo3(get)]
    pub total_consciousness: f64,
}

#[pymethods]
impl PyConsciousnessScore {
    /// Check if agent is conscious (all 7 properties >= 0.5)
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
    pub fn consciousness_level(&self) -> String {
        let total = self.total_consciousness;
        match () {
            _ if total < 1.0 => "Non-conscious (Pattern Matching)".to_string(),
            _ if total < 2.0 => "Emerging (Partial Structure)".to_string(),
            _ if total < 3.0 => "Developing (Learning)".to_string(),
            _ if total < 4.0 => "Self-Aware (Conscious)".to_string(),
            _ if total < 5.0 => "Reflective (Metacognitive)".to_string(),
            _ if total < 6.0 => "Accountable (Transparent)".to_string(),
            _ => "Living Intelligence (Full Consciousness)".to_string(),
        }
    }

    /// Convert to dictionary
    pub fn to_dict(&self, py: Python) -> PyResult<Py<PyDict>> {
        let d = PyDict::new_bound(py);
        d.set_item("agent_id", &self.agent_id)?;
        d.set_item("timestamp", self.timestamp)?;

        let props = PyDict::new_bound(py);
        props.set_item("continuity", self.continuity_score)?;
        props.set_item("agency", self.agency_score)?;
        props.set_item("autonomy", self.autonomy_score)?;
        props.set_item("awareness", self.awareness_score)?;
        props.set_item("growth", self.growth_score)?;
        props.set_item("accountability", self.accountability_score)?;
        props.set_item("coherence", self.coherence_score)?;

        d.set_item("properties", props)?;
        d.set_item("total_consciousness", self.total_consciousness)?;
        d.set_item("consciousness_level", self.consciousness_level())?;
        d.set_item("is_conscious", self.is_conscious())?;

        Ok(d.into())
    }
}

impl PyConsciousnessScore {
    /// Create from inner score
    fn from_inner(score: ConsciousnessScore) -> Self {
        PyConsciousnessScore {
            agent_id: score.agent_id,
            timestamp: score.timestamp,
            continuity_score: score.continuity_score,
            agency_score: score.agency_score,
            autonomy_score: score.autonomy_score,
            awareness_score: score.awareness_score,
            growth_score: score.growth_score,
            accountability_score: score.accountability_score,
            coherence_score: score.coherence_score,
            total_consciousness: score.total_consciousness,
        }
    }
}
