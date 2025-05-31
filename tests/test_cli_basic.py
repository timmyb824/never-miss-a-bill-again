import subprocess


def test_cli_help():
    """Ensure the CLI help command works and prints usage info."""
    result = subprocess.run(
        ["python", "-m", "nmba.cli", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0
    assert "Usage" in result.stdout or "usage" in result.stdout
