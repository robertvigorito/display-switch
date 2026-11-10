"""Rez package definition for display-switch."""

import subprocess

name = "display_switch"
version = subprocess.check_output(["rezops-get-version"]).decode().strip()
description = "Enable or disable Windows monitors individually or in named groups"
requires = []
private_build_requires = []
build_command = f"rezops-build {name}"


def commands():
    """Expose the generated package and optional Nuke tools in Rez.

    """
    env.PYTHONPATH.append("{root}/python")  # noqa: F821 -- Rez injects ``env`` at runtime.
    env.NUKE_PATH.append("{root}/nuke")  # noqa: F821 -- Rez injects ``env`` at runtime.

