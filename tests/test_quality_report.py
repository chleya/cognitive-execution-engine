from cee_core import build_quality_report, compute_quality_metrics, execute_task, render_quality_report


def test_render_quality_report_includes_core_metrics_and_counts():
    metrics = compute_quality_metrics(execute_task("analyze project risk"))

    report = render_quality_report(metrics)

    assert "Quality Report" in report
    assert "Replay success rate            : 100%" in report
    assert "Policy bypass rate             : 0%" in report
    assert "Allowed transitions            : 4" in report
    assert "Blocked transitions            : 0" in report


def test_build_quality_report_computes_and_renders_in_one_step():
    report = build_quality_report(execute_task("update the project belief summary"))

    assert "Quality Report" in report
    assert "Approval-required transitions  : 1" in report
    assert "Blocked transitions            : 1" in report
