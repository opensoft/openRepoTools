# SPDX-License-Identifier: Apache-2.0
"""Accept ownership invariants; no claim of reproducing a kernel scheduling race."""

from __future__ import annotations

import asyncio
import contextlib
import json
import socket

import pytest

from test_lane_managed_cli import _load_cli, _request


class _Connection:
    def __init__(self, sock):
        self.sock = sock
        self.close_calls = 0

    def __getattr__(self, name):
        return getattr(self.sock, name)

    def close(self):
        self.close_calls += 1
        self.sock.close()


class _Accept:
    """Controlled Unix readiness, with the old sock_accept seam for comparison."""

    fd = 987654321

    def __init__(self):
        self.legacy_result = asyncio.get_running_loop().create_future()
        self.entered = asyncio.Event()
        self.exited = asyncio.Event()
        self.calls = 0
        self.registrations = 0
        self.removals = 0
        self.callback = None
        self.outcome = None

    def fileno(self):
        return self.fd

    def setblocking(self, value):
        assert value is False

    def install(self, monkeypatch):
        loop = asyncio.get_running_loop()
        add_reader, remove_reader = loop.add_reader, loop.remove_reader

        def add(fd, callback, *args):
            if fd != self.fd:
                return add_reader(fd, callback, *args)
            assert self.callback is None
            self.callback = lambda: callback(*args)
            self.registrations += 1
            self.entered.set()

        def remove(fd):
            if fd != self.fd:
                return remove_reader(fd)
            assert self.callback is not None
            self.callback = None
            self.removals += 1
            self.exited.set()
            return True

        monkeypatch.setattr(loop, "add_reader", add)
        monkeypatch.setattr(loop, "remove_reader", remove)
        monkeypatch.setattr(loop, "sock_accept", self.legacy_accept)

    def accept(self):
        self.calls += 1
        outcome, self.outcome = self.outcome, None
        if isinstance(outcome, BaseException):
            raise outcome
        assert outcome is not None
        return outcome

    def fire(self, outcome):
        assert self.callback is not None
        self.outcome = outcome
        self.callback()

    async def legacy_accept(self, server):
        self.entered.set()
        try:
            return await self.legacy_result
        finally:
            self.exited.set()


class _Polls:
    """Replace only poll scheduling; keep asyncio tasks/I/O/cancellation real."""

    def __init__(self):
        self.calls = asyncio.Queue()

    def __getattr__(self, name):
        return getattr(asyncio, name)

    async def wait(self, tasks, *, timeout):
        assert timeout == 0.1
        task, = tasks
        gate = asyncio.get_running_loop().create_future()
        self.calls.put_nowait((task, gate))
        return await gate


@pytest.fixture
def sockets():
    owned, peer = socket.socketpair()
    owned.setblocking(False)
    peer.setblocking(False)
    try:
        yield _Connection(owned), peer
    finally:
        owned.close()
        peer.close()


def _start(api, monkeypatch, handler, stop):
    accept, polls = _Accept(), _Polls()
    accept.install(monkeypatch)
    monkeypatch.setitem(api, "asyncio", polls)
    service = asyncio.create_task(api["_serve_daemon_loop"](
        accept, handler, connect_timeout=1.0, operation_timeout=2.0,
        max_bytes=api["MAX_FRAME_BYTES"], max_requests=1, stop_event=stop,
    ))
    return accept, polls, service


async def _cancel(service):
    service.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await service


def _run(scenario):
    async def bounded():
        # Watchdog only: all interleavings are driven by futures/events.
        await asyncio.wait_for(scenario(), timeout=5.0)

    asyncio.run(bounded())


def test_poll_timeout_does_not_cancel_accept_before_shutdown(monkeypatch):
    """Old wait_for cancels at timeout; new wait retains the pending accept.

    Both hooks use the real asyncio timeout primitive with timeout zero after
    the accept has started, so old-code failure is an assertion, not a watchdog.
    """

    api = _load_cli()

    async def scenario():
        stop = asyncio.Event()
        handled, cancelled_at_poll, timed_out = [], [], []
        accept, _polls, service = _start(api, monkeypatch, handled.append, stop)

        class TimeoutPolls(_Polls):
            async def wait_for(self, awaitable, *, timeout):
                assert timeout == 0.1
                task = asyncio.ensure_future(awaitable)
                await accept.entered.wait()
                try:
                    return await asyncio.wait_for(task, timeout=0)
                finally:
                    timed_out.append(task)
                    cancelled_at_poll.append(task.cancelled())
                    stop.set()

            async def wait(self, tasks, *, timeout):
                assert timeout == 0.1
                task, = tasks
                await accept.entered.wait()
                result = await asyncio.wait(tasks, timeout=0)
                timed_out.append(task)
                cancelled_at_poll.append(task.cancelled())
                stop.set()
                return result

        monkeypatch.setitem(api, "asyncio", TimeoutPolls())
        try:
            assert await service == []
            assert cancelled_at_poll == [False], "poll timeout cancelled the accept"
            assert accept.registrations == accept.removals == 1
            assert accept.exited.is_set()
            assert timed_out[0].cancelled()  # Shutdown still cancels readiness.
            assert handled == []
        finally:
            await _cancel(service)

    _run(scenario)


def test_pending_accept_survives_polls_and_boundary_completion_responds_once(
    monkeypatch, sockets,
):
    api = _load_cli()
    connection, peer = sockets

    async def scenario():
        handler_entered, release_handler = asyncio.Event(), asyncio.Event()
        handled = []

        async def handler(request, *, deadline):
            handled.append(request["request_id"])
            assert deadline > api["time"].monotonic()
            handler_entered.set()
            await release_handler.wait()
            return {"ok": True, "result": {"served": True}}

        accept, polls, service = _start(api, monkeypatch, handler, asyncio.Event())
        try:
            task, gate = await polls.calls.get()
            await accept.entered.wait()
            assert not task.done()
            gate.set_result((set(), {task}))

            next_task, gate = await polls.calls.get()
            assert next_task is task
            assert accept.registrations == 1 and accept.calls == 0
            assert not task.done()
            await asyncio.get_running_loop().sock_sendall(
                peer, api["encode_frame"](_request()),
            )
            accept.fire((connection, "local-client"))
            # The poll took its timeout snapshot just before accept completed.
            # Resuming that timeout must not abandon the completed connection.
            gate.set_result((set(), {task}))

            completed_task, gate = await polls.calls.get()
            assert completed_task is task and task.done()
            gate.set_result(({task}, set()))
            await handler_entered.wait()
            assert accept.calls == 1
            assert polls.calls.empty()
            assert not service.done()
            release_handler.set()
            responses = await service
            assert handled == ["req-1"]
            assert len(responses) == 1 and responses[0]["ok"] is True
            chunks = []
            while chunk := await asyncio.get_running_loop().sock_recv(peer, 65536):
                chunks.append(chunk)
            lines = b"".join(chunks).splitlines()
            assert len(lines) == 1
            assert json.loads(lines[0]) == responses[0]
            assert connection.close_calls == 1
            assert accept.calls == 1
            assert accept.registrations == accept.removals == 1
        finally:
            await _cancel(service)

    _run(scenario)


@pytest.mark.parametrize("exit_kind", ["stop", "cancel"])
@pytest.mark.parametrize("completed", [False, True], ids=["pending", "completed"])
def test_exit_reaps_pending_or_completed_unconsumed_accept(
    monkeypatch, sockets, exit_kind, completed,
):
    api = _load_cli()
    connection, _peer = sockets

    async def scenario():
        stop = asyncio.Event()
        handled = []
        accept, polls, service = _start(api, monkeypatch, handled.append, stop)
        try:
            task, gate = await polls.calls.get()
            await accept.entered.wait()
            if completed:
                accept.fire((connection, "local-client"))
            if exit_kind == "stop":
                stop.set()
                gate.set_result(({task}, set()) if completed else (set(), {task}))
                assert await service == []
            else:
                service.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await service
            assert task.done()
            assert task.cancelled() is (not completed)
            assert accept.exited.is_set()
            assert accept.calls == int(completed)
            assert accept.registrations == accept.removals == 1
            assert handled == []
            assert connection.close_calls == int(completed)
            if completed:
                assert connection.fileno() == -1
        finally:
            await _cancel(service)

    _run(scenario)


def test_cancel_during_handler_awaits_handler_and_closes_owned_connection(
    monkeypatch, sockets,
):
    api = _load_cli()
    connection, peer = sockets

    async def scenario():
        entered, exited = asyncio.Event(), asyncio.Event()
        release_handler = asyncio.Event()

        async def handler(request):
            entered.set()
            try:
                await release_handler.wait()
            finally:
                exited.set()

        accept, polls, service = _start(api, monkeypatch, handler, asyncio.Event())
        try:
            task, gate = await polls.calls.get()
            await accept.entered.wait()
            await asyncio.get_running_loop().sock_sendall(
                peer, api["encode_frame"](_request()),
            )
            accept.fire((connection, "local-client"))
            gate.set_result(({task}, set()))
            await entered.wait()
            service.cancel()
            with pytest.raises(asyncio.CancelledError):
                await service
            assert exited.is_set()
            assert connection.close_calls == 1
            assert connection.fileno() == -1
            assert accept.calls == 1
            assert polls.calls.empty()
        finally:
            await _cancel(service)

    _run(scenario)


def test_cancel_then_accept_without_yield_closes_unconsumed_socket(
    monkeypatch, sockets,
):
    """The service is cancelled before readiness publishes, without a yield."""

    api = _load_cli()
    connection, _peer = sockets

    async def scenario():
        handled = []
        accept, polls, service = _start(api, monkeypatch, handled.append, asyncio.Event())
        try:
            ready, _gate = await polls.calls.get()
            await accept.entered.wait()
            service.cancel()
            accept.fire((connection, "local-client"))
            # No await between cancellation and publication: cleanup must
            # recover the socket even though the consumer never resumes.
            assert ready.done() and not ready.cancelled()
            with pytest.raises(asyncio.CancelledError):
                await service
            assert connection.close_calls == 1
            assert connection.fileno() == -1
            assert accept.registrations == accept.removals == 1
            assert handled == []
        finally:
            await _cancel(service)

    _run(scenario)


@pytest.mark.parametrize("error_type", [BlockingIOError, InterruptedError])
def test_retryable_accept_error_keeps_exact_reader_armed(monkeypatch, sockets, error_type):
    api = _load_cli()
    connection, _peer = sockets

    async def scenario():
        stop = asyncio.Event()
        accept, polls, service = _start(api, monkeypatch, lambda request: None, stop)
        try:
            ready, gate = await polls.calls.get()
            callback = accept.callback
            accept.fire(error_type())
            assert accept.callback is callback
            assert not ready.done()
            assert accept.removals == 0
            accept.fire((connection, "local-client"))
            stop.set()
            gate.set_result(({ready}, set()))
            assert await service == []
            assert accept.calls == 2
            assert accept.registrations == accept.removals == 1
            assert connection.close_calls == 1
        finally:
            await _cancel(service)

    _run(scenario)


def test_other_accept_oserror_surfaces_as_transport_refusal(monkeypatch):
    api = _load_cli()

    async def scenario():
        accept, polls, service = _start(
            api, monkeypatch, lambda request: None, asyncio.Event(),
        )
        ready, gate = await polls.calls.get()
        accept.fire(OSError("accept failed"))
        gate.set_result(({ready}, set()))
        try:
            with pytest.raises(api["ManagedCLIError"]) as caught:
                await service
            assert caught.value.code == "transport"
            assert accept.registrations == accept.removals == 1
        finally:
            if not service.done():
                await _cancel(service)

    _run(scenario)


def test_stale_readiness_callback_cannot_remove_next_accept_reader(monkeypatch, sockets):
    api = _load_cli()
    connection, _peer = sockets

    async def scenario():
        server = _Accept()
        server.install(monkeypatch)
        first = api["_DaemonAccept"](asyncio.get_running_loop(), server)
        stale_callback = server.callback
        server.fire((connection, "local-client"))
        first.close()
        second = api["_DaemonAccept"](asyncio.get_running_loop(), server)
        try:
            callback = server.callback
            stale_callback()
            first.close()
            assert server.callback is callback
            assert server.calls == 1
            assert server.removals == 1
            assert connection.close_calls == 1
            assert not second.ready.done()
        finally:
            second.close()
        assert server.registrations == server.removals == 2

    _run(scenario)
