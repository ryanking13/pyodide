import contextlib
import socket
import threading
from pathlib import Path

import pytest
from pytest_pyodide import run_in_pyodide

from conftest import only_node

pytestmark = [
    pytest.mark.requires_dynamic_linking,
    only_node,
]


@contextlib.contextmanager
def tcp_server(handler, *, timeout=5.0):
    """Start a TCP server on an OS-assigned port in a background thread.

    Yields the (host, port) the server is listening on.
    *handler* is called with ``(conn, addr)`` for each accepted connection.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    server_socket.settimeout(timeout)
    host, port = server_socket.getsockname()

    errors: list[str] = []
    ready = threading.Event()

    def _serve():
        ready.set()
        try:
            conn, addr = server_socket.accept()
            try:
                handler(conn, addr)
            finally:
                conn.close()
        except Exception as e:
            errors.append(str(e))
        finally:
            server_socket.close()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    ready.wait(timeout=timeout)

    try:
        yield host, port
    finally:
        thread.join(timeout=timeout)
        assert not errors, f"Server error: {errors[0]}"


def test_socket_connect(selenium_nodesock):
    """Test that Python socket can connect to a server and exchange data."""
    TEST_MESSAGE = b"Hello from client"
    RESPONSE_MESSAGE = b"Hello from server"

    server_received = []

    def handler(conn, _addr):
        data = conn.recv(1024)
        server_received.append(data)
        conn.sendall(RESPONSE_MESSAGE)

    @run_in_pyodide
    async def run(selenium, host, port, message):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        s.sendall(message)

        response = s.recv(1024)

        s.close()
        return response.decode()

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port, TEST_MESSAGE)
        assert len(server_received) == 1
        assert server_received[0] == TEST_MESSAGE
        assert result == RESPONSE_MESSAGE.decode()


def test_socket_multiple_send_recv(selenium_nodesock):
    """Test multiple send/recv operations on the same connection."""
    MESSAGES = [b"First message", b"Second message", b"Third message"]

    server_received = []

    def handler(conn, _addr):
        for _ in range(len(MESSAGES)):
            data = conn.recv(1024)
            if data:
                server_received.append(data)
                conn.sendall(data)

    @run_in_pyodide
    def run(selenium, host, port, messages):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        responses = []
        for msg in messages:
            s.sendall(msg)
            response = s.recv(1024)
            responses.append(response.decode())

        s.close()
        return responses

    with tcp_server(handler) as (host, port):
        results = run(selenium_nodesock, host, port, MESSAGES)
        assert len(server_received) == len(MESSAGES)
        assert results == [msg.decode() for msg in MESSAGES]


def test_socket_large_data_transfer(selenium_nodesock):
    """Test transferring larger amounts of data."""
    DATA_SIZE = 64 * 1024  # 64KB

    server_received = []

    def handler(conn, _addr):
        received = b""
        while len(received) < DATA_SIZE:
            chunk = conn.recv(8192)
            if not chunk:
                break
            received += chunk
        server_received.append(received)
        conn.sendall(f"Received {len(received)} bytes".encode())

    @run_in_pyodide
    def run(selenium, host, port, data_size):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        data = b"X" * data_size
        s.sendall(data)

        response = s.recv(1024)
        s.close()
        return response.decode()

    with tcp_server(handler, timeout=10.0) as (host, port):
        result = run(selenium_nodesock, host, port, DATA_SIZE)
        assert len(server_received) == 1
        assert len(server_received[0]) == DATA_SIZE
        assert result == f"Received {DATA_SIZE} bytes"


def test_socket_getpeername(selenium_nodesock):
    """Test socket.getpeername() returns correct remote address."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    @run_in_pyodide
    def run(selenium, host, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        peer = s.getpeername()
        s.sendall(b"test")
        s.recv(1024)
        s.close()
        return peer

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result[1] == port
        assert isinstance(result[0], str) and len(result[0]) > 0, (
            f"Expected non-empty host string, got: {result[0]}"
        )


def test_socket_getsockname(selenium_nodesock):
    """Test socket.getsockname() returns local address info."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    @run_in_pyodide
    def run(selenium, host, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        local = s.getsockname()
        s.sendall(b"test")
        s.recv(1024)
        s.close()
        return local

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert len(result) == 2
        assert isinstance(result[0], str)  # IP
        assert isinstance(result[1], int)  # Port


def test_socket_connection_refused(selenium_nodesock):
    """Test that connecting to a non-listening port raises an error."""
    # Bind to port 0, get the assigned port, then close immediately.
    # This gives us a port that is almost certainly not listening.
    tmp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tmp.bind(("127.0.0.1", 0))
    _, port = tmp.getsockname()
    tmp.close()

    @run_in_pyodide(packages=["pytest"])
    def run(selenium, port):
        import socket

        import pytest

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(OSError):
            s.connect(("127.0.0.1", port))

    run(selenium_nodesock, port)


def test_socket_recv_after_close(selenium_nodesock):
    """Test receiving data after server closes connection."""

    def handler(conn, _addr):
        conn.sendall(b"Final message")

    @run_in_pyodide
    def run(selenium, host, port):
        import socket
        import time

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        time.sleep(0.5)

        data = s.recv(1024)
        s.close()
        return data.decode()

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == "Final message"


def test_socket_recv_after_close_chunked(selenium_nodesock):
    """Drain a full message in small reads after the server has closed.

    Exercises reading across several on-demand reads once the peer has closed,
    followed by a clean EOF (empty recv).
    """

    def handler(conn, _addr):
        conn.sendall(b"".join(b"line%02d\n" % i for i in range(50)))

    @run_in_pyodide
    def run(selenium, host, port):
        import socket
        import time

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        time.sleep(0.5)

        chunks = []
        while True:
            chunk = s.recv(8)
            if not chunk:
                break
            chunks.append(chunk)
        s.close()
        return b"".join(chunks)

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == b"".join(b"line%02d\n" % i for i in range(50))


def test_socket_fileno(selenium_nodesock):
    """Test that socket.fileno() returns a valid file descriptor."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    @run_in_pyodide
    def run(selenium, host, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fd_before = s.fileno()

        s.connect((host, port))
        fd_after = s.fileno()

        s.sendall(b"test")
        s.recv(1024)
        s.close()

        return (fd_before, fd_after)

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert isinstance(result[0], int) and result[0] > 0
        assert isinstance(result[1], int) and result[1] > 0
        assert result[0] == result[1]


def test_socket_send_recv_partial(selenium_nodesock):
    """Test partial recv when buffer is smaller than data."""
    FULL_MESSAGE = b"A" * 1000

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(FULL_MESSAGE)

    @run_in_pyodide
    def run(selenium, host, port, full_message):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        s.sendall(b"start")

        received = b""
        while len(received) < len(full_message):
            chunk = s.recv(100)
            if not chunk:
                break
            received += chunk

        s.close()
        return received.decode()

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port, FULL_MESSAGE)
        assert len(result) == len(FULL_MESSAGE)


def test_socket_create_multiple(selenium_nodesock):
    """Test creating multiple sockets simultaneously."""

    def echo_handler(conn, _addr):
        data = conn.recv(1024)
        _, sport = conn.getsockname()
        conn.sendall(f"Server{sport}:{data.decode()}".encode())

    @run_in_pyodide
    def run(selenium, host1, port1, host2, port2):
        import socket

        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        s1.connect((host1, port1))
        s2.connect((host2, port2))

        s1.sendall(b"Hello1")
        s2.sendall(b"Hello2")

        r1 = s1.recv(1024)
        r2 = s2.recv(1024)

        s1.close()
        s2.close()

        return [r1.decode(), r2.decode()]

    with (
        tcp_server(echo_handler) as (host1, port1),
        tcp_server(echo_handler) as (host2, port2),
    ):
        result = run(selenium_nodesock, host1, port1, host2, port2)
        assert result == [f"Server{port1}:Hello1", f"Server{port2}:Hello2"]


def test_socket_recv_eof(selenium_nodesock):
    """Test that recv returns b'' after server closes and all data is consumed."""

    def handler(conn, _addr):
        conn.sendall(b"goodbye")
        conn.close()

    @run_in_pyodide
    def run(selenium, host, port):
        import socket
        import time

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        data = s.recv(1024)

        # Give time for the FIN to arrive
        time.sleep(1.0)

        eof = s.recv(1024)

        s.close()
        return (data.decode(), len(eof))

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result[0] == "goodbye"
        assert result[1] == 0


def test_socket_send_after_remote_close(selenium_nodesock):
    """Test that sending data after the remote side closes raises an error."""

    def handler(conn, _addr):
        conn.close()

    @run_in_pyodide(packages=["pytest"])
    def run(selenium, host, port):
        import socket
        import time

        import pytest

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        # Give time for the FIN to arrive
        time.sleep(0.5)

        with pytest.raises(OSError):
            # Send enough data to trigger the error
            for _ in range(10):
                s.sendall(b"X" * 4096)
                time.sleep(0.05)

    with tcp_server(handler) as (host, port):
        run(selenium_nodesock, host, port)


def test_socket_makefile(selenium_nodesock):
    """Test socket.makefile() with line-based I/O."""

    def handler(conn, _addr):
        conn.sendall(b"line1\nline2\nline3\n")
        conn.close()

    @run_in_pyodide
    def run(selenium, host, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        f = s.makefile("r")
        lines = f.readlines()
        f.close()
        s.close()
        return [l.strip() for l in lines]

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == ["line1", "line2", "line3"]


def test_socket_asyncio_concurrent(selenium_nodesock):
    """Test concurrent socket operations with asyncio.gather."""

    def echo_handler(conn, _addr):
        data = conn.recv(1024)
        conn.sendall(data)

    @run_in_pyodide
    async def run(selenium, host1, port1, host2, port2):
        import asyncio
        import socket

        async def socket_task(host, port, msg):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            s.sendall(msg.encode())
            data = s.recv(1024)
            s.close()
            return data.decode()

        r1, r2 = await asyncio.gather(
            socket_task(host1, port1, "msg1"), socket_task(host2, port2, "msg2")
        )
        return [r1, r2]

    with (
        tcp_server(echo_handler) as (host1, port1),
        tcp_server(echo_handler) as (host2, port2),
    ):
        result = run(selenium_nodesock, host1, port1, host2, port2)
        assert result == ["msg1", "msg2"]


def test_socket_large_recv(selenium_nodesock):
    """Test receiving large data (64KB) from server via recv loop."""
    DATA_SIZE = 64 * 1024  # 64KB

    def handler(conn, _addr):
        conn.recv(1024)  # wait for ready signal
        data = b"Y" * DATA_SIZE
        conn.sendall(data)
        conn.close()

    @run_in_pyodide
    def run(selenium, host, port, data_size):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        s.sendall(b"ready")

        received = b""
        while len(received) < data_size:
            chunk = s.recv(8192)
            if not chunk:
                break
            received += chunk

        s.close()
        return (len(received), received == b"Y" * data_size)

    with tcp_server(handler, timeout=10.0) as (host, port):
        result = run(selenium_nodesock, host, port, DATA_SIZE)
        assert result[0] == DATA_SIZE
        assert result[1] is True, "Received data content mismatch"


def test_socket_double_close(selenium_nodesock):
    """Test that closing a socket twice does not crash."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    @run_in_pyodide
    def run(selenium, host, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        s.sendall(b"test")
        s.recv(1024)

        s.close()
        s.close()  # second close should not raise

    with tcp_server(handler) as (host, port):
        run(selenium_nodesock, host, port)


def test_socket_shutdown(selenium_nodesock):
    """Test that shutting down a socket works."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    @run_in_pyodide
    def run(selenium, host, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        s.sendall(b"test")
        s.recv(1024)

        s.shutdown(socket.SHUT_RDWR)
        s.close()

    with tcp_server(handler) as (host, port):
        run(selenium_nodesock, host, port)


def test_socket_shutdown_pairs(selenium_nodesock):
    """All 9 combinations of two consecutive shutdown() calls should succeed (Linux behavior)."""

    server_conns = []

    def handler(conn, _addr):
        server_conns.append(conn)
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                conn.sendall(data)
        except OSError:
            pass

    @run_in_pyodide
    def run(selenium, host, port, first, second):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s.sendall(b"ping")
        s.recv(1024)

        s.shutdown(first)
        s.shutdown(second)
        s.close()

    shut_values = [0, 1, 2]
    for first in shut_values:
        for second in shut_values:
            with tcp_server(handler) as (host, port):
                run(selenium_nodesock, host, port, first, second)
            server_conns.clear()


def test_socket_nonblocking_recv_with_buffered_data(selenium_nodesock):
    """Non-blocking recv returns buffered data once the socket is readable."""

    def handler(conn, _addr):
        data = conn.recv(1024)
        conn.sendall(data)

    @run_in_pyodide
    def run(selenium, host, port):
        import select
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        s.sendall(b"hello")

        s.setblocking(False)
        readable, _, _ = select.select([s], [], [], 5.0)
        assert readable, "socket should become readable"
        data = s.recv(1024)
        s.close()
        return data

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == b"hello"


@pytest.mark.parametrize("timeout", [2.0, None])
def test_socket_select_returns_when_any_socket_is_readable(selenium_nodesock, timeout):
    """select() returns for one ready NodeSockFS socket without waiting for another."""

    release_blocked_handler = threading.Event()

    def ready_handler(conn, _addr):
        assert conn.recv(1024) == b"ready"
        conn.sendall(b"ready")

    def blocked_handler(conn, _addr):
        release_blocked_handler.wait(timeout=2.0)

    @run_in_pyodide
    def run(selenium, host1, port1, host2, port2, timeout):
        import select
        import socket
        import time

        first = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        second = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            first.connect((host1, port1))
            second.connect((host2, port2))
            first.sendall(b"ready")
            started = time.monotonic()
            readable, _, _ = select.select([first, second], [], [], timeout)
            elapsed = time.monotonic() - started
            return first in readable, second in readable, elapsed
        finally:
            first.close()
            second.close()

    with (
        tcp_server(ready_handler) as (host1, port1),
        tcp_server(blocked_handler) as (host2, port2),
    ):
        first_ready, second_ready, elapsed = run(
            selenium_nodesock,
            host1,
            port1,
            host2,
            port2,
            timeout,
        )
        release_blocked_handler.set()
    assert first_ready
    assert not second_ready
    assert elapsed < 1.0


def test_socket_select_timeout_zero_reports_all_buffered_sockets(selenium_nodesock):
    """A timeout-zero select processes every ready NodeSockFS descriptor."""

    def handler(conn, _addr):
        conn.sendall(b"ready")
        assert conn.recv(1024) == b""

    @run_in_pyodide
    def run(selenium, host1, port1, host2, port2):
        import select
        import socket

        first = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        second = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            first.connect((host1, port1))
            second.connect((host2, port2))
            assert select.select([first], [], [], 5.0)[0] == [first]
            assert select.select([second], [], [], 5.0)[0] == [second]
            return select.select([first, second], [], [], 0)[0] == [first, second]
        finally:
            first.close()
            second.close()

    with (
        tcp_server(handler) as (host1, port1),
        tcp_server(handler) as (host2, port2),
    ):
        assert run(selenium_nodesock, host1, port1, host2, port2)


def test_socket_poll_ignores_negative_fd(selenium_nodesock):
    """poll() clears and ignores negative entries while processing live sockets."""

    def handler(conn, _addr):
        assert conn.recv(1024) == b""

    @run_in_pyodide
    def open_socket(selenium, host, port):
        import builtins
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        builtins.__dict__["poll_test_socket"] = sock
        return sock.fileno()

    @run_in_pyodide
    def close_socket(selenium):
        import builtins

        builtins.__dict__["poll_test_socket"].close()
        del builtins.__dict__["poll_test_socket"]

    with tcp_server(handler) as (host, port):
        fd = open_socket(selenium_nodesock, host, port)
        try:
            result, negative_revents, socket_revents = selenium_nodesock.run_js(
                f"""
                const pollfds = pyodide._module._malloc(16);
                try {{
                  pyodide._module.HEAP32[pollfds >> 2] = -1;
                  pyodide._module.HEAP16[(pollfds + 4) >> 1] = 1;
                  pyodide._module.HEAP16[(pollfds + 6) >> 1] = 0x7fff;
                  pyodide._module.HEAP32[(pollfds + 8) >> 2] = {fd};
                  pyodide._module.HEAP16[(pollfds + 12) >> 1] = 4;
                  pyodide._module.HEAP16[(pollfds + 14) >> 1] = 0;
                  const result = await pyodide._module.SOCKFS.pollAsync(
                    pollfds,
                    2,
                    0,
                  );
                  return [
                    result,
                    pyodide._module.HEAP16[(pollfds + 6) >> 1],
                    pyodide._module.HEAP16[(pollfds + 14) >> 1],
                  ];
                }} finally {{
                  pyodide._module._free(pollfds);
                }}
                """
            )
            assert result == 1
            assert negative_revents == 0
            assert socket_revents & 4
        finally:
            close_socket(selenium_nodesock)


def test_socket_send_after_shutdown_write_raises_epipe(selenium_nodesock):
    """SHUT_WR puts the NodeSockFS writer into a terminal EPIPE state."""

    def handler(conn, _addr):
        assert conn.recv(1024) == b""

    @run_in_pyodide(packages=["pytest"])
    def run(selenium, host, port):
        import socket

        import pytest

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((host, port))
            sock.shutdown(socket.SHUT_WR)
            with pytest.raises(BrokenPipeError):
                sock.send(b"after shutdown")
        finally:
            sock.close()

    with tcp_server(handler) as (host, port):
        run(selenium_nodesock, host, port)


def test_socket_nonblocking_recv_eagain_then_data(selenium_nodesock):
    """A non-blocking recv reports EAGAIN until an on-demand read surfaces data.

    Without select(), a plain retry loop still makes progress: the first recv
    kicks a read and raises BlockingIOError, and a later retry returns the data.
    """

    def handler(conn, _addr):
        data = conn.recv(1024)
        conn.sendall(data)

    @run_in_pyodide(packages=["pytest"])
    def run(selenium, host, port):
        import socket
        import time

        import pytest

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s.sendall(b"hello")
        time.sleep(0.5)

        s.setblocking(False)

        with pytest.raises(BlockingIOError):
            s.recv(1024)

        data = b""
        for _ in range(100):
            try:
                data = s.recv(1024)
                break
            except BlockingIOError:
                time.sleep(0.05)
        s.close()
        return data

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == b"hello"


def test_socket_select_readable_on_eof(selenium_nodesock):
    """select() reports a peer-closed socket as readable; recv then returns b''."""

    def handler(conn, _addr):
        conn.close()

    @run_in_pyodide
    def run(selenium, host, port):
        import select
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        readable, _, _ = select.select([s], [], [], 5.0)
        assert readable, "a closed peer should be reported readable"
        data = s.recv(1024)
        s.close()
        return len(data)

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == 0


def test_socket_recv_backpressure(selenium_nodesock):
    """Receiving large data doesn't cause unbounded memory growth."""
    DATA_SIZE = 1024 * 1024

    server_sent = []

    def handler(conn, _addr):
        conn.recv(1024)
        data = b"A" * DATA_SIZE
        conn.sendall(data)
        server_sent.append(len(data))
        conn.close()

    @run_in_pyodide
    def run(selenium, host, port, data_size):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        s.sendall(b"go")

        received = b""
        while len(received) < data_size:
            chunk = s.recv(65536)
            if not chunk:
                break
            received += chunk

        s.close()
        return len(received)

    with tcp_server(handler, timeout=15.0) as (host, port):
        nbytes = run(selenium_nodesock, host, port, DATA_SIZE)
        assert nbytes == DATA_SIZE
        assert server_sent[0] == DATA_SIZE


def test_socket_shutdown_non_nodesock(selenium_standalone):
    """
    Calling shutdown on a non-node socket will raise "Function not implemented"
    """

    @run_in_pyodide(packages=["pytest"])
    def run(selenium):
        import socket

        import pytest

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.listen(1)

        assert hasattr(s, "shutdown"), "shutdown method should exist"

        with pytest.raises(OSError, match="Function not implemented"):
            s.shutdown(socket.SHUT_RDWR)

        s.close()

    run(selenium_standalone)


def test_socket_settimeout_nonblocking(selenium_nodesock):
    """settimeout(0) makes recv raise socket.timeout when no data is available."""

    def handler(conn, _addr):
        import time

        time.sleep(2)
        conn.sendall(b"delayed")
        conn.close()

    @run_in_pyodide(packages=["pytest"])
    def run(selenium, host, port):
        import socket

        import pytest

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        s.settimeout(0)

        with pytest.raises(OSError):
            s.recv(1024)

    with tcp_server(handler) as (host, port):
        run(selenium_nodesock, host, port)


def test_socket_settimeout_restore_blocking(selenium_nodesock):
    """settimeout(0) then settimeout(None) restores blocking mode."""

    def handler(conn, _addr):
        conn.sendall(b"hello")
        conn.close()

    @run_in_pyodide
    def run(selenium, host, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        s.settimeout(0)
        s.settimeout(None)

        data = s.recv(1024)
        s.close()
        return data.decode()

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == "hello"


# ---------------------------------------------------------------------------
# asyncio webloop tests
# ---------------------------------------------------------------------------


def test_asyncio_sock_connect_recv_sendall(selenium_nodesock):
    """Test low-level sock_connect + sock_recv + sock_sendall via asyncio."""
    TEST_MESSAGE = b"async hello"
    RESPONSE = b"async reply"

    def handler(conn, _addr):
        _ = conn.recv(1024)
        conn.sendall(RESPONSE)

    @run_in_pyodide
    async def run(selenium, host, port, message):
        import asyncio
        import socket

        loop = asyncio.get_event_loop()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(False)

        await loop.sock_connect(s, (host, port))
        await loop.sock_sendall(s, message)
        data = await loop.sock_recv(s, 1024)
        s.close()
        return data.decode()

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port, TEST_MESSAGE)
        assert result == RESPONSE.decode()


def test_asyncio_create_connection_echo(selenium_nodesock):
    """Test create_connection with an echo protocol."""

    def handler(conn, _addr):
        while True:
            data = conn.recv(1024)
            if not data:
                break
            conn.sendall(data)

    @run_in_pyodide
    async def run(selenium, host, port):
        import asyncio

        class EchoClient(asyncio.Protocol):
            def __init__(self):
                self.received = bytearray()
                self.done = asyncio.get_event_loop().create_future()

            def data_received(self, data):
                self.received.extend(data)

            def connection_lost(self, exc):
                if not self.done.done():
                    self.done.set_result(None)

        loop = asyncio.get_event_loop()
        transport, proto = await loop.create_connection(EchoClient, host, port)

        transport.write(b"First")
        transport.write(b"Second")
        transport.write(b"Third")

        await asyncio.sleep(1)
        transport.close()
        await asyncio.wait_for(proto.done, timeout=5.0)
        return proto.received.decode()

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert "First" in result
        assert "Second" in result
        assert "Third" in result


def test_asyncio_create_connection_server_closes(selenium_nodesock):
    """Server sends data then closes; transport should detect EOF."""

    def handler(conn, _addr):
        conn.sendall(b"goodbye")
        conn.close()

    @run_in_pyodide
    async def run(selenium, host, port):
        import asyncio

        class Receiver(asyncio.Protocol):
            def __init__(self):
                self.received = bytearray()
                self.lost_exc = "not_called"
                self.done = asyncio.get_event_loop().create_future()

            def data_received(self, data):
                self.received.extend(data)

            def connection_lost(self, exc):
                self.lost_exc = repr(exc)
                if not self.done.done():
                    self.done.set_result(None)

        loop = asyncio.get_event_loop()
        _, proto = await loop.create_connection(Receiver, host, port)

        await asyncio.wait_for(proto.done, timeout=5.0)
        return (proto.received.decode(), proto.lost_exc)

    with tcp_server(handler) as (host, port):
        data, exc = run(selenium_nodesock, host, port)
        assert data == "goodbye"
        assert exc == "None"


def test_asyncio_open_connection(selenium_nodesock):
    """Test asyncio.open_connection (StreamReader/Writer API)."""
    RESPONSE = b"stream reply"

    def handler(conn, _addr):
        _ = conn.recv(1024)
        conn.sendall(RESPONSE)
        conn.close()

    @run_in_pyodide
    async def run(selenium, host, port):
        import asyncio

        reader, writer = await asyncio.open_connection(host, port)

        writer.write(b"hello")
        await writer.drain()

        data = await reader.read(1024)
        writer.close()
        return data.decode()

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == RESPONSE.decode()


def test_asyncio_open_connection_hostname(selenium_nodesock):
    """Test that Emscripten's synthetic address maps back to its hostname."""
    RESPONSE = b"hostname reply"

    def handler(conn, _addr):
        conn.sendall(RESPONSE)

    @run_in_pyodide
    async def run(selenium, port):
        import asyncio
        import socket

        reader, writer = await asyncio.open_connection(
            "localhost", port, family=socket.AF_INET
        )
        data = await reader.read(1024)
        writer.close()
        return data.decode()

    with tcp_server(handler) as (_host, port):
        result = run(selenium_nodesock, port)
        assert result == RESPONSE.decode()


def test_asyncio_sock_recv_into(selenium_nodesock):
    """Test sock_recv_into fills a buffer."""
    RESPONSE = b"buffer test"

    def handler(conn, _addr):
        conn.sendall(RESPONSE)

    @run_in_pyodide
    async def run(selenium, host, port, expected_len):
        import asyncio
        import socket

        loop = asyncio.get_event_loop()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(False)

        await loop.sock_connect(s, (host, port))

        buf = bytearray(1024)
        n = await loop.sock_recv_into(s, buf)
        s.close()
        return (n, buf[:n].decode())

    with tcp_server(handler) as (host, port):
        n, data = run(selenium_nodesock, host, port, len(RESPONSE))
        assert n == len(RESPONSE)
        assert data == RESPONSE.decode()


def test_asyncio_concurrent_connections(selenium_nodesock):
    """Two concurrent open_connection calls via asyncio.gather."""

    def handler(conn, _addr):
        data = conn.recv(1024)
        conn.sendall(data)

    @run_in_pyodide
    async def run(selenium, host1, port1, host2, port2):
        import asyncio

        async def do_echo(host, port, msg):
            reader, writer = await asyncio.open_connection(host, port)
            writer.write(msg)
            await writer.drain()
            data = await reader.read(1024)
            writer.close()
            return data.decode()

        r1, r2 = await asyncio.gather(
            do_echo(host1, port1, b"conn1"),
            do_echo(host2, port2, b"conn2"),
        )
        return (r1, r2)

    with (
        tcp_server(handler) as (host1, port1),
        tcp_server(handler) as (host2, port2),
    ):
        result = run(selenium_nodesock, host1, port1, host2, port2)
        assert result[0] == "conn1"
        assert result[1] == "conn2"


def test_asyncio_client_close_lifecycle(selenium_nodesock):
    """Verify transport.close() triggers connection_lost(None)."""

    def handler(conn, _addr):
        while True:
            data = conn.recv(1024)
            if not data:
                break
            conn.sendall(data)

    @run_in_pyodide
    async def run(selenium, host, port):
        import asyncio

        events = []

        class Tracker(asyncio.Protocol):
            def __init__(self):
                self.done = asyncio.get_event_loop().create_future()

            def connection_made(self, transport):
                events.append("connection_made")
                self.transport = transport

            def data_received(self, data):
                events.append(f"data:{data.decode()}")

            def connection_lost(self, exc):
                events.append(f"connection_lost:{exc}")
                if not self.done.done():
                    self.done.set_result(None)

        loop = asyncio.get_event_loop()
        transport, proto = await loop.create_connection(Tracker, host, port)

        transport.write(b"ping")
        await asyncio.sleep(0.5)

        assert not transport.is_closing()
        transport.close()
        # Give some time for the close to propagate
        await asyncio.sleep(0.1)
        assert transport.is_closing()

        await asyncio.wait_for(proto.done, timeout=5.0)
        return ",".join(events)

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert "connection_made" in result
        assert "connection_lost:None" in result


# ---------------------------------------------------------------------------
# TLS tests
# ---------------------------------------------------------------------------


@pytest.fixture
def self_signed_cert(tmp_path):
    import datetime
    import ipaddress

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    certfile = tmp_path / "cert.pem"
    keyfile = tmp_path / "key.pem"

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(
            datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)
        )
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    Path(certfile).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    Path(keyfile).write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return certfile, keyfile


@contextlib.contextmanager
def tls_server(handler, certfile, keyfile, *, timeout=5.0):
    """Start a TLS server with a self-signed cert. Yields (host, port)."""
    import ssl as host_ssl

    server_ctx = host_ssl.SSLContext(host_ssl.PROTOCOL_TLS_SERVER)  # type: ignore[attr-defined]
    server_ctx.load_cert_chain(certfile, keyfile)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    server_socket.settimeout(timeout)
    host, port = server_socket.getsockname()
    tls_sock = server_ctx.wrap_socket(server_socket, server_side=True)

    errors: list[str] = []
    ready = threading.Event()

    def _serve():
        ready.set()
        try:
            conn, addr = tls_sock.accept()
            try:
                handler(conn, addr)
            finally:
                conn.close()
        except Exception as e:
            errors.append(str(e))
        finally:
            tls_sock.close()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    ready.wait(timeout=timeout)

    try:
        yield host, port
    finally:
        thread.join(timeout=timeout)
        assert not errors, f"TLS server error: {errors[0]}"


@contextlib.contextmanager
def starttls_server(handler, certfile, keyfile, *, greeting=b"GREETING", timeout=5.0):
    """Start a server that speaks plaintext first, then upgrades in place to TLS.

    It sends *greeting* in the clear, reads one plaintext upgrade request, then
    wraps the same connection with TLS server-side before invoking *handler*.
    This models the STARTTLS/PyMySQL flow. Yields (host, port).
    """
    import ssl as host_ssl

    server_ctx = host_ssl.SSLContext(host_ssl.PROTOCOL_TLS_SERVER)  # type: ignore[attr-defined]
    server_ctx.load_cert_chain(certfile, keyfile)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    server_socket.settimeout(timeout)
    host, port = server_socket.getsockname()

    errors: list[str] = []
    ready = threading.Event()

    def _serve():
        ready.set()
        try:
            conn, addr = server_socket.accept()
            conn.sendall(greeting)
            conn.recv(1024)
            tls_conn = server_ctx.wrap_socket(conn, server_side=True)
            try:
                handler(tls_conn, addr)
            finally:
                tls_conn.close()
        except Exception as e:
            errors.append(str(e))
        finally:
            server_socket.close()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    ready.wait(timeout=timeout)

    try:
        yield host, port
    finally:
        thread.join(timeout=timeout)
        assert not errors, f"STARTTLS server error: {errors[0]}"


@pytest.mark.skip_refcount_check
def test_tls_starttls_send_recv(selenium_nodesock, self_signed_cert):
    """Connect plain TCP, upgrade via wrap_socket/startTls, exchange data over TLS."""
    RESPONSE = b"TLS OK"

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(RESPONSE)

    @run_in_pyodide
    def run(selenium, host, port):
        import socket
        import ssl

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # type: ignore[attr-defined]
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # type: ignore[attr-defined]
        ctx.check_hostname = False

        ss = ctx.wrap_socket(s, server_hostname="localhost")
        ss.sendall(b"Hello TLS")
        response = ss.recv(1024)
        ss.close()
        return response.decode()

    with tls_server(handler, *self_signed_cert) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == RESPONSE.decode()


@pytest.mark.skip_refcount_check
def test_tls_starttls_after_plaintext_greeting(selenium_nodesock, self_signed_cert):
    """Consume a plaintext greeting with a blocking recv, then upgrade to TLS.

    This is the PyMySQL/SMTP STARTTLS flow: the on-demand reader must reach a
    quiescent point after the greeting so startTls can release the stream lock
    (a pending read here crashes releaseLock in workerd).
    """
    GREETING = b"GREETING"
    RESPONSE = b"TLS OK"

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(RESPONSE)

    @run_in_pyodide
    def run(selenium, host, port, greeting):
        import socket
        import ssl

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        assert s.recv(1024) == greeting
        s.sendall(b"STARTTLS")

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # type: ignore[attr-defined]
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # type: ignore[attr-defined]
        ctx.check_hostname = False

        ss = ctx.wrap_socket(s, server_hostname="localhost")
        ss.sendall(b"Hello TLS")
        response = ss.recv(1024)
        ss.close()
        return response.decode()

    with starttls_server(handler, *self_signed_cert, greeting=GREETING) as (host, port):
        result = run(selenium_nodesock, host, port, GREETING)
        assert result == RESPONSE.decode()


@pytest.mark.skip_refcount_check
def test_tls_starttls_multiple_roundtrips(selenium_nodesock, self_signed_cert):
    """Exchange several messages over TLS after the upgrade.

    Verifies that the reader swapped in by startTls keeps re-arming on-demand
    reads across multiple recv calls.
    """

    def handler(conn, _addr):
        for _ in range(3):
            data = conn.recv(1024)
            if not data:
                break
            conn.sendall(b"echo:" + data)

    @run_in_pyodide
    def run(selenium, host, port):
        import socket
        import ssl

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # type: ignore[attr-defined]
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # type: ignore[attr-defined]
        ctx.check_hostname = False

        ss = ctx.wrap_socket(s, server_hostname="localhost")
        results = []
        for i in range(3):
            ss.sendall(f"msg{i}".encode())
            results.append(ss.recv(1024).decode())
        ss.close()
        return results

    with tls_server(handler, *self_signed_cert) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == ["echo:msg0", "echo:msg1", "echo:msg2"]


def test_asyncio_nodesock_fd_readiness_rejects_unsupported_descriptors(
    selenium_nodesock,
):
    """WebLoop does not expose readiness registration for arbitrary descriptors."""

    @run_in_pyodide(packages=["pytest"])
    def run(selenium):
        import asyncio
        import os

        import pytest

        loop = asyncio.get_event_loop()
        path = "/nodesock-readiness-test"
        fd = os.open(path, os.O_CREAT | os.O_RDWR)
        try:
            for add in (loop.add_reader, loop.add_writer):
                with pytest.raises(NotImplementedError):
                    add(fd, lambda: None)

            # Test negative descriptor
            with pytest.raises(ValueError):
                loop.add_reader(-1, lambda: None)
        finally:
            os.close(fd)
            os.unlink(path)

    run(selenium_nodesock)


def test_asyncio_nodesock_fd_readiness_callbacks(selenium_nodesock):
    """WebLoop reader and writer registrations work for NodeSockFS sockets."""

    def handler(conn, _addr):
        for expected in (b"reader", b"replace", b"remove"):
            assert conn.recv(1024) == expected
            conn.sendall(expected)

    @run_in_pyodide
    async def run(selenium, host, port):
        import asyncio
        import contextvars
        import socket

        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        fd = sock.fileno()
        received = []
        context_value = contextvars.ContextVar("context_value", default="default")
        writer_called = loop.create_future()
        reader_called = loop.create_future()

        def writer_callback(arg):
            loop.remove_writer(fd)
            if not writer_called.done():
                writer_called.set_result(arg)

        def reader_callback(arg):
            received.append((arg, context_value.get(), sock.recv(1024)))
            loop.remove_reader(sock)
            if not reader_called.done():
                reader_called.set_result(None)

        try:
            loop.add_writer(fd, writer_callback, "writer")
            token = context_value.set("reader registration")
            try:
                loop.add_reader(sock, reader_callback, "reader")
            finally:
                context_value.reset(token)

            sock.sendall(b"reader")
            assert await asyncio.wait_for(writer_called, timeout=5) == "writer"
            await asyncio.wait_for(reader_called, timeout=5)
            assert received == [("reader", "reader registration", b"reader")]
            assert loop.remove_reader(fd) is False
            assert loop.remove_writer(sock) is False

            old_called = []
            replacement_called = loop.create_future()

            def old_callback():
                old_called.append(True)

            def replacement_callback():
                data = sock.recv(1024)
                loop.remove_reader(fd)
                if not replacement_called.done():
                    replacement_called.set_result(data)

            loop.add_reader(fd, old_callback)
            loop.add_reader(fd, replacement_callback)
            sock.sendall(b"replace")
            assert await asyncio.wait_for(replacement_called, timeout=5) == b"replace"
            assert old_called == []

            removed_called = []
            loop.add_reader(fd, lambda: removed_called.append(True))
            assert loop.remove_reader(fd) is True
            sock.sendall(b"remove")
            assert sock.recv(1024) == b"remove"
            await asyncio.sleep(0)
            assert removed_called == []
        finally:
            loop.remove_reader(fd)
            loop.remove_writer(fd)
            sock.close()

    with tcp_server(handler) as (host, port):
        run(selenium_nodesock, host, port)


def test_asyncio_nodesock_closed_fd_reuse_ignores_stale_reader(selenium_nodesock):
    """A queued readiness result cannot target a new socket reusing its fd."""

    @run_in_pyodide
    async def run(selenium):
        import asyncio
        import socket

        loop = asyncio.get_event_loop()
        original = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fd = original.fileno()
        called = []

        loop.add_reader(fd, lambda: called.append(True))
        original.close()

        replacement = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            assert replacement.fileno() == fd
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert called == []
            assert loop.remove_reader(fd) is False
        finally:
            replacement.close()

    run(selenium_nodesock)


def test_asyncio_nodesock_reader_eof_callback_can_close_socket(selenium_nodesock):
    """EOF wakes a reader, and closing its fd prevents another registration."""

    def handler(_conn, _addr):
        pass

    @run_in_pyodide
    async def run(selenium, host, port):
        import asyncio
        import socket

        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        fd = sock.fileno()
        eof = loop.create_future()

        def reader_callback():
            assert sock.recv(1024) == b""
            sock.close()
            if not eof.done():
                eof.set_result(None)

        try:
            loop.add_reader(fd, reader_callback)
            await asyncio.wait_for(eof, timeout=5)
            assert loop.remove_reader(fd) is False
        finally:
            loop.remove_reader(fd)
            sock.close()

    with tcp_server(handler) as (host, port):
        run(selenium_nodesock, host, port)


def test_asyncio_nodesock_reader_exception_rearms(selenium_nodesock):
    """Reader callback errors use the loop handler and leave the reader active."""

    def handler(conn, _addr):
        assert conn.recv(1024) == b"first"
        conn.sendall(b"bad")
        assert conn.recv(1024) == b"next"
        conn.sendall(b"good")

    @run_in_pyodide
    async def run(selenium, host, port):
        import asyncio
        import socket

        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        errors = []
        second_call = loop.create_future()
        calls = 0

        def exception_handler(_loop, context):
            errors.append(context["exception"])

        def reader_callback():
            nonlocal calls
            calls += 1
            data = sock.recv(1024)
            if calls == 1:
                assert data == b"bad"
                sock.sendall(b"next")
                raise RuntimeError("reader callback failed")
            loop.remove_reader(sock)
            if not second_call.done():
                second_call.set_result(data)

        previous_handler = loop.get_exception_handler()
        loop.set_exception_handler(exception_handler)
        try:
            loop.add_reader(sock, reader_callback)
            sock.sendall(b"first")
            assert await asyncio.wait_for(second_call, timeout=5) == b"good"
            assert len(errors) == 1
            assert isinstance(errors[0], RuntimeError)
        finally:
            loop.remove_reader(sock)
            loop.set_exception_handler(previous_handler)
            sock.close()

    with tcp_server(handler) as (host, port):
        run(selenium_nodesock, host, port)
