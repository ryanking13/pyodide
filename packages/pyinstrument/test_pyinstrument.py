import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.skip_refcount_check
@run_in_pyodide(packages=["pyinstrument"])
async def test_pyinstrument(selenium, tmp_path):
    """Check that we can run the profiler on async code

    without errors.
    """
    import asyncio
    import json
    from pathlib import Path

    from pyinstrument.profiler import Profiler, Session

    p1 = Profiler()
    with p1:
        await asyncio.sleep(0.1)

    p1.print(show_all=True, timeline=True)

    session_file = Path("foo.pysession")
    s1 = p1.last_session
    s1.save(session_file)

    s1_data = json.load(session_file.open())

    # _all_ the keys as of 4.4.0, but presumably more could be added
    expected_keys = {
        "cpu_time",
        "duration",
        "frame_records",
        "program",
        "sample_count",
        "start_call_stack",
        "start_time",
    }
    missing_keys = expected_keys - set(s1_data)

    assert not missing_keys, f"session JSON missing: {missing_keys}"

    s2 = Session.load(session_file).to_json()

    assert s1_data.keys() == s2.keys()

    for k, v in s1_data.items():
        if s2[k] != v:
            assert s2[k] == v, f"{k} mismatch: {s2[k]} != {v}"
