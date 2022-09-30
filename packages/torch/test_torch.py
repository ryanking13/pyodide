from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["torch"])
def test_import():
    import torch

    print(torch.__version__)
