"""Load every plugin QML document with Qt 6.12, the Qt Omarchy's Arch packages ship."""

import os
import subprocess
import unittest
from pathlib import Path

from support import ROOT

STUBS = ROOT / "tests" / "qmlstubs"
HARNESS = ROOT / "tests" / "qmlload" / "main.qml"
# Qt prints these when a document is rejected or a binding cannot be applied.
# A clean load still prints the QMLLOAD_OK line from the harness.
_FAILURES = (
    "Cannot override",
    "Property value set multiple times",
    "Cannot assign to non-existent",
    "is not a type",
    "failed to load",
    "Unable to assign",
    "ReferenceError",
    "TypeError",
    "QMLLOAD_FAIL",
    ": error:",
)


def _qml_binary():
    override = os.environ.get("QML_BIN")
    if override:
        return override
    home = Path.home() / "Qt"
    found = sorted(home.glob("6.12.*/gcc_64/bin/qml"))
    if found:
        return str(found[-1])
    return ""


class QmlLoadTests(unittest.TestCase):
    def test_every_plugin_component_loads(self):
        qml = _qml_binary()
        self.assertTrue(
            qml and Path(qml).is_file(),
            "Qt 6.12 qml is required (aqt install-qt linux desktop 6.12.0 linux_gcc_64). "
            "Set QML_BIN if it lives somewhere else.",
        )
        runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp/runtime-qmlload"
        os.makedirs(runtime, exist_ok=True)
        env = os.environ.copy()
        env.update({
            "QT_QPA_PLATFORM": "offscreen",
            "QSG_RHI_BACKEND": "software",
            "QT_QUICK_CONTROLS_STYLE": "Basic",
            "QML_DISABLE_DISK_CACHE": "1",
            "XDG_RUNTIME_DIR": runtime,
        })
        completed = subprocess.run(
            [qml, "-I", str(STUBS), str(HARNESS)],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
            check=False,
        )
        output = completed.stdout
        problems = [needle for needle in _FAILURES if needle in output]
        self.assertIn("6.12", Path(qml).as_posix(), qml)
        self.assertFalse(
            problems or completed.returncode != 0 or "QMLLOAD_OK" not in output,
            f"qml exit {completed.returncode} problems {problems}\n{output}",
        )
        lint = str(Path(qml).with_name("qmllint"))
        self.assertTrue(Path(lint).is_file(), lint)
        for path in sorted(ROOT.glob("*.qml")):
            linted = subprocess.run(
                [lint, "-I", str(STUBS), str(path)],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=60,
                check=False,
            )
            self.assertNotIn(
                "shadows final member",
                linted.stdout,
                f"{path.name}\n{linted.stdout}",
            )
