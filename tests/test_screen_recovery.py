"""Regression tests for the Turing screen freezing with nothing in the log.

The screen would stop updating after the app had been running a while — chat
kept being translated and logged, but the panel was stuck on an old frame and
no error was ever raised. Two hardware realities cause that, and neither shows
up as an exception:

1. ``LcdComm.WriteLine`` catches ``SerialTimeoutException`` and only logs
   "(Write line) Too fast! Slow down!". On Windows that exception means the
   write was *partial*, so the rest of a bitmap chunk is lost. The Turing
   protocol is a byte stream (a DISPLAY_BITMAP header followed by exactly
   width*height*2 bytes), so the panel then waits forever for the missing
   bytes and eats every later frame as payload — a permanent freeze.
2. The port is opened with hardware flow control, so a screen that stops
   asserting CTS blocks ``write()`` indefinitely and the display thread never
   comes back.

The display loop also used to re-send an identical 300 KB frame five times a
second, which is what kept the link saturated enough to hit (1) in the first
place.
"""

from __future__ import annotations

import sys
import threading
import time
import types

import pytest
from PIL import Image, ImageDraw

from display.screen_controller import ScreenController
from display.turing_display import DisplayLinkError, TuringDisplay


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeSerialTimeout(Exception):
    """Stands in for ``serial.SerialTimeoutException`` (a partial write)."""


class _FakeSerial:
    """Minimal pyserial stand-in that records what the library wrote."""

    def __init__(self):
        self.written = bytearray()
        self.raise_on_write = None
        self.short_write = False
        self.cancelled = 0
        self.closed = False

    def write(self, data):
        if self.raise_on_write is not None:
            raise self.raise_on_write
        if self.short_write:
            self.written.extend(data[:1])
            return 1
        self.written.extend(data)
        return len(data)

    def cancel_write(self):
        self.cancelled += 1

    def close(self):
        self.closed = True


class _FakeScreen:
    """Stand-in for ``LcdCommRevA`` that writes frames through the serial handle.

    ``DisplayPILImage`` mirrors the upstream behaviour that hides the failure:
    a write timeout is swallowed and the remaining chunks go out anyway.
    """

    def __init__(self):
        self.lcd_serial = _FakeSerial()
        self.frames = 0
        self.closed = 0

    def DisplayPILImage(self, image):  # noqa: N802 - matches the library's name
        self.frames += 1
        payload = image.tobytes()
        for start in range(0, len(payload), 4096):
            try:
                self.lcd_serial.write(payload[start:start + 4096])
            except _FakeSerialTimeout:
                pass  # "(Write line) Too fast! Slow down!"

    def closeSerial(self):  # noqa: N802 - matches the library's name
        self.closed += 1


def _connected_display() -> TuringDisplay:
    """A TuringDisplay wired to a fake screen, as if ``connect()`` had run."""
    display = TuringDisplay(port="COM_TEST")
    display.screen = _FakeScreen()
    display._buffer = Image.new("RGB", (display.width, display.height), (0, 0, 0))
    display._draw = ImageDraw.Draw(display._buffer)
    display._is_connected = True
    display._install_serial_guards()
    return display


class _FakeDisplay:
    """Display stand-in for the controller's loop and watchdog."""

    def __init__(self):
        self.is_connected = True
        self.render_started_at = None
        self.width = 480
        self.renders = []
        self.fault_once = False
        self.reconnects = 0
        self.reconnect_result = True
        self.aborts = 0
        self._image = Image.new("RGB", (480, 320), (0, 0, 0))
        self.draw = ImageDraw.Draw(self._image)
        self.font = None
        self.font_bold = None

    def clear(self):
        pass

    def disconnect(self):
        self.is_connected = False

    def render(self, force=False):
        self.renders.append(force)
        if self.fault_once:
            self.fault_once = False
            raise DisplayLinkError("short write (1/4096 bytes)")
        return True

    def reconnect(self):
        self.reconnects += 1
        return self.reconnect_result

    def abort_write(self):
        self.aborts += 1
        return True

    def text_width(self, text, font=None):
        return 10 * len(text)

    def wrap_text(self, text, max_width, font=None):
        return [text]


def _controller(display=None) -> ScreenController:
    controller = ScreenController(port="COM_TEST", poll_interval=0.01, stall_timeout=0.05)
    controller.watchdog_interval = 0.01
    controller.display = display if display is not None else _FakeDisplay()
    return controller


def _wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


# ---------------------------------------------------------------------------
# Unchanged frames must not be re-sent
# ---------------------------------------------------------------------------

def test_unchanged_frame_is_not_resent():
    display = _connected_display()

    assert display.render() is True, "the first frame always has to go out"
    assert display.render() is False, (
        "an unchanged buffer must not be pushed again — re-sending a ~300 KB "
        "frame five times a second is what saturates the link"
    )
    assert display.screen.frames == 1


def test_changed_frame_is_sent():
    display = _connected_display()
    display.render()

    display.draw.rectangle([0, 0, 10, 10], fill=(255, 0, 0))

    assert display.render() is True
    assert display.screen.frames == 2


def test_force_resends_identical_frame():
    """After a reconnect the panel is blank, so the same buffer must go out."""
    display = _connected_display()
    display.render()

    assert display.render(force=True) is True
    assert display.screen.frames == 2


# ---------------------------------------------------------------------------
# Dropped bytes must stop being silent
# ---------------------------------------------------------------------------

def test_swallowed_write_timeout_becomes_a_link_error():
    display = _connected_display()
    display.screen.lcd_serial.raise_on_write = _FakeSerialTimeout("Write timeout")

    with pytest.raises(DisplayLinkError):
        display.render()


def test_short_write_becomes_a_link_error():
    """A write cancelled from another thread returns short instead of raising."""
    display = _connected_display()
    display.screen.lcd_serial.short_write = True

    with pytest.raises(DisplayLinkError):
        display.render()


def test_failed_frame_is_not_remembered_as_displayed():
    display = _connected_display()
    display.screen.lcd_serial.raise_on_write = _FakeSerialTimeout("Write timeout")
    with pytest.raises(DisplayLinkError):
        display.render()

    display.screen.lcd_serial.raise_on_write = None

    assert display.render() is True, (
        "the frame never made it to the panel, so the identical buffer must "
        "still be sent once the link is back"
    )


def test_abort_write_cancels_and_records_the_fault():
    display = _connected_display()

    assert display.abort_write() is True
    assert display.screen.lcd_serial.cancelled == 1
    assert display.write_fault


def test_reconnect_closes_the_old_port():
    display = _connected_display()
    screen = display.screen
    display.render()

    # connect() needs the real library, which isn't available here.
    display.connect = lambda: False
    assert display.reconnect() is False
    assert screen.closed == 1
    assert display._last_frame is None


# ---------------------------------------------------------------------------
# The library must not be able to kill the process
# ---------------------------------------------------------------------------

def test_guarded_open_serial_raises_instead_of_exiting(monkeypatch):
    """``LcdComm.openSerial`` calls ``sys.exit(0)``/``os._exit(0)`` on failure.

    From a worker thread that either kills the app outright or ends the
    display thread with nothing in the log.
    """
    class _Unopenable:
        def __init__(self, *args, **kwargs):
            raise OSError("could not open port COM_TEST")

    stub = types.ModuleType("serial")
    stub.Serial = _Unopenable
    monkeypatch.setitem(sys.modules, "serial", stub)

    display = TuringDisplay(port="COM_TEST")
    screen = types.SimpleNamespace(com_port="COM_TEST", lcd_serial=None)

    with pytest.raises(RuntimeError):
        display._open_serial_port(screen, attempts=2, retry_delay=0)


def test_port_open_is_retried_on_every_attempt():
    opens = []

    class _Unopenable:
        def __init__(self, *args, **kwargs):
            opens.append(args[0])
            raise OSError("could not open port")

    stub = types.ModuleType("serial")
    stub.Serial = _Unopenable
    display = TuringDisplay(port="COM_TEST")
    screen = types.SimpleNamespace(com_port="COM_TEST", lcd_serial=None)

    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(sys.modules, "serial", stub)
        with pytest.raises(RuntimeError):
            display._open_serial_port(screen, attempts=3, retry_delay=0)

    assert opens == ["COM_TEST"] * 3, "a screen that is still re-enumerating needs every retry"


def test_guarded_screen_class_overrides_open_serial():
    exits = []

    class _Suicidal:
        def __init__(self, com_port=None, display_width=0, display_height=0):
            self.com_port = com_port
            self.lcd_serial = None
            self.openSerial()

        def openSerial(self):  # noqa: N802 - matches the library's name
            exits.append("sys.exit(0)")
            raise SystemExit(0)

    display = TuringDisplay(port="COM_TEST")
    opened = []
    display._open_serial_port = lambda screen, **kwargs: opened.append(screen)

    guarded = display._guarded_screen_class(_Suicidal)
    instance = guarded(com_port="COM_TEST", display_width=480, display_height=320)

    assert exits == [], "the constructor must not reach the library's exit path"
    assert opened == [instance]


# ---------------------------------------------------------------------------
# Whole connect -> fault -> reconnect cycle against a stand-in library
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_library(monkeypatch):
    """Stand in for turing-smart-screen-python and pyserial.

    The real library is cloned by ``scripts/dev_setup.py`` and needs the
    hardware, so the parts :meth:`TuringDisplay.connect` drives are faked here:
    a screen class whose constructor opens the port (the call the guard has to
    intercept) and a serial handle that can be told to fail.
    """
    import display.turing_display as turing_display

    serials = []

    class _Serial:
        def __new__(cls, port, baud, timeout=None, rtscts=False):
            handle = _FakeSerial()
            handle.port = port
            serials.append(handle)
            return handle

    class _LcdCommRevA:
        def __init__(self, com_port=None, display_width=0, display_height=0):
            self.com_port = com_port
            self.lcd_serial = None
            self.resets = 0
            self.frames = 0
            self.openSerial()

        def openSerial(self):  # noqa: N802 - matches the library's name
            raise AssertionError("the library's own openSerial must never run")

        def closeSerial(self):  # noqa: N802 - matches the library's name
            if self.lcd_serial is not None:
                self.lcd_serial.close()

        def Reset(self):  # noqa: N802 - matches the library's name
            self.resets += 1
            self.closeSerial()
            self.openSerial()

        def InitializeComm(self):  # noqa: N802 - matches the library's name
            pass

        def SetBrightness(self, level=0):  # noqa: N802 - matches the library's name
            pass

        def SetOrientation(self, orientation=None):  # noqa: N802 - matches the library's name
            pass

        def DisplayPILImage(self, image):  # noqa: N802 - matches the library's name
            self.frames += 1
            payload = image.tobytes()
            for start in range(0, len(payload), 4096):
                try:
                    self.lcd_serial.write(payload[start:start + 4096])
                except _FakeSerialTimeout:
                    pass  # "(Write line) Too fast! Slow down!"

    stub_serial = types.ModuleType("serial")
    stub_serial.Serial = _Serial
    monkeypatch.setitem(sys.modules, "serial", stub_serial)
    monkeypatch.setattr(
        turing_display, "time", types.SimpleNamespace(sleep=lambda s: None, monotonic=time.monotonic)
    )
    monkeypatch.setattr(
        TuringDisplay,
        "_import_screen_class",
        lambda self: (_LcdCommRevA, types.SimpleNamespace(LANDSCAPE=1, PORTRAIT=0)),
    )
    return types.SimpleNamespace(serials=serials)


def test_connect_render_fault_and_reconnect(fake_library):
    display = TuringDisplay(port="COM_TEST")

    assert display.connect() is True
    assert display.is_connected
    assert len(fake_library.serials) == 2, "the constructor opens the port, Reset() reopens it"

    display.clear()
    display.draw.rectangle([0, 0, 20, 20], fill=(0, 128, 255))
    assert display.render() is True
    frames_before = display.screen.frames

    # The screen stops taking data mid-frame, exactly as a stalled USB link does.
    fake_library.serials[-1].raise_on_write = _FakeSerialTimeout("Write timeout")
    display.draw.rectangle([0, 0, 20, 20], fill=(255, 0, 0))
    with pytest.raises(DisplayLinkError):
        display.render()

    assert display.reconnect() is True
    assert display.is_connected
    assert display.screen.frames == 0, "a fresh screen object, so the panel is blank"

    # The buffer is recreated by connect(), so redraw and push.
    display.clear()
    display.draw.rectangle([0, 0, 20, 20], fill=(255, 0, 0))
    assert display.render() is True
    assert display.screen.frames == 1
    assert frames_before >= 1


def test_connect_reports_failure_instead_of_exiting(fake_library, monkeypatch):
    """A missing screen must leave the app running and simply return False."""
    def _explode(port, baud, timeout=None, rtscts=False):
        raise OSError("could not open port COM_TEST")

    monkeypatch.setattr(sys.modules["serial"], "Serial", _explode)
    display = TuringDisplay(port="COM_TEST")

    assert display.connect() is False
    assert display.is_connected is False


# ---------------------------------------------------------------------------
# Controller + display together: what the idle link actually carries
# ---------------------------------------------------------------------------

def test_idle_controller_stops_writing_to_the_screen():
    """The bug in one assertion: an idle screen used to be redrawn 5x a second."""
    display = _connected_display()
    display._load_fonts()
    controller = _controller(display)

    controller.running = True
    thread = threading.Thread(target=controller._display_loop, daemon=True)
    thread.start()
    try:
        time.sleep(0.2)  # ~20 loop iterations at the test poll interval
        assert display.screen.frames == 1, (
            "nothing changed on screen, so exactly one frame (the initial "
            "blank one) should have reached the hardware"
        )

        controller.display_message(player="Alice", original="hola", translated="hi")

        assert _wait_until(lambda: display.screen.frames == 2)
        time.sleep(0.1)
        assert display.screen.frames == 2, "the new message must be sent once, not repeatedly"
    finally:
        controller.running = False
        controller._stop_event.set()
        thread.join(timeout=2)


def test_idle_screen_is_repainted_periodically():
    """Dropping the constant refresh must not mean never repainting.

    A panel can lose its picture without the serial link noticing, so an
    unchanged screen is still pushed once a minute (here, much faster).
    """
    display = _FakeDisplay()

    def render(force=False):
        display.renders.append(force)
        return force  # nothing changed: only a forced frame goes out

    display.render = render
    controller = _controller(display)
    controller.refresh_interval = 0.05

    controller.running = True
    thread = threading.Thread(target=controller._display_loop, daemon=True)
    thread.start()
    try:
        assert _wait_until(lambda: display.renders.count(True) >= 2)
    finally:
        controller.running = False
        controller._stop_event.set()
        thread.join(timeout=2)

    assert display.renders.count(False) > 0, "most cycles must still skip the hardware"


# ---------------------------------------------------------------------------
# Controller: recovery
# ---------------------------------------------------------------------------

def test_display_loop_reconnects_after_a_link_error():
    display = _FakeDisplay()
    display.fault_once = True
    controller = _controller(display)
    statuses = []
    controller._on_status = lambda state, detail="": statuses.append(state)

    controller.running = True
    thread = threading.Thread(target=controller._display_loop, daemon=True)
    thread.start()
    try:
        assert _wait_until(lambda: display.reconnects >= 1), "dropped bytes must trigger a reconnect"
        assert _wait_until(lambda: True in display.renders), "the panel is blank after a reset — redraw it"
    finally:
        controller.running = False
        controller._stop_event.set()
        thread.join(timeout=2)

    assert "reconnecting" in statuses
    assert "connected" in statuses


def test_failed_reconnect_is_retried():
    display = _FakeDisplay()
    display.fault_once = True
    display.reconnect_result = False
    controller = _controller(display)
    controller.RECONNECT_BACKOFF = (0, 0)

    controller.running = True
    thread = threading.Thread(target=controller._display_loop, daemon=True)
    thread.start()
    try:
        assert _wait_until(lambda: display.reconnects >= 2)
    finally:
        controller.running = False
        controller._stop_event.set()
        thread.join(timeout=2)

    assert controller._needs_reconnect is True


def test_display_loop_survives_a_library_exit():
    """``SystemExit`` in a thread is swallowed by ``threading`` — no traceback."""
    display = _FakeDisplay()
    calls = []

    def render(force=False):
        calls.append(force)
        if len(calls) == 1:
            raise SystemExit(0)
        return True

    display.render = render
    controller = _controller(display)

    controller.running = True
    thread = threading.Thread(target=controller._display_loop, daemon=True)
    thread.start()
    try:
        assert _wait_until(lambda: display.reconnects >= 1)
        assert thread.is_alive(), "the display thread must not die silently"
    finally:
        controller.running = False
        controller._stop_event.set()
        thread.join(timeout=2)


def test_watchdog_breaks_a_stuck_write():
    display = _FakeDisplay()
    controller = _controller(display)
    controller.running = True
    # A write that blocked forever: the frame started long ago and never ended.
    display.render_started_at = time.monotonic() - 60

    thread = threading.Thread(target=controller._watchdog_loop, daemon=True)
    thread.start()
    try:
        assert _wait_until(lambda: display.aborts >= 1), "a stuck write must be aborted"
        assert controller._needs_reconnect is True
        # The same stuck frame must not be aborted over and over.
        time.sleep(0.1)
        assert display.aborts == 1
    finally:
        controller.running = False
        controller._stop_event.set()
        thread.join(timeout=2)


def test_watchdog_leaves_a_healthy_write_alone():
    display = _FakeDisplay()
    controller = _controller(display)
    controller.running = True
    display.render_started_at = time.monotonic()

    thread = threading.Thread(target=controller._watchdog_loop, daemon=True)
    thread.start()
    try:
        time.sleep(0.03)
        assert display.aborts == 0
        assert controller._needs_reconnect is False
    finally:
        controller.running = False
        controller._stop_event.set()
        thread.join(timeout=2)


def test_watchdog_restarts_a_dead_display_thread():
    display = _FakeDisplay()
    controller = _controller(display)
    controller.running = True
    dead = threading.Thread(target=lambda: None)
    dead.start()
    dead.join()
    controller.display_thread = dead

    thread = threading.Thread(target=controller._watchdog_loop, daemon=True)
    thread.start()
    try:
        assert _wait_until(
            lambda: controller.display_thread is not dead and controller.display_thread.is_alive()
        )
    finally:
        controller.running = False
        controller._stop_event.set()
        thread.join(timeout=2)
        if controller.display_thread is not None:
            controller.display_thread.join(timeout=2)


def test_watchdog_gives_up_after_repeated_thread_deaths():
    display = _FakeDisplay()
    controller = _controller(display)
    controller.running = True
    controller._thread_restarts = controller.MAX_THREAD_RESTARTS
    dead = threading.Thread(target=lambda: None)
    dead.start()
    dead.join()
    controller.display_thread = dead
    statuses = []
    controller._on_status = lambda state, detail="": statuses.append((state, detail))

    thread = threading.Thread(target=controller._watchdog_loop, daemon=True)
    thread.start()
    thread.join(timeout=2)

    assert not thread.is_alive(), "the watchdog must stop instead of restarting forever"
    assert controller.display_thread is dead
    assert statuses and statuses[-1][0] == "disconnected"


def test_disconnect_does_not_hang_on_a_stuck_write():
    display = _FakeDisplay()
    release = threading.Event()

    def render(force=False):
        display.render_started_at = time.monotonic()
        release.wait(5)
        display.render_started_at = None
        return True

    def abort_write():
        display.aborts += 1
        release.set()
        return True

    display.render = render
    display.abort_write = abort_write
    controller = _controller(display)
    controller.running = True
    controller._start_display_thread()

    assert _wait_until(lambda: display.render_started_at is not None)
    started = time.monotonic()
    controller.disconnect()

    assert time.monotonic() - started < 5, "disconnect must break the stuck write, not wait it out"
    assert display.aborts == 1
