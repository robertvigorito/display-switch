import pytest

from display_switch import monitor_backend as mb


def test_parse_empty_payload():
    assert mb.parse_monitors("") == []


def test_parse_lines_and_enabled_state():
    payload = "DISPLAY\\A\\1\tDell\t0\r\nDISPLAY\\B\\2\tLG\t1\r\n"
    monitors = mb.parse_monitors(payload)
    assert monitors == [
        mb.Monitor("DISPLAY\\A\\1", "Dell", False),
        mb.Monitor("DISPLAY\\B\\2", "LG", True),
    ]


def test_parse_ignores_malformed_lines():
    assert mb.parse_monitors("garbage\n\t\t\n") == []


def test_ps_quote_escapes_single_quotes():
    assert mb._ps_quote("a'b") == "'a''b'"


def test_guard_blocks_disabling_last_active_monitor():
    monitors = [mb.Monitor("A", "a", True), mb.Monitor("B", "b", False)]
    with pytest.raises(mb.GuardError):
        mb.check_disable_allowed(monitors, ["A"])


def test_guard_allows_disabling_when_another_remains():
    monitors = [mb.Monitor("A", "a", True), mb.Monitor("B", "b", True)]
    mb.check_disable_allowed(monitors, ["A"])


def test_apply_change_records_failures(monkeypatch):
    calls = []

    def fake_run(script):
        calls.append(script)
        if "[DisplayTopology]::List()" in script:
            return "A\ta\t1\nB\tb\t1\n"
        if "'B'" in script:
            raise mb.PowerShellError("Monitor not found in the display topology")
        return ""

    monkeypatch.setattr(mb, "run_powershell", fake_run)
    result = mb.apply_change(["A", "B", "Z"], enabled=True)
    assert result.succeeded == ["A"]
    assert result.failed == {
        "B": "Monitor not found in the display topology",
        "Z": "Monitor not found",
    }
    assert any("[DisplayTopology]::Set('A', $true, " in c for c in calls)


def test_apply_change_disable_is_guarded(monkeypatch):
    def fake_run(script):
        return "A\ta\t1\n"

    monkeypatch.setattr(mb, "run_powershell", fake_run)
    with pytest.raises(mb.GuardError):
        mb.apply_change(["A"], enabled=False)
