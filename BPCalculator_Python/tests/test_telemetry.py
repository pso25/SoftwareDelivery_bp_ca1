"""Telemetry (MIGRATION.md F11): off without a connection string, and the
CategoryCalculated event sends the category only, never the readings."""
import logging

import app as app_module


def test_telemetry_off_without_connection_string(monkeypatch):
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    calls = []
    monkeypatch.setattr(app_module, "enable_telemetry", calls.append)
    app_module.create_app("Testing")
    assert calls == []


def test_telemetry_on_with_connection_string(monkeypatch):
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=test")
    calls = []
    monkeypatch.setattr(app_module, "enable_telemetry", calls.append)
    flask_app = app_module.create_app("Testing")
    assert calls == [flask_app]


def category_events(caplog):
    return [r for r in caplog.records
            if getattr(r, "microsoft.custom_event.name", None) == "CategoryCalculated"]


def test_event_has_category_but_not_readings(client, caplog):
    caplog.set_level(logging.INFO, logger="pages")
    client.post("/", data={"BP.Systolic": "145", "BP.Diastolic": "92"})
    events = category_events(caplog)
    assert len(events) == 1
    assert events[0].category == "HIGH"
    assert "145" not in events[0].getMessage()
    assert "92" not in events[0].getMessage()


def test_no_event_on_page_open_or_invalid_reading(client, caplog):
    caplog.set_level(logging.INFO, logger="pages")
    client.get("/")
    client.post("/", data={"BP.Systolic": "80", "BP.Diastolic": "90"})
    assert category_events(caplog) == []
