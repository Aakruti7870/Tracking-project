from pathlib import Path


def test_automation_history_backfill_is_opt_in():
    config = (Path(__file__).parents[1] / "config.py").read_text()
    server = (Path(__file__).parents[1] / "server.py").read_text()

    assert 'AUTOMATION_BACKFILL_ON_STARTUP: bool = _boolean("AUTOMATION_BACKFILL_ON_STARTUP", False)' in config
    assert 'if settings.AUTOMATION_BACKFILL_ON_STARTUP:' in server
    assert 'backfilled = await backfill_order_status_events(limit=500)' in server

    guard = server.index('if settings.AUTOMATION_BACKFILL_ON_STARTUP:')
    replay = server.index('backfilled = await backfill_order_status_events(limit=500)')
    assert replay > guard
