from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["test", "unicodedata"], pytest_assert_rewrites=False)
def test_unicodedata(selenium):
    # from test import libregrtest

    # name = "test_unicodedata"
    # ignore_tests = [
    #     "*test_normalization*"
    # ]

    # try:
    #     libregrtest.main([name], ignore_tests=ignore_tests, verbose=True, verbose3=True, match_tests=["*"])
    # except SystemExit as e:
    #     if e.code != 0:
    #         raise RuntimeError(f"Failed with code: {e.code}")

    # TODO: libregrtest.main(["test_unicodedata"]) doesn't collect any tests for some unknown reason.

    import test.test_unicodedata
    import unittest
    from test.support import _filter_suite

    suite = unittest.TestSuite(
        [unittest.TestLoader().loadTestsFromModule(test.test_unicodedata)]
    )

    ignore_tests = [
        "test_normalization",
    ]

    _filter_suite(
        suite,
        lambda test: all(ignore_test not in test.id() for ignore_test in ignore_tests),
    )

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    assert result.wasSuccessful()
