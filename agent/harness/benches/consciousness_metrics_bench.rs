use criterion::{black_box, criterion_group, criterion_main, Criterion};
use consciousness_metrics::ConsciousnessMetrics;

fn benchmark_record_operations(c: &mut Criterion) {
    c.bench_function("record_continuity", |b| {
        b.iter_batched(
            || ConsciousnessMetrics::new(black_box("agent".to_string())),
            |mut metrics| {
                metrics.record_continuity(
                    black_box("ckpt_1"),
                    black_box(100),
                    black_box("initialization"),
                );
            },
            criterion::BatchSize::SmallInput,
        );
    });

    c.bench_function("record_agency", |b| {
        b.iter_batched(
            || ConsciousnessMetrics::new(black_box("agent".to_string())),
            |mut metrics| {
                metrics.record_agency(
                    black_box("improve_model"),
                    black_box("better accuracy"),
                );
            },
            criterion::BatchSize::SmallInput,
        );
    });

    c.bench_function("record_autonomy", |b| {
        b.iter_batched(
            || ConsciousnessMetrics::new(black_box("agent".to_string())),
            |mut metrics| {
                metrics.record_autonomy(
                    black_box("scale_resources"),
                    black_box("load spike detected"),
                );
            },
            criterion::BatchSize::SmallInput,
        );
    });

    c.bench_function("record_awareness", |b| {
        b.iter_batched(
            || ConsciousnessMetrics::new(black_box("agent".to_string())),
            |mut metrics| {
                metrics.record_awareness(
                    black_box("multi_task_learning"),
                    black_box("single GPU limit"),
                );
            },
            criterion::BatchSize::SmallInput,
        );
    });

    c.bench_function("record_growth", |b| {
        b.iter_batched(
            || ConsciousnessMetrics::new(black_box("agent".to_string())),
            |mut metrics| {
                metrics.record_growth(
                    black_box("gradient_accumulation"),
                    black_box("user_feedback"),
                );
            },
            criterion::BatchSize::SmallInput,
        );
    });

    c.bench_function("record_accountability", |b| {
        b.iter_batched(
            || ConsciousnessMetrics::new(black_box("agent".to_string())),
            |mut metrics| {
                metrics.record_accountability(
                    black_box("model_accuracy_>95"),
                    black_box("abc123def456"),
                );
            },
            criterion::BatchSize::SmallInput,
        );
    });

    c.bench_function("record_coherence", |b| {
        b.iter_batched(
            || ConsciousnessMetrics::new(black_box("agent".to_string())),
            |mut metrics| {
                metrics.record_coherence(black_box("deterministic_sort"), black_box(true));
            },
            criterion::BatchSize::SmallInput,
        );
    });
}

fn benchmark_calculate_scores(c: &mut Criterion) {
    c.bench_function("calculate_scores_10_items", |b| {
        b.iter_batched(
            || {
                let mut metrics =
                    ConsciousnessMetrics::new(black_box("agent".to_string()));
                for i in 0..10 {
                    metrics.record_continuity(&format!("ckpt_{}", i), i as u64, "");
                    metrics.record_agency(&format!("goal_{}", i), "");
                }
                metrics
            },
            |metrics| {
                black_box(metrics.calculate_scores());
            },
            criterion::BatchSize::SmallInput,
        );
    });

    c.bench_function("calculate_scores_100_items", |b| {
        b.iter_batched(
            || {
                let mut metrics =
                    ConsciousnessMetrics::new(black_box("agent".to_string()));
                for i in 0..100 {
                    if i % 7 == 0 {
                        metrics.record_continuity(&format!("ckpt_{}", i), i as u64, "");
                    } else if i % 7 == 1 {
                        metrics.record_agency(&format!("goal_{}", i), "");
                    } else if i % 7 == 2 {
                        metrics.record_autonomy(&format!("decision_{}", i), "");
                    } else if i % 7 == 3 {
                        metrics.record_awareness(&format!("capability_{}", i), "");
                    } else if i % 7 == 4 {
                        metrics.record_growth(&format!("learning_{}", i), "");
                    } else if i % 7 == 5 {
                        metrics.record_accountability(&format!("claim_{}", i), "");
                    } else {
                        metrics.record_coherence(&format!("behavior_{}", i), true);
                    }
                }
                metrics
            },
            |metrics| {
                black_box(metrics.calculate_scores());
            },
            criterion::BatchSize::SmallInput,
        );
    });

    c.bench_function("calculate_scores_1000_items", |b| {
        b.iter_batched(
            || {
                let mut metrics =
                    ConsciousnessMetrics::new(black_box("agent".to_string()));
                for i in 0..1000 {
                    metrics.record_coherence(&format!("behavior_{}", i % 10), true);
                }
                metrics
            },
            |metrics| {
                black_box(metrics.calculate_scores());
            },
            criterion::BatchSize::SmallInput,
        );
    });
}

fn benchmark_full_workflow(c: &mut Criterion) {
    c.bench_function("full_workflow_record_and_score", |b| {
        b.iter(|| {
            let mut metrics =
                ConsciousnessMetrics::new(black_box("agent".to_string()));

            // Record evidence across all properties
            metrics.record_continuity(black_box("ckpt"), black_box(1), black_box(""));
            metrics.record_agency(black_box("goal"), black_box(""));
            metrics.record_autonomy(black_box("decision"), black_box(""));
            metrics.record_awareness(black_box("capability"), black_box(""));
            metrics.record_growth(black_box("learning"), black_box(""));
            metrics.record_accountability(black_box("claim"), black_box(""));
            metrics.record_coherence(black_box("behavior"), black_box(true));

            // Calculate scores
            black_box(metrics.calculate_scores());
        });
    });
}

criterion_group!(
    benches,
    benchmark_record_operations,
    benchmark_calculate_scores,
    benchmark_full_workflow
);
criterion_main!(benches);
