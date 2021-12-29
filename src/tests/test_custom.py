from pathlib import Path

import pytest

def test_custom_python(selenium, request):
    # selenium.run_js(
    #     """
    #     pyodide.runPythonInternal(`
    #         import random
    #         for i in range(1000000):
    #             a = random.randint(0, 1000)        
    #     `)
    #     """
    # )
    selenium.run_js(
        """
        for(var i = 0; i < 10000; i += 1) {
            pyodide.runPython(`1`)
        }        
        """
    )

def test_custom_js(selenium, request):
    selenium.run_js(
        """
        for(var i = 0; i < 1000000000; i += 1) {
            var a = Math.floor(Math.random() * 1000000);
        }
        """
    )