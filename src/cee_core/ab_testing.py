"""A/B testing framework for Plan B validation.

Provides infrastructure for running controlled experiments to compare
different implementations and validate the value of new features.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Tuple
from uuid import uuid4
from datetime import datetime, UTC
from enum import Enum
import json
from pathlib import Path


class ExperimentStatus(Enum):
    """Status of an A/B experiment."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExperimentResult:
    """Result from a single experiment trial."""

    trial_id: str
    variant_name: str
    metrics: Dict[str, Any]
    success: bool
    duration_seconds: float
    error_message: Optional[str] = None
    timestamp: float = field(default_factory=lambda: datetime.now(UTC).timestamp())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "variant_name": self.variant_name,
            "metrics": self.metrics,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
        }


@dataclass
class ExperimentVariant:
    """A variant in an A/B experiment."""

    name: str
    description: str
    implementation: Callable[..., Dict[str, Any]]
    is_control: bool = False


@dataclass
class ABExperiment:
    """A/B experiment configuration and results."""

    name: str
    description: str
    variants: List[ExperimentVariant]
    metrics_to_track: List[str]
    experiment_id: str = field(default_factory=lambda: f"exp_{uuid4().hex}")
    num_trials: int = 100
    status: ExperimentStatus = ExperimentStatus.PENDING
    results: List[ExperimentResult] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: datetime.now(UTC).timestamp())
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "description": self.description,
            "variants": [
                {
                    "name": v.name,
                    "description": v.description,
                    "is_control": v.is_control
                }
                for v in self.variants
            ],
            "metrics_to_track": self.metrics_to_track,
            "num_trials": self.num_trials,
            "status": self.status.value,
            "results": [r.to_dict() for r in self.results],
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ABExperiment":
        variants = []
        for v_data in data.get("variants", []):
            variants.append(ExperimentVariant(
                name=v_data["name"],
                description=v_data["description"],
                implementation=lambda: {},  # Will not be restored from dict
                is_control=v_data.get("is_control", False)
            ))
        
        results = []
        for r_data in data.get("results", []):
            results.append(ExperimentResult(
                trial_id=r_data["trial_id"],
                variant_name=r_data["variant_name"],
                metrics=r_data["metrics"],
                success=r_data["success"],
                duration_seconds=r_data["duration_seconds"],
                error_message=r_data.get("error_message"),
                timestamp=r_data["timestamp"]
            ))
        
        return cls(
            experiment_id=data["experiment_id"],
            name=data["name"],
            description=data["description"],
            variants=variants,
            metrics_to_track=data["metrics_to_track"],
            num_trials=data["num_trials"],
            status=ExperimentStatus(data["status"]),
            results=results,
            created_at=data["created_at"],
            completed_at=data.get("completed_at")
        )


@dataclass
class ExperimentAnalysis:
    """Statistical analysis of an A/B experiment."""

    experiment_id: str
    control_variant: str
    treatment_variants: List[str]
    metric_analyses: Dict[str, Dict[str, Any]]
    overall_recommendation: str
    confidence_level: float = 0.95


class ABTestingFramework:
    """Framework for running and analyzing A/B experiments."""

    def __init__(self, results_dir: Optional[str] = None):
        """Initialize the A/B testing framework.
        
        Args:
            results_dir: Directory to store experiment results
        """
        if results_dir is None:
            results_dir = Path.cwd() / "ab_test_results"
        
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.experiments: Dict[str, ABExperiment] = {}

    def create_experiment(
        self,
        name: str,
        description: str,
        metrics_to_track: List[str],
        variants: List[ExperimentVariant],
        num_trials: int = 100
    ) -> ABExperiment:
        """Create a new A/B experiment.
        
        Args:
            name: Experiment name
            description: Experiment description
            metrics_to_track: List of metrics to track
            variants: List of experiment variants
            num_trials: Number of trials per variant
            
        Returns:
            Created ABExperiment object
        """
        experiment = ABExperiment(
            name=name,
            description=description,
            variants=variants,
            metrics_to_track=metrics_to_track,
            num_trials=num_trials
        )
        self.experiments[experiment.experiment_id] = experiment
        return experiment

    def run_experiment(
        self,
        experiment: ABExperiment,
        trial_input_generator: Optional[Callable[[], Dict[str, Any]]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> ABExperiment:
        """Run an A/B experiment.
        
        Args:
            experiment: Experiment to run
            trial_input_generator: Optional function to generate trial inputs
            progress_callback: Optional callback for progress updates
            
        Returns:
            Updated ABExperiment with results
        """
        import time
        
        experiment.status = ExperimentStatus.RUNNING
        total_trials = experiment.num_trials * len(experiment.variants)
        trial_count = 0

        for variant in experiment.variants:
            for i in range(experiment.num_trials):
                trial_id = f"trial_{uuid4().hex}"
                trial_input = trial_input_generator() if trial_input_generator else {}
                
                start_time = time.time()
                success = True
                error_message = None
                metrics = {}
                
                try:
                    metrics = variant.implementation(**trial_input)
                except Exception as e:
                    success = False
                    error_message = str(e)
                
                duration = time.time() - start_time
                
                result = ExperimentResult(
                    trial_id=trial_id,
                    variant_name=variant.name,
                    metrics=metrics,
                    success=success,
                    duration_seconds=duration,
                    error_message=error_message
                )
                
                experiment.results.append(result)
                
                trial_count += 1
                if progress_callback:
                    progress_callback(trial_count, total_trials)

        experiment.status = ExperimentStatus.COMPLETED
        experiment.completed_at = datetime.now(UTC).timestamp()
        
        self._save_experiment(experiment)
        return experiment

    def analyze_experiment(self, experiment: ABExperiment) -> ExperimentAnalysis:
        """Analyze the results of an experiment.
        
        Args:
            experiment: Completed experiment to analyze
            
        Returns:
            ExperimentAnalysis with statistical results
        """
        import statistics
        
        control_variant = next((v for v in experiment.variants if v.is_control), None)
        if not control_variant:
            control_variant = experiment.variants[0]
        
        control_name = control_variant.name
        treatment_names = [v.name for v in experiment.variants if v.name != control_name]
        
        metric_analyses = {}
        
        for metric in experiment.metrics_to_track:
            metric_analyses[metric] = self._analyze_metric(
                experiment, metric, control_name, treatment_names
            )
        
        overall_recommendation = self._generate_overall_recommendation(
            experiment, metric_analyses, control_name
        )
        
        return ExperimentAnalysis(
            experiment_id=experiment.experiment_id,
            control_variant=control_name,
            treatment_variants=treatment_names,
            metric_analyses=metric_analyses,
            overall_recommendation=overall_recommendation
        )

    def _analyze_metric(
        self,
        experiment: ABExperiment,
        metric: str,
        control_name: str,
        treatment_names: List[str]
    ) -> Dict[str, Any]:
        """Analyze a single metric across variants."""
        import statistics
        
        results_by_variant: Dict[str, List[float]] = {}
        
        for result in experiment.results:
            if not result.success:
                continue
            
            if result.variant_name not in results_by_variant:
                results_by_variant[result.variant_name] = []
            
            value = result.metrics.get(metric)
            if isinstance(value, (int, float)):
                results_by_variant[result.variant_name].append(value)
        
        analysis = {}
        
        for variant_name in [control_name] + treatment_names:
            values = results_by_variant.get(variant_name, [])
            if values:
                analysis[variant_name] = {
                    "mean": statistics.mean(values),
                    "median": statistics.median(values),
                    "std_dev": statistics.stdev(values) if len(values) >= 2 else 0,
                    "count": len(values),
                    "min": min(values),
                    "max": max(values)
                }
            else:
                analysis[variant_name] = {
                    "mean": 0,
                    "median": 0,
                    "std_dev": 0,
                    "count": 0,
                    "min": 0,
                    "max": 0
                }
        
        # Calculate relative improvements
        control_mean = analysis.get(control_name, {}).get("mean", 0)
        if control_mean > 0:
            for variant_name in treatment_names:
                treatment_mean = analysis.get(variant_name, {}).get("mean", 0)
                relative_improvement = ((treatment_mean - control_mean) / control_mean) * 100
                analysis[variant_name]["relative_improvement_percent"] = relative_improvement
        
        return analysis

    def _generate_overall_recommendation(
        self,
        experiment: ABExperiment,
        metric_analyses: Dict[str, Dict[str, Any]],
        control_name: str
    ) -> str:
        """Generate an overall recommendation based on experiment results."""
        treatment_names = [v.name for v in experiment.variants if v.name != control_name]
        
        if not treatment_names:
            return "No treatment variants to compare."
        
        # Simple heuristic: check if any treatment is better on majority of metrics
        winning_variants = {}
        
        for metric in experiment.metrics_to_track:
            metric_analysis = metric_analyses.get(metric, {})
            control_mean = metric_analysis.get(control_name, {}).get("mean", 0)
            
            for variant in treatment_names:
                treatment_mean = metric_analysis.get(variant, {}).get("mean", 0)
                if treatment_mean > control_mean:
                    if variant not in winning_variants:
                        winning_variants[variant] = 0
                    winning_variants[variant] += 1
        
        if winning_variants:
            best_variant = max(winning_variants.items(), key=lambda x: x[1])
            return f"Variant '{best_variant[0]}' shows improvement on {best_variant[1]}/{len(experiment.metrics_to_track)} metrics."
        
        return "No treatment variant shows clear improvement over control."

    def _save_experiment(self, experiment: ABExperiment) -> None:
        """Save experiment results to disk."""
        exp_file = self.results_dir / f"{experiment.experiment_id}.json"
        with open(exp_file, "w", encoding="utf-8") as f:
            json.dump(experiment.to_dict(), f, indent=2, ensure_ascii=False)

    def load_experiment(self, experiment_id: str) -> Optional[ABExperiment]:
        """Load an experiment from disk.
        
        Args:
            experiment_id: ID of the experiment to load
            
        Returns:
            Loaded ABExperiment or None if not found
        """
        exp_file = self.results_dir / f"{experiment_id}.json"
        if not exp_file.exists():
            return None
        
        with open(exp_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        experiment = ABExperiment.from_dict(data)
        self.experiments[experiment.experiment_id] = experiment
        return experiment

    def generate_report(self, experiment: ABExperiment, analysis: ExperimentAnalysis) -> str:
        """Generate a human-readable experiment report.
        
        Args:
            experiment: Completed experiment
            analysis: Experiment analysis
            
        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"A/B EXPERIMENT REPORT: {experiment.name}")
        lines.append("=" * 80)
        lines.append(f"Experiment ID: {experiment.experiment_id}")
        lines.append(f"Created: {datetime.fromtimestamp(experiment.created_at).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"Completed: {datetime.fromtimestamp(experiment.completed_at).strftime('%Y-%m-%d %H:%M:%S UTC') if experiment.completed_at else 'N/A'}")
        lines.append(f"Status: {experiment.status.value}")
        lines.append("")
        
        lines.append("-" * 80)
        lines.append("VARIANTS")
        lines.append("-" * 80)
        for variant in experiment.variants:
            control_mark = " [CONTROL]" if variant.is_control else ""
            lines.append(f"{variant.name}{control_mark}: {variant.description}")
        lines.append("")
        
        lines.append("-" * 80)
        lines.append("RESULTS SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total trials: {len(experiment.results)}")
        
        success_count = sum(1 for r in experiment.results if r.success)
        lines.append(f"Success rate: {success_count}/{len(experiment.results)} ({success_count/len(experiment.results)*100:.1f}%)")
        lines.append("")
        
        for metric in experiment.metrics_to_track:
            lines.append(f"--- {metric} ---")
            metric_analysis = analysis.metric_analyses.get(metric, {})
            for variant_name, variant_analysis in metric_analysis.items():
                rel_imp = variant_analysis.get("relative_improvement_percent", 0)
                imp_str = f" (+{rel_imp:.1f}%)" if rel_imp > 0 else ""
                lines.append(f"  {variant_name}: mean={variant_analysis['mean']:.4f}, median={variant_analysis['median']:.4f}, n={variant_analysis['count']}{imp_str}")
            lines.append("")
        
        lines.append("-" * 80)
        lines.append("OVERALL RECOMMENDATION")
        lines.append("-" * 80)
        lines.append(analysis.overall_recommendation)
        
        return "\n".join(lines)
