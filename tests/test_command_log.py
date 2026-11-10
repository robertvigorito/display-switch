"""Tests for the PowerShell command log used by the Copy PS button."""

from display_switch import monitor_backend as mb


def test_format_command_log_puts_result_comment_above_script() -> None:
    """Each logged command is shown as a result comment followed by its script.

    Returns:
        None
    """
    records = [
        mb.CommandRecord(script="Disable-PnpDevice -InstanceId 'X' -Confirm:$false", ok=False, output="Generic failure\nmore"),
        mb.CommandRecord(script="Get-PnpDevice -Class Monitor", ok=True, output="[]"),
    ]

    text = mb.format_command_log(records)

    assert text == (
        "# FAILED: Generic failure\n"
        "Disable-PnpDevice -InstanceId 'X' -Confirm:$false\n\n"
        "# OK: []\n"
        "Get-PnpDevice -Class Monitor"
    )


def test_command_log_is_bounded() -> None:
    """The log keeps only the most recent entries.

    Returns:
        None
    """
    for index in range(mb.MAX_LOG_ENTRIES + 5):
        mb._record(f"script {index}", ok=True, output="")

    records = mb.command_log()

    assert len(records) == mb.MAX_LOG_ENTRIES
    assert records[-1].script == f"script {mb.MAX_LOG_ENTRIES + 4}"
