from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(packages=["numpy", "joblib"])
def test_joblib_numpy_pickle(selenium):
    import joblib
    import numpy as np
    from numpy.testing import assert_array_equal

    X = np.ones(10)

    file_path = "./X.pkl"

    joblib.dump(X, file_path)

    X2 = joblib.load(file_path)

    assert_array_equal(X, X2)


@run_in_pyodide(packages=["numpy", "joblib"])
def test_joblib_parallel(selenium):
    from math import sqrt

    from joblib import Parallel, delayed

    # check that the default multiprocessing backend
    # gracefully reduces to n_jobs=1
    res = Parallel(n_jobs=2)(delayed(sqrt)(i**2) for i in range(10))
    assert res == [sqrt(i**2) for i in range(10)]

    # check threading backend
    Parallel(n_jobs=2, backend="threading")(delayed(sqrt)(i**2) for i in range(10))
