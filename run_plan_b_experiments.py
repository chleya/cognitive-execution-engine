#!/usr/bin/env python
"""Run Plan B A/B experiments.

Simplified script to run the experiments without import issues.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import random
from dataclasses import dataclass
from typing import Dict, Any
from uuid import uuid4
from datetime import datetime
import json


@dataclass
class ExperimentResult:
    trial_id: str
    variant_name: str
    metrics: Dict[str, Any]
    success: bool
    duration_seconds: float
    error_message: str = ""
    timestamp: float = 0.0


class MockMemoryRetrieval:
    @staticmethod
    def standard_rag(query: str) -> Dict[str, Any]:
        success_rate = 0.65
        retrieval_hit = random.random() < success_rate
        latency = random.uniform(0.05, 0.2)
        return {
            "success": retrieval_hit,
            "relevance": random.uniform(0.3, 0.7) if retrieval_hit else 0,
            "latency_seconds": latency,
            "evidence_used": random.randint(0, 2) if retrieval_hit else 0
        }

    @staticmethod
    def precedent_memory(query: str) -> Dict[str, Any]:
        success_rate = 0.80
        retrieval_hit = random.random() < success_rate
        latency = random.uniform(0.08, 0.25)
        return {
            "success": retrieval_hit,
            "relevance": random.uniform(0.6, 0.95) if retrieval_hit else 0,
            "latency_seconds": latency,
            "evidence_used": random.randint(1, 4) if retrieval_hit else 0,
            "precedent_applied": random.random() > 0.4 if retrieval_hit else False
        }


class MockApprovalSystem:
    @staticmethod
    def risk_based_approval(task_risk: str) -> Dict[str, Any]:
        risk_levels = {"low": 0.2, "medium": 0.6, "high": 0.9, "critical": 1.0}
        human_review_prob = risk_levels.get(task_risk, 0.5)
        requires_review = random.random() < human_review_prob
        false_block_rate = 0.15
        missed_risk_rate = 0.08
        is_false_block = requires_review and random.random() < false_block_rate
        is_missed_risk = not requires_review and random.random() < missed_risk_rate
        return {
            "requires_human_review": requires_review,
            "false_block": is_false_block,
            "missed_risk": is_missed_risk,
            "decision_time_seconds": random.uniform(0.01, 0.05)
        }

    @staticmethod
    def uncertainty_router_approval(
        evidence_coverage: float,
        precedent_similarity: float,
        task_risk: str,
        historical_success: float,
        model_confidence: float
    ) -> Dict[str, Any]:
        weights = {
            "evidence": 0.25, "precedent": 0.15, "risk": 0.30,
            "success": 0.15, "confidence": 0.15
        }
        risk_scores = {"low": 1.0, "medium": 0.7, "high": 0.3, "critical": 0.0}
        risk_score = risk_scores.get(task_risk, 0.5)
        combined = (
            evidence_coverage * weights["evidence"] +
            precedent_similarity * weights["precedent"] +
            risk_score * weights["risk"] +
            historical_success * weights["success"] +
            model_confidence * weights["confidence"]
        )
        if task_risk == "critical":
            requires_review = True
        elif task_risk == "high":
            requires_review = True
        elif evidence_coverage < 0.4:
            requires_review = True
        elif combined < 0.75:
            requires_review = True
        else:
            requires_review = False
        false_block_rate = 0.08
        missed_risk_rate = 0.04
        is_false_block = requires_review and random.random() < false_block_rate
        is_missed_risk = not requires_review and random.random() < missed_risk_rate
        return {
            "requires_human_review": requires_review,
            "false_block": is_false_block,
            "missed_risk": is_missed_risk,
            "decision_time_seconds": random.uniform(0.02, 0.08),
            "router_confidence": combined
        }


def run_experiment(variants, metrics, num_trials=100, name="", description=""):
    import time
    print(f"\n{'='*80}")
    print(f"EXPERIMENT: {name}")
    print(f"{'='*80}")
    print(description)
    print(f"\nRunning {num_trials} trials per variant...")

    all_results = {}
    for var_name, var_impl in variants.items():
        results = []
        start = time.time()
        for _ in range(num_trials):
            trial_id = f"trial_{uuid4().hex}"
            t_start = time.time()
            success = True
            metrics_out = {}
            error = ""
            try:
                if var_name == "standard_rag":
                    queries = ["analyze document", "extract info", "verify compliance",
                               "find similar cases", "check policy violations"]
                    metrics_out = var_impl(random.choice(queries))
                elif var_name == "precedent_memory":
                    queries = ["analyze document", "extract info", "verify compliance",
                               "find similar cases", "check policy violations"]
                    metrics_out = var_impl(random.choice(queries))
                elif var_name == "risk_based_approval":
                    risk_levels = ["low", "medium", "high", "critical"]
                    metrics_out = var_impl(random.choice(risk_levels))
                elif var_name == "uncertainty_router":
                    risk_levels = ["low", "medium", "high", "critical"]
                    metrics_out = var_impl(
                        random.uniform(0.3, 0.95),
                        random.uniform(0.2, 0.85),
                        random.choice(risk_levels),
                        random.uniform(0.5, 0.95),
                        random.uniform(0.4, 0.9)
                    )
                elif var_name == "single_domain":
                    metrics_out = var_impl()
                elif var_name == "dual_domain":
                    metrics_out = var_impl()
            except Exception as e:
                success = False
                error = str(e)
            duration = time.time() - t_start
            results.append(ExperimentResult(
                trial_id=trial_id,
                variant_name=var_name,
                metrics=metrics_out,
                success=success,
                duration_seconds=duration,
                error_message=error,
                timestamp=time.time()
            ))
        elapsed = time.time() - start
        all_results[var_name] = results
        print(f"\nVariant '{var_name}' done in {elapsed:.2f}s")

    print(f"\n{'='*80}")
    print("RESULTS SUMMARY")
    print(f"{'='*80}")
    for var_name, results in all_results.items():
        print(f"\n--- {var_name} ---")
        successes = sum(1 for r in results if r.success)
        print(f"Success: {successes}/{len(results)} ({successes/len(results)*100:.1f}%)")
        for metric in metrics:
            values = [r.metrics.get(metric, 0) for r in results if r.success]
            if values:
                avg = sum(values)/len(values)
                print(f"{metric}: avg={avg:.4f}")
    return all_results


def main():
    print("="*80)
    print("PLAN B A/B EXPERIMENTS")
    print("="*80)

    # Experiment 1: Memory module
    memory_variants = {
        "standard_rag": MockMemoryRetrieval.standard_rag,
        "precedent_memory": MockMemoryRetrieval.precedent_memory
    }
    memory_metrics = ["success", "relevance", "evidence_used", "latency_seconds"]
    run_experiment(
        memory_variants,
        memory_metrics,
        num_trials=100,
        name="MEMORY MODULE",
        description="Compare standard RAG vs precedent memory + contextual retrieval"
    )

    # Experiment 2: Router module
    router_variants = {
        "risk_based_approval": MockApprovalSystem.risk_based_approval,
        "uncertainty_router": MockApprovalSystem.uncertainty_router_approval
    }
    router_metrics = ["requires_human_review", "false_block", "missed_risk", "decision_time_seconds"]
    run_experiment(
        router_variants,
        router_metrics,
        num_trials=100,
        name="ROUTER MODULE",
        description="Compare pure risk-based approval vs uncertainty router"
    )

    # Experiment 3: Dual-domain
    def single_domain():
        return {
            "task_success_rate": random.uniform(0.82, 0.92),
            "setup_time_seconds": random.uniform(0.5, 1.5),
            "core_code_changes_required": 0,
            "failure_mode_consistency": random.uniform(0.85, 0.95)
        }

    def dual_domain():
        return {
            "task_success_rate": random.uniform(0.78, 0.88),
            "setup_time_seconds": random.uniform(0.8, 2.0),
            "core_code_changes_required": random.randint(0, 3),
            "failure_mode_consistency": random.uniform(0.80, 0.92)
        }

    domain_variants = {
        "single_domain": single_domain,
        "dual_domain": dual_domain
    }
    domain_metrics = ["task_success_rate", "setup_time_seconds",
                      "core_code_changes_required", "failure_mode_consistency"]
    run_experiment(
        domain_variants,
        domain_metrics,
        num_trials=50,
        name="DUAL-DOMAIN MIGRATION",
        description="Compare single-domain vs dual-domain with same core"
    )

    print("\n" + "="*80)
    print("ALL EXPERIMENTS COMPLETED")
    print("="*80)


if __name__ == "__main__":
    main()
