"""Unit coverage for operator Cloud Scheduler describe validation (no cloud)."""
import automation_scheduler_check as chk

PROJECT = "tracking-project-preview"
REGION = "asia-south1"
WORKER = "tracking-automation-worker"
RUNTIME_SA = "224495133432-compute@developer.gserviceaccount.com"


def _good_describe():
    return {
        "state": "ENABLED",
        "schedule": "* * * * *",
        "timeZone": "UTC",
        "httpTarget": {
            "uri": chk.expected_worker_uri(PROJECT, REGION, WORKER),
            "httpMethod": "POST",
            "oauthToken": {"serviceAccountEmail": RUNTIME_SA},
        },
    }


def _check(describe):
    return chk.evaluate_scheduler(
        describe, project_id=PROJECT, region=REGION, worker_job=WORKER, runtime_sa=RUNTIME_SA
    )


def test_valid_scheduler_passes():
    result = _check(_good_describe())
    assert result.ok, result.problems
    assert result.parsed["schedule"] == "* * * * *"


def test_disabled_state_flagged():
    describe = _good_describe()
    describe["state"] = "PAUSED"
    result = _check(describe)
    assert not result.ok
    assert any("state must be ENABLED" in p for p in result.problems)


def test_wrong_schedule_flagged():
    describe = _good_describe()
    describe["schedule"] = "*/5 * * * *"
    result = _check(describe)
    assert not result.ok
    assert any("schedule must be" in p for p in result.problems)


def test_wrong_timezone_flagged():
    describe = _good_describe()
    describe["timeZone"] = "Asia/Kolkata"
    result = _check(describe)
    assert not result.ok
    assert any("timeZone" in p for p in result.problems)


def test_wrong_target_job_flagged():
    describe = _good_describe()
    describe["httpTarget"]["uri"] = chk.expected_worker_uri(PROJECT, REGION, "some-other-job")
    result = _check(describe)
    assert not result.ok
    assert any("httpTarget.uri" in p for p in result.problems)


def test_wrong_oauth_sa_flagged():
    describe = _good_describe()
    describe["httpTarget"]["oauthToken"]["serviceAccountEmail"] = "attacker@example.com"
    result = _check(describe)
    assert not result.ok
    assert any("OAuth service account" in p for p in result.problems)


def test_missing_oauth_flagged():
    describe = _good_describe()
    describe["httpTarget"]["oauthToken"] = {}
    result = _check(describe)
    assert not result.ok
    assert any("serviceAccountEmail" in p for p in result.problems)


def test_empty_describe_flags_everything():
    result = _check({})
    assert not result.ok
    assert len(result.problems) >= 4
