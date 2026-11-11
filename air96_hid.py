"""Find the Air96 VIA hidraw node and exchange 32-byte reports.

Discovery reads sysfs. It does not open the device until a transport is
constructed. The raw HID interface is usage page ``0xFF60`` usage ``0x61``.
The boot keyboard interface is ignored. Writes are 32 bytes with no report
ID; if the kernel rejects that, one retry prefixes a zero report ID.
"""

import errno
import os
from pathlib import Path
import select
import time

from air96_layout import PRODUCT_IDS, VENDOR_ID, VIA_USAGE, VIA_USAGE_PAGE
from air96_protocol import PACKET_SIZE

HIDRAW_ROOT = Path("/sys/class/hidraw")


class HidError(RuntimeError):
    pass


def application_usages(descriptor):
    """Return (usage_page, usage) for each application collection."""
    found = []
    index = 0
    page = 0
    usage = 0
    data = bytes(descriptor)
    while index < len(data):
        header = data[index]
        size = header & 0x03
        if size == 3:
            size = 4
        kind = (header >> 2) & 0x03
        tag = (header >> 4) & 0x0F
        payload = data[index + 1:index + 1 + size]
        index += 1 + size
        value = int.from_bytes(payload, "little") if payload else 0
        if kind == 1 and tag == 0:  # global usage page
            page = value
        elif kind == 2 and tag == 0:  # local usage
            usage = value
        elif kind == 0 and tag == 0xA and value == 1:  # application collection
            found.append((page, usage))
            usage = 0
    return found


def _uevent(text):
    fields = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return fields


def _hid_id(fields):
    raw = fields.get("HID_ID", "")
    parts = raw.split(":")
    if len(parts) != 3:
        return None
    try:
        return int(parts[1], 16), int(parts[2], 16)
    except ValueError:
        return None


def _interface(device_path):
    for part in Path(device_path).parts:
        if ":" in part and part.rsplit(":", 1)[-1].count(".") == 1:
            try:
                return int(part.rsplit(".", 1)[-1])
            except ValueError:
                return None
    return None


def find_devices(root=None):
    base = Path(root) if root else HIDRAW_ROOT
    if not base.is_dir():
        return []
    found = []
    for node in sorted(base.glob("hidraw*")):
        device = node / "device"
        try:
            fields = _uevent((device / "uevent").read_text(errors="replace"))
            descriptor = (device / "report_descriptor").read_bytes()
        except OSError:
            continue
        parsed = _hid_id(fields)
        if not parsed or parsed[0] != VENDOR_ID or parsed[1] not in PRODUCT_IDS:
            continue
        usages = application_usages(descriptor)
        if (VIA_USAGE_PAGE, VIA_USAGE) not in usages:
            continue
        path = Path("/dev") / node.name
        found.append({
            "path": str(path),
            "vid": parsed[0],
            "pid": parsed[1],
            "name": fields.get("HID_NAME", ""),
            "iface": _interface(os.path.realpath(device)),
            "usages": usages,
        })
    return found


def find_event_nodes(root=None):
    """Input event nodes for modifier listening. Name match covers a dongle that still says Air96."""
    base = Path(root) if root else Path("/sys/class/input")
    if not base.is_dir():
        return []
    found = []
    for node in sorted(base.glob("event*")):
        device = node / "device"
        try:
            vendor = int((device / "id" / "vendor").read_text().strip(), 16)
            product = int((device / "id" / "product").read_text().strip(), 16)
            name = (device / "name").read_text(errors="replace").strip()
        except (OSError, ValueError):
            continue
        lowered = name.lower()
        id_match = vendor == VENDOR_ID and product in PRODUCT_IDS
        name_match = "air96" in lowered
        if not id_match and not name_match:
            continue
        found.append({"path": str(Path("/dev/input") / node.name), "name": name, "vid": vendor, "pid": product})
    return found


class HidTransport:
    def __init__(self, path, timeout=0.4):
        self.path = path
        self.timeout = timeout
        self.fd = os.open(path, os.O_RDWR | os.O_CLOEXEC)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def transact(self, payload):
        data = bytes(payload)
        if len(data) != PACKET_SIZE:
            raise HidError("VIA report must be 32 bytes")
        self._write(data)
        return self._read()

    def _write(self, data):
        try:
            written = os.write(self.fd, data)
        except OSError as exc:
            if exc.errno != errno.EINVAL:
                raise HidError(f"HID write failed: {exc.strerror}") from exc
            written = os.write(self.fd, b"\x00" + data)
        if written < PACKET_SIZE:
            raise HidError("Short HID write")

    def _read(self):
        ready, _, _ = select.select([self.fd], [], [], self.timeout)
        if not ready:
            raise HidError("Keyboard did not answer")
        data = os.read(self.fd, PACKET_SIZE + 1)
        if len(data) == PACKET_SIZE + 1 and data[0] == 0:
            data = data[1:]
        if len(data) < PACKET_SIZE:
            raise HidError("Short HID response")
        return data[:PACKET_SIZE]


class EvdevModifiers:
    """Track Shift/Ctrl/Alt/Super. Other key codes are discarded and not stored."""

    EVENT_SIZE = 24
    EV_KEY = 1
    CODES = {
        29: "ctrl",
        97: "ctrl",
        42: "shift",
        54: "shift",
        56: "alt",
        100: "alt",
        125: "super",
        126: "super",
    }

    def __init__(self):
        self.mask = 0
        self._down = {name: 0 for name in ("ctrl", "shift", "alt", "super")}
        self.fds = []
        self.permission = ""

    def open_nodes(self, nodes):
        self.close()
        errors = []
        for node in nodes:
            try:
                fd = os.open(node["path"], os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
            except OSError as exc:
                errors.append(exc.strerror or str(exc))
                continue
            self.fds.append(fd)
        if nodes and not self.fds:
            self.permission = "Cannot read the keyboard's input device. Install the optional modifier udev rule or join the input group, then replug. " + (errors[0] if errors else "")
        elif not nodes:
            self.permission = "No Air96 input device found. A 2.4G dongle with a generic name is not matched."
        else:
            self.permission = ""
        return self.fds

    def close(self):
        for fd in self.fds:
            os.close(fd)
        self.fds = []
        self.mask = 0
        self._down = {name: 0 for name in self._down}

    def drain(self):
        changed = False
        for fd in list(self.fds):
            while True:
                try:
                    data = os.read(fd, self.EVENT_SIZE * 64)
                except BlockingIOError:
                    break
                except OSError:
                    self.fds.remove(fd)
                    os.close(fd)
                    break
                if not data:
                    break
                for offset in range(0, len(data) - self.EVENT_SIZE + 1, self.EVENT_SIZE):
                    event_type = int.from_bytes(data[offset + 16:offset + 18], "little")
                    code = int.from_bytes(data[offset + 18:offset + 20], "little")
                    value = int.from_bytes(data[offset + 20:offset + 24], "little", signed=True)
                    if event_type != self.EV_KEY or value == 2:
                        continue
                    name = self.CODES.get(code)
                    if name is None:
                        continue
                    self._down[name] += 1 if value == 1 else -1 if value == 0 else 0
                    self._down[name] = max(0, self._down[name])
                    changed = True
        bits = {"shift": 1, "ctrl": 4, "alt": 8, "super": 64}
        self.mask = 0
        for name, bit in bits.items():
            if self._down[name]:
                self.mask |= bit
        return changed


def monotonic():
    return time.monotonic()
