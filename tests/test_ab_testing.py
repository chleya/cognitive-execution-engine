"""Tests for ab_testing module."""

import pytest
import tempfile
import shutil
import time
from pathlib import Path
from src.cee_core.ab_testing import (
    ABTestingFramework,
    ABExperiment,
    ExperimentVariant,
    ExperimentResult,
    ExperimentAnalysis,
    ExperimentStatus,
)


def control_variant():
    """Control variant implementation."""
    return {"accuracy": 0.7, "latency": 100, "success": True}


def treatment_variant_a():
    """Treatment variant A implementation."""
    return {"accuracy": 0.85, "latency": 120, "success": True}


def treatment_variant_b():
    """Treatment variant B implementation."""
    return {"accuracy": 0.8, "latency": 90, "success": True}


def failing_variant():
    """Variant that sometimes fails."""
    raise ValueError("Deterministic failure for testing")


class TestExperimentStatus:
    """Tests for ExperimentStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert ExperimentStatus.PENDING.value == "pending"
        assert ExperimentStatus.RUNNING.value == "running"
        assert ExperimentStatus.COMPLETED.value == "completed"
        assert ExperimentStatus.FAILED.value == "failed"


class TestExperimentVariant:
    """Tests for ExperimentVariant dataclass."""

    def test_create_variant(self):
        """Test creating an experiment variant."""
        variant = ExperimentVariant(
            name="control",
            description="Baseline implementation",
            implementation=control_variant,
            is_control=True
        )
        
        assert variant.name == "control"
        assert variant.is_control is True
        assert callable(variant.implementation)


class TestABTestingFramework:
    """Tests for ABTestingFramework class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def framework(self, temp_dir):
        """Create a testing framework instance."""
        return ABTestingFramework(results_dir=temp_dir)

    @pytest.fixture
    def variants(self):
        """Create test variants."""
        return [
            ExperimentVariant(
                name="control",
                description="Control variant",
                implementation=control_variant,
                is_control=True
            ),
            ExperimentVariant(
                name="treatment_a",
                description="Treatment A",
                implementation=treatment_variant_a
            ),
            ExperimentVariant(
                name="treatment_b",
                description="Treatment B",
                implementation=treatment_variant_b
            )
        ]

    def test_create_framework_default_path(self, temp_dir):
        """Test creating framework with default path."""
        import os
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            framework = ABTestingFramework()
            assert framework.results_dir == Path(temp_dir) / "ab_test_results"
            assert framework.results_dir.exists()
        finally:
            os.chdir(original_cwd)

    def test_create_experiment(self, framework, variants):
        """Test creating an experiment."""
        experiment = framework.create_experiment(
            name="accuracy_test",
            description="Test accuracy improvements",
            metrics_to_track=["accuracy", "latency"],
            variants=variants,
            num_trials=10
        )
        
        assert experiment.name == "accuracy_test"
        assert experiment.status == ExperimentStatus.PENDING
        assert len(experiment.variants) == 3
        assert experiment.num_trials == 10
        assert experiment.experiment_id in framework.experiments

    def test_run_experiment(self, framework, variants):
        """Test running an experiment."""
        experiment = framework.create_experiment(
            name="quick_test",
            description="Quick test run",
            metrics_to_track=["accuracy", "latency"],
            variants=variants[:2],
            num_trials=5
        )
        
        result = framework.run_experiment(experiment)
        
        assert result.status == ExperimentStatus.COMPLETED
        assert len(result.results) == 10
        assert all(r.trial_id for r in result.results)
        assert all(r.variant_name in ["control", "treatment_a"] for r in result.results)

    def test_run_experiment_with_progress(self, framework, variants):
        """Test running experiment with progress callback."""
        experiment = framework.create_experiment(
            name="progress_test",
            description="Test progress callback",
            metrics_to_track=["accuracy"],
            variants=variants[:1],
            num_trials=3
        )
        
        progress_updates = []
        
        def progress_callback(current, total):
            progress_updates.append((current, total))
        
        framework.run_experiment(experiment, progress_callback=progress_callback)
        
        assert len(progress_updates) == 3

    def test_run_experiment_with_input_generator(self, framework):
        """Test running experiment with input generator."""
        def input_generator():
            return {"input_value": 42}
        
        def variant_with_input(input_value=0):
            return {"result": input_value * 2}
        
        variants = [
            ExperimentVariant(
                name="test",
                description="Test variant",
                implementation=variant_with_input,
                is_control=True
            )
        ]
        
        experiment = framework.create_experiment(
            name="input_test",
            description="Test input generator",
            metrics_to_track=["result"],
            variants=variants,
            num_trials=2
        )
        
        result = framework.run_experiment(experiment, trial_input_generator=input_generator)
        
        for r in result.results:
            if r.success:
                assert r.metrics["result"] == 84

    def test_analyze_experiment(self, framework, variants):
        """Test analyzing experiment results."""
        experiment = framework.create_experiment(
            name="analysis_test",
            description="Test analysis",
            metrics_to_track=["accuracy", "latency"],
            variants=variants,
            num_trials=5
        )
        
        framework.run_experiment(experiment)
        analysis = framework.analyze_experiment(experiment)
        
        assert analysis.experiment_id == experiment.experiment_id
        assert analysis.control_variant == "control"
        assert "treatment_a" in analysis.treatment_variants
        assert "treatment_b" in analysis.treatment_variants
        assert "accuracy" in analysis.metric_analyses

    def test_save_and_load_experiment(self, framework, variants):
        """Test saving and loading experiments."""
        experiment = framework.create_experiment(
            name="persistence_test",
            description="Test persistence",
            metrics_to_track=["accuracy"],
            variants=variants[:2],
            num_trials=3
        )
        
        framework.run_experiment(experiment)
        
        loaded = framework.load_experiment(experiment.experiment_id)
        
        assert loaded is not None
        assert loaded.experiment_id == experiment.experiment_id
        assert loaded.name == experiment.name
        assert len(loaded.results) == len(experiment.results)

    def test_load_nonexistent_experiment(self, framework):
        """Test loading nonexistent experiment."""
        loaded = framework.load_experiment("nonexistent_exp")
        assert loaded is None

    def test_generate_report(self, framework, variants):
        """Test generating experiment report."""
        experiment = framework.create_experiment(
            name="report_test",
            description="Test report generation",
            metrics_to_track=["accuracy", "latency"],
            variants=variants[:2],
            num_trials=5
        )
        
        framework.run_experiment(experiment)
        analysis = framework.analyze_experiment(experiment)
        report = framework.generate_report(experiment, analysis)
        
        assert "A/B EXPERIMENT REPORT" in report
        assert "report_test" in report
        assert "VARIANTS" in report
        assert "RESULTS SUMMARY" in report
        assert "OVERALL RECOMMENDATION" in report

    def test_experiment_to_dict_and_from_dict(self, variants):
        """Test experiment serialization."""
        experiment = ABExperiment(
            name="serialize_test",
            description="Test serialization",
            variants=variants[:2],
            metrics_to_track=["accuracy"],
            num_trials=5
        )
        
        exp_dict = experiment.to_dict()
        restored = ABExperiment.from_dict(exp_dict)
        
        assert restored.experiment_id == experiment.experiment_id
        assert restored.name == experiment.name
        assert restored.description == experiment.description

    def test_failing_variant(self, framework):
        """Test experiments with failing variants."""
        variants = [
            ExperimentVariant(
                name="control",
                description="Control",
                implementation=control_variant,
                is_control=True
            ),
            ExperimentVariant(
                name="failing",
                description="Sometimes fails",
                implementation=failing_variant
            )
        ]
        
        experiment = framework.create_experiment(
            name="failure_test",
            description="Test failure handling",
            metrics_to_track=["accuracy"],
            variants=variants,
            num_trials=10
        )
        
        result = framework.run_experiment(experiment)
        
        assert result.status == ExperimentStatus.COMPLETED
        assert any(not r.success for r in result.results)
