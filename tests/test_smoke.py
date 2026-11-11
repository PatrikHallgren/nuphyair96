import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from contextlib import redirect_stdout
from unittest.mock import patch

import support  # noqa: F401
from air96_backend import Backend
from air96_ha import send, service_request, turn_on_payload
from air96_hid import EvdevModifiers
from air96_worker import HyprEvents, ThemeWatch, serve


def key_event(code, value):
    data = bytearray(24)
    data[16:18] = (1).to_bytes(2, "little")
    data[18:20] = code.to_bytes(2, "little")
    data[20:24] = value.to_bytes(4, "little", signed=True)
    return bytes(data)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.seen = {
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "body": body,
        }
        payload = b"[]"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        return


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def backend(self):
        theme = self.root / "theme"
        theme.mkdir(exist_ok=True)
        return Backend(
            config_path=self.root / "config.json",
            state_dir=self.root / "state",
            theme_path=theme,
            profiles_dir=self.root / "profiles",
            environ={},
        )

    def test_theme_watch_sees_keyboard_rgb(self):
        theme = self.root / "theme"
        theme.mkdir()
        watcher = ThemeWatch(theme)
        try:
            (theme / "keyboard.rgb").write_text("ff00ff\n")
            changed = set()
            for _ in range(5):
                changed |= watcher.drain()
                if "theme" in changed:
                    break
            self.assertIn("theme", changed)
        finally:
            watcher.close()

    def test_hypr_socket_updates_the_focused_window(self):
        path = self.root / "socket2.sock"
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(path))
        server.listen(1)
        server.settimeout(2)
        events = HyprEvents()
        try:
            with patch("air96_worker.hypr_socket_path", return_value=path):
                self.assertTrue(events.connect())
            client, _address = server.accept()
            client.sendall(b"activewindow>>firefox,Hello, world\nsubmap>>resize\nconfigreloaded>>\nignored\n")
            client.close()
            backend = self.backend()
            with patch("air96_worker.refresh_binds", return_value=True) as refresh:
                self.assertTrue(events.drain(backend))
            refresh.assert_called_once()
            self.assertEqual(backend.window_class, "firefox")
            self.assertEqual(backend.window_title, "Hello, world")
            self.assertEqual(backend.submap, "resize")
        finally:
            events.close()
            server.close()

    def test_evdev_open_reads_modifiers_and_reports_a_missing_node(self):
        fifo = self.root / "event0"
        os.mkfifo(fifo)
        listener = EvdevModifiers()
        writer = None
        try:
            opened = listener.open_nodes([{"path": str(fifo), "name": "NuPhy Air96 V2", "vid": 0x19F5, "pid": 0x3265}])
            self.assertEqual(len(opened), 1)
            self.assertEqual(listener.permission, "")
            writer = os.open(fifo, os.O_WRONLY)
            os.write(writer, key_event(16, 1) + key_event(125, 1))
            self.assertTrue(listener.drain())
            self.assertEqual(listener.mask, 64)
        finally:
            listener.close()
            if writer is not None:
                os.close(writer)
        missing = EvdevModifiers()
        missing.open_nodes([{"path": str(self.root / "missing-event")}])
        self.assertEqual(missing.fds, [])
        self.assertIn("Cannot read", missing.permission)

    def test_home_assistant_client_posts_to_a_local_server(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            payload = turn_on_payload(["light.desk"], "#7aa2f7", 40)
            prepared = service_request(f"http://127.0.0.1:{port}", "long-lived-token", payload)
            result = send(prepared, timeout=2)
        finally:
            thread.join(timeout=2)
            server.server_close()
        self.assertEqual(result["status"], 200)
        self.assertEqual(server.seen["path"], "/api/services/light/turn_on")
        self.assertEqual(server.seen["authorization"], "Bearer long-lived-token")
        body = json.loads(server.seen["body"])
        self.assertEqual(body["entity_id"], ["light.desk"])
        self.assertNotIn("long-lived-token", server.seen["body"].decode())

    def test_worker_serves_one_request_and_exits(self):
        read_fd, write_fd = os.pipe()
        os.write(
            write_fd,
            b"\n".join(
                [
                    b"not-json",
                    b'{"id": 3, "action": "status"}',
                    b'{"id": 4, "action": "nope"}',
                    b'{"id": 5, "action": "ha-push"}',
                ]
            )
            + b"\n",
        )
        os.close(write_fd)
        stdin = os.fdopen(read_fd, "rb", buffering=0)
        stdout = StringIO()
        error = []

        def run():
            try:
                with patch("air96_worker.find_devices", return_value=[]), patch(
                    "air96_worker.refresh_binds", return_value=False
                ), patch("air96_worker.refresh_window"), redirect_stdout(stdout):
                    serve(backend=self.backend(), stdin=stdin)
            except Exception as exc:  # noqa: BLE001 - the assertion below reports it
                error.append(exc)

        thread = threading.Thread(target=run)
        thread.start()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive(), "worker did not exit after stdin closed")
        self.assertEqual(error, [])
        lines = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertGreaterEqual(len(lines), 4)
        self.assertTrue(any(item.get("protocolError") for item in lines))
        status = next(item for item in lines if item.get("requestId") == 3)
        self.assertIn("layout", status)
        self.assertEqual(status["setupIssue"], "not-found")
        unknown = next(item for item in lines if item.get("requestId") == 4)
        self.assertTrue(unknown.get("protocolError"))
        self.assertIn("Invalid worker request", unknown["error"])
        pushed = next(item for item in lines if item.get("requestId") == 5)
        self.assertIn("token is missing", pushed["error"])
        self.assertNotIn('"token":', stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
