import re
import unittest
from pathlib import Path

from support import ROOT

_PROPERTY = re.compile(
    r"^(?:(?:default|readonly|required)\s+)*"
    r"(?:property\s+\S+\s+)?"
    r"([A-Za-z_][A-Za-z0-9_.]*)\s*:"
)
_SKIP = {"function", "signal", "import", "pragma", "if", "else", "for", "while", "switch", "return", "case"}


def _strip(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    return re.sub(r'"(?:\\.|[^"\\])*"', '""', text)


def duplicate_bindings(text, source="qml"):
    """Same QML object assigning one property twice.

    Quickshell reports that as "Property value set multiple times" and then
    refuses to instantiate the document. A handler assigned twice is this bug.
    """
    text = _strip(text)
    depth = 0
    function_depth = []
    seen = [{}]
    errors = []
    line_no = 1
    index = 0
    while index < len(text):
        if text[index] == "\n":
            line_no += 1
            index += 1
            continue
        if text.startswith("function", index) and (index == 0 or not (text[index - 1].isalnum() or text[index - 1] == "_")):
            function_depth.append(None)
            index += len("function")
            continue
        if text[index] == "{":
            if function_depth and function_depth[-1] is None:
                function_depth[-1] = depth + 1
            depth += 1
            seen.append({})
            index += 1
            continue
        if text[index] == "}":
            if function_depth and function_depth[-1] == depth:
                function_depth.pop()
            if seen:
                seen.pop()
            depth = max(0, depth - 1)
            index += 1
            continue
        if function_depth:
            index += 1
            continue
        start = index
        while index < len(text) and text[index] not in "{}\n":
            index += 1
        fragment = text[start:index].strip()
        match = _PROPERTY.match(fragment)
        if match and match.group(1).split(".")[0] not in _SKIP and seen:
            name = match.group(1)
            bucket = seen[-1]
            if name in bucket:
                errors.append(
                    f"{source}:{line_no} sets {name} again (first at line {bucket[name]})"
                )
            else:
                bucket[name] = line_no
        continue
    return errors


class QmlBindingTests(unittest.TestCase):
    def test_a_repeated_handler_is_reported(self):
        text = "Item {\n  onEditorServiceChanged: a()\n  onEditorServiceChanged: b()\n}\n"
        errors = duplicate_bindings(text)
        self.assertEqual(len(errors), 1)
        self.assertIn("onEditorServiceChanged", errors[0])

    def test_nested_objects_may_reuse_a_name(self):
        text = "Item {\n  onClicked: a()\n  Item {\n    onClicked: b()\n  }\n}\n"
        self.assertEqual(duplicate_bindings(text), [])

    def test_plugin_qml_sets_each_property_once(self):
        problems = []
        for path in sorted(ROOT.glob("*.qml")):
            problems.extend(duplicate_bindings(path.read_text(encoding="utf-8"), path.name))
        self.assertEqual(problems, [])

    def test_plugin_qml_does_not_redeclare_final_item_properties(self):
        # QQuickItem properties marked FINAL in Qt 6.12 (Arch qt6-base, which
        # Omarchy ships). Declaring one of these on an Item, Control, or
        # ScrollView is the load error "Cannot override FINAL property".
        final = {
            "parent", "x", "y", "z", "width", "height", "opacity", "visible",
            "childrenRect", "anchors", "left", "right", "horizontalCenter",
            "top", "bottom", "verticalCenter", "baseline", "focus",
            "activeFocus", "activeFocusOnTab", "transform", "layer",
            "data", "children", "resources",
        }
        declared = re.compile(
            r"^\s*(?:default\s+|readonly\s+|required\s+)*property\s+\S+\s+([A-Za-z_]\w*)\b",
            re.M,
        )
        problems = []
        for path in sorted(ROOT.glob("*.qml")):
            text = _strip(path.read_text(encoding="utf-8"))
            for match in declared.finditer(text):
                name = match.group(1)
                if name in final:
                    line = text.count("\n", 0, match.start()) + 1
                    problems.append(f"{path.name}:{line} redeclares FINAL property {name}")
        self.assertEqual(problems, [])
