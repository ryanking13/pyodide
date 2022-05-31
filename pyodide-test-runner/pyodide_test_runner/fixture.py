import _thread
import contextlib
import threading

import pytest

from .browser import (
    BrowserWrapper,
    NodeWrapper,
    PlaywrightChromeWrapper,
    PlaywrightFirefoxWrapper,
    PlaywrightSafariWrapper,
    SeleniumChromeWrapper,
    SeleniumFirefoxWrapper,
)
from .server import spawn_web_server
from .utils import parse_driver_timeout, set_webdriver_script_timeout


@pytest.fixture(scope="session")
def playwright_session(request):
    if request.config.option.runner.lower() != "playwright":
        yield None

    # import playwright here to allow running tests without playwright installation
    else:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            pytest.exit(
                "playwright not installed. try `pip install playwright && python -m playwright install`",
                returncode=1,
            )

        p = sync_playwright().start()
        yield p

        # Stopping a playwright context manager hangs sometimes
        # so we add a timeout to silently exit if it takes too long
        timer = threading.Timer(10, lambda: _thread.interrupt_main())
        timer.start()
        try:
            p.stop()
        except KeyboardInterrupt:
            pass
        finally:
            timer.cancel()


@pytest.fixture(scope="module")
def playwright_browser(request, playwright_session, browser_type):
    if request.config.option.runner.lower() != "playwright":
        yield None
    else:
        try:
            match browser_type:
                case "chrome":
                    browser = playwright_session.chromium.launch(
                        args=[
                            "--js-flags=--expose-gc",
                        ],
                    )
                case "firefox":
                    browser = playwright_session.firefox.launch()
                case "safari":
                    browser = playwright_session.webkit.launch()
                case "node":
                    browser = None
        except Exception as e:
            pytest.exit(f"playwright failed to launch\n{e}", returncode=1)
        try:
            yield browser
        finally:
            if browser is not None:
                browser.close()


@contextlib.contextmanager
def selenium_common(
    request,
    browser_type,
    web_server_main,
    load_pyodide=True,
    script_type="classic",
    playwright_browser=None,
):
    """Returns an initialized selenium object.

    If `_should_skip_test` indicate that the test will be skipped,
    return None, as initializing Pyodide for selenium is expensive
    """

    server_hostname, server_port, server_log = web_server_main
    runner_type = request.config.option.runner.lower()
    cls: type[BrowserWrapper]

    browser_set = {
        ("selenium", "firefox"): SeleniumFirefoxWrapper,
        ("selenium", "chrome"): SeleniumChromeWrapper,
        ("selenium", "node"): NodeWrapper,
        ("playwright", "firefox"): PlaywrightFirefoxWrapper,
        ("playwright", "chrome"): PlaywrightChromeWrapper,
        ("playwright", "safari"): PlaywrightSafariWrapper,
        ("playwright", "node"): NodeWrapper,
    }

    cls = browser_set.get((runner_type, browser_type))
    if cls is None:
        raise AssertionError(
            f"Unknown runner or browser: {runner_type} / {browser_type}"
        )

    dist_dir = request.config.getoption("--dist-dir")
    runner = cls(
        server_port=server_port,
        server_hostname=server_hostname,
        server_log=server_log,
        load_pyodide=load_pyodide,
        playwright_browser=playwright_browser,
        script_type=script_type,
        dist_dir=dist_dir,
    )
    try:
        yield runner
    finally:
        runner.quit()


@pytest.fixture(scope="function")
def selenium_standalone(request, browser_type, web_server_main, playwright_browser):
    with selenium_common(
        request, browser_type, web_server_main, playwright_browser=playwright_browser
    ) as selenium:
        with set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request.node)
        ):
            try:
                yield selenium
            finally:
                print(selenium.logs)


@pytest.fixture(scope="module")
def selenium_esm(request, browser_type, web_server_main, playwright_browser):
    with selenium_common(
        request,
        browser_type,
        web_server_main,
        load_pyodide=True,
        playwright_browser=playwright_browser,
        script_type="module",
    ) as selenium:
        with set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request.node)
        ):
            try:
                yield selenium
            finally:
                print(selenium.logs)


@contextlib.contextmanager
def selenium_standalone_noload_common(
    request, browser_type, web_server_main, playwright_browser, script_type="classic"
):
    with selenium_common(
        request,
        browser_type,
        web_server_main,
        load_pyodide=False,
        playwright_browser=playwright_browser,
        script_type=script_type,
    ) as selenium:
        with set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request.node)
        ):
            try:
                yield selenium
            finally:
                print(selenium.logs)


@pytest.fixture(scope="function")
def selenium_webworker_standalone(
    request, browser_type, web_server_main, playwright_browser, script_type
):
    # Avoid loading the fixture if the test is going to be skipped
    if browser_type == "firefox" and script_type == "module":
        pytest.skip("firefox does not support module type web worker")

    if browser_type == "node":
        pytest.skip("node does not support webworker")

    with selenium_standalone_noload_common(
        request,
        browser_type,
        web_server_main,
        playwright_browser,
        script_type=script_type,
    ) as selenium:
        yield selenium


@pytest.fixture(scope="function")
def selenium_standalone_noload(
    request, browser_type, web_server_main, playwright_browser
):
    """Only difference between this and selenium_webworker_standalone is that
    this also tests on node."""

    with selenium_standalone_noload_common(
        request, browser_type, web_server_main, playwright_browser
    ) as selenium:
        yield selenium


# selenium instance cached at the module level
@pytest.fixture(scope="module")
def selenium_module_scope(request, browser_type, web_server_main, playwright_browser):
    with selenium_common(
        request, browser_type, web_server_main, playwright_browser=playwright_browser
    ) as selenium:
        yield selenium


# Hypothesis is unhappy with function scope fixtures. Instead, use the
# module scope fixture `selenium_module_scope` and use:
# `with selenium_context_manager(selenium_module_scope) as selenium`
@contextlib.contextmanager
def selenium_context_manager(selenium_module_scope):
    try:
        selenium_module_scope.clean_logs()
        yield selenium_module_scope
    finally:
        print(selenium_module_scope.logs)


@pytest.fixture
def selenium(request, selenium_module_scope):
    with selenium_context_manager(selenium_module_scope) as selenium:
        with set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request.node)
        ):
            yield selenium


@pytest.fixture(scope="function")
def console_html_fixture(request, browser_type, web_server_main, playwright_browser):

    if browser_type == "node":
        pytest.skip("no support in node")

    with selenium_common(
        request,
        browser_type,
        web_server_main,
        load_pyodide=False,
        playwright_browser=playwright_browser,
    ) as selenium:
        selenium.goto(
            f"http://{selenium.server_hostname}:{selenium.server_port}/console.html"
        )
        selenium.javascript_setup()
        try:
            yield selenium
        finally:
            print(selenium.logs)


@pytest.fixture(scope="session")
def web_server_main(request):
    """Web server that serves files in the dist directory"""
    with spawn_web_server(request.config.option.dist_dir) as output:
        yield output


@pytest.fixture(scope="session")
def web_server_secondary(request):
    """Secondary web server that serves files dist directory"""
    with spawn_web_server(request.config.option.dist_dir) as output:
        yield output


@pytest.fixture(params=["classic", "module"], scope="module")
def script_type(request):
    return request.param
