from pyodide_test_runner import run_in_pyodide


# TODO: don't use numpy in this test as it's not necessairly installed.
@run_in_pyodide(packages=["pytest", "numpy"])
def test_pytest(selenium):
    import io
    from contextlib import redirect_stderr
    from pathlib import Path

    import numpy
    import pytest

    base_dir = Path(numpy.__file__).parent / "core" / "tests"

    with redirect_stderr(io.StringIO()) as f:
        pytest.main([str(base_dir / "test_api.py")])
        log = f.getvalue()

    assert "ERROR" not in log
