"""Health monitor exit-code mapping (stale worker must fail loudly)."""
import automation_health as monitor
from automation_heartbeat import Health


def test_healthy_and_warning_do_not_hard_fail():
    assert monitor.monitor_exit_code(Health.HEALTHY) == 0
    assert monitor.monitor_exit_code(Health.WARNING) == 0


def test_failed_and_unknown_fail_loudly():
    assert monitor.monitor_exit_code(Health.FAILED) == 1
    assert monitor.monitor_exit_code(Health.UNKNOWN) == 1
