class KnownBaselineDefect(Exception):
    """Only an exact, observed baseline defect qualifies as an expected failure."""


def expected_status(response, *, current, desired):
    actual = response.status_code
    if actual == current:
        raise KnownBaselineDefect(f"Observed HTTP {actual}; desired HTTP {desired}")
    # Any other bad outcome is an ordinary failure, not an allowed xfail.
    assert actual == desired, f"Unexpected HTTP {actual}; expected {desired}"
