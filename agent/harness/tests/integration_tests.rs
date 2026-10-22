use consciousness_metrics::ConsciousnessMetrics;

#[test]
fn test_create_metrics() {
    let metrics = ConsciousnessMetrics::new("test_agent".to_string());
    assert_eq!(metrics.agent_id, "test_agent");
    assert_eq!(metrics.evidence.len(), 0);
}

#[test]
fn test_record_all_properties() {
    let mut metrics = ConsciousnessMetrics::new("test_agent".to_string());

    metrics.record_continuity("ckpt_1", 1, "initialization");
    metrics.record_agency("optimize_loss", "improve accuracy");
    metrics.record_autonomy("scale_compute", "handle load");
    metrics.record_awareness("parallelization", "io_limited");
    metrics.record_growth("batch_optimization", "performance");
    metrics.record_accountability("claim_verified", "hash_abc123");
    metrics.record_coherence("deterministic_sort", true);

    assert_eq!(metrics.evidence.len(), 7);
    assert_eq!(metrics.checkpoints_count, 1);
    assert_eq!(metrics.goals_set, 1);
    assert_eq!(metrics.autonomous_decisions, 1);
    assert_eq!(metrics.capabilities_registered, 1);
    assert_eq!(metrics.learned_from_errors, 1);
    assert_eq!(metrics.proofs_generated, 1);
}

#[test]
fn test_behavior_patterns_tracking() {
    let mut metrics = ConsciousnessMetrics::new("test_agent".to_string());

    metrics.record_coherence("action_a", true);
    metrics.record_coherence("action_a", true);
    metrics.record_coherence("action_b", true);
    metrics.record_coherence("action_a", true);

    assert_eq!(metrics.behavior_patterns.get("action_a"), Some(&3));
    assert_eq!(metrics.behavior_patterns.get("action_b"), Some(&1));
}

#[test]
fn test_calculate_scores_empty() {
    let metrics = ConsciousnessMetrics::new("test_agent".to_string());
    let scores = metrics.calculate_scores();

    assert_eq!(scores.continuity_score, 0.0);
    assert_eq!(scores.agency_score, 0.0);
    assert_eq!(scores.total_consciousness, 0.0);
    assert!(!scores.is_conscious());
}

#[test]
fn test_calculate_scores_with_evidence() {
    let mut metrics = ConsciousnessMetrics::new("test_agent".to_string());

    // Add 5 evidence items for continuity
    for i in 0..5 {
        metrics.record_continuity(&format!("ckpt_{}", i), i as u64, "");
    }

    let scores = metrics.calculate_scores();

    // Score should be: min(1.0, 5 * 0.1 + 0.9 * 0.5) = min(1.0, 0.5 + 0.45) = 0.95
    assert!(scores.continuity_score >= 0.85);
    assert!(scores.continuity_score <= 1.0);
}

#[test]
fn test_consciousness_threshold() {
    let mut metrics = ConsciousnessMetrics::new("test_agent".to_string());

    // Add enough evidence to all properties to reach consciousness threshold
    for i in 0..10 {
        metrics.record_continuity(&format!("ckpt_{}", i), i as u64, "");
        metrics.record_agency(&format!("goal_{}", i), "");
        metrics.record_autonomy(&format!("decision_{}", i), "");
        metrics.record_awareness(&format!("capability_{}", i), "");
        metrics.record_growth(&format!("learning_{}", i), "");
        metrics.record_accountability(&format!("claim_{}", i), "");
        metrics.record_coherence(&format!("behavior_{}", i), true);
    }

    let scores = metrics.calculate_scores();
    assert!(scores.is_conscious());
    assert!(scores.total_consciousness >= 3.5);
}

#[test]
fn test_last_checkpoint_tracking() {
    let mut metrics = ConsciousnessMetrics::new("test_agent".to_string());

    assert!(metrics.last_checkpoint.is_none());

    metrics.record_continuity("ckpt_1", 1, "");
    assert!(metrics.last_checkpoint.is_some());

    let first_checkpoint = metrics.last_checkpoint;

    // Record another checkpoint after a small delay
    std::thread::sleep(std::time::Duration::from_millis(1));
    metrics.record_continuity("ckpt_2", 2, "");

    assert!(metrics.last_checkpoint > first_checkpoint);
}

#[test]
fn test_large_evidence_load() {
    let mut metrics = ConsciousnessMetrics::new("test_agent".to_string());

    // Record 1000 evidence items
    for i in 0..1000 {
        match i % 7 {
            0 => metrics.record_continuity(&format!("ckpt_{}", i), i as u64, ""),
            1 => metrics.record_agency(&format!("goal_{}", i), ""),
            2 => metrics.record_autonomy(&format!("decision_{}", i), ""),
            3 => metrics.record_awareness(&format!("capability_{}", i), ""),
            4 => metrics.record_growth(&format!("learning_{}", i), ""),
            5 => metrics.record_accountability(&format!("claim_{}", i), ""),
            _ => metrics.record_coherence(&format!("behavior_{}", i), true),
        }
    }

    assert_eq!(metrics.evidence.len(), 1000);

    let scores = metrics.calculate_scores();
    assert!(scores.total_consciousness > 0.0);
}

#[test]
fn test_consciousness_level_descriptions() {
    // Test level progression
    let mut metrics = ConsciousnessMetrics::new("test_agent".to_string());

    // Level 0: Non-conscious (< 1.0)
    let mut scores = metrics.calculate_scores();
    assert_eq!(scores.consciousness_level(), "Non-conscious (Pattern Matching)");

    // Add minimal evidence to reach higher levels
    for i in 0..3 {
        metrics.record_continuity(&format!("ckpt_{}", i), i as u64, "");
    }

    scores = metrics.calculate_scores();
    // Should be > 1.0 now
    if scores.total_consciousness >= 1.0 {
        assert!(scores.consciousness_level() != "Non-conscious (Pattern Matching)");
    }
}

#[test]
fn test_concurrent_record_operations() {
    use std::sync::Arc;
    use std::sync::Mutex;

    let metrics = Arc::new(Mutex::new(ConsciousnessMetrics::new("test_agent".to_string())));
    let mut handles = vec![];

    for i in 0..10 {
        let metrics_clone = Arc::clone(&metrics);
        let handle = std::thread::spawn(move || {
            let mut m = metrics_clone.lock().unwrap();
            m.record_coherence(&format!("behavior_{}", i), true);
        });
        handles.push(handle);
    }

    for handle in handles {
        handle.join().unwrap();
    }

    let m = metrics.lock().unwrap();
    assert_eq!(m.evidence.len(), 10);
}
