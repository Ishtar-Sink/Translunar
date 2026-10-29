from translunar import __version__
from translunar.cli import main
from translunar.core.errors import ClipLockedError, DependencyMissingError, UsageError
from translunar.core.models import StepState, SubtitleLimits


def test_cli_without_command_returns_usage_code() -> None:
    assert main([]) == 2


def test_version_is_defined() -> None:
    assert __version__ == "0.1.0"


def test_exit_codes_follow_contract() -> None:
    assert UsageError.exit_code == 2
    assert ClipLockedError.exit_code == 4
    assert DependencyMissingError.exit_code == 5


def test_defaults_follow_business_rules() -> None:
    limits = SubtitleLimits()
    assert (limits.max_lines, limits.max_chars_per_line, limits.max_cps) == (2, 32, 17.0)
    assert StepState.DESATUALIZADO.value == "desatualizado"


def test_synthetic_video_fixture(make_video) -> None:  # type: ignore[no-untyped-def]
    assert make_video().stat().st_size > 0
