from routers.kyc_recovery import can_reset_status


def test_only_in_progress_kyc_can_be_reset():
    assert can_reset_status("IN_PROGRESS") is True

    for status in (
        None,
        "NOT_STARTED",
        "PENDING",
        "VERIFIED",
        "REJECTED",
        "REQUIRES_REVERIFICATION",
    ):
        assert can_reset_status(status) is False
