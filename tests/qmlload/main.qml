import QtQuick
import QtQuick.Controls
import "../../" as Air

ApplicationWindow {
  id: window
  width: 900
  height: 700
  visible: true
  color: "#101315"

  QtObject {
    id: airService
    property var snapshot: ({
      keyboardName: "NuPhy Air96 V2",
      layout: [{id: "esc", x: 0, y: 0, w: 1, h: 1, label: "Esc", row: 0, col: 0, led: 0}],
      layers: [{id: 2, name: "Win"}],
      lighting: {effect: 1, brightness: 180, speed: 128, hex: "#ffffff", follow_theme: false, solid_when_following: true},
      homeAssistant: {url: "", entities: [], enabled: false, syncBrightness: false, onlyWhenOn: true, hex: "#ffffff", brightness: 180, followTheme: true, tokenEnv: "HA_TOKEN", configured: false},
      screensaver: {enabled: false},
      theme: "#ffffff"
    })
    property var keymap: ({known: false, keys: ({}), codes: [{name: "A", short: "A", value: 4}]})
    property var drafts: ({})
    property var changes: []
    property bool actionBusy: false
    property bool ready: true
    property string lastError: ""
    function request(action, config) { return false }
    function stage(layer, row, col, value, original) {}
    function discard() {}
  }

  QtObject {
    id: barStub
    property var shell: shellStub
    property bool vertical: false
    property int barSize: 26
    property string position: "top"
    property color barForeground: "#cacccc"
    property string fontFamily: "monospace"
    function moduleWidgets(name) { return [widget] }
    function requestPopout(key) {}
  }

  QtObject {
    id: shellStub
    function serviceFor(name) { return airService }
  }

  Air.PlainText { id: plain; text: "Air96" }
  Air.ColorPicker { id: picker; width: 240 }
  Air.KeyboardView {
    id: keys
    width: 400
    layout: airService.snapshot.layout
    labels: ({esc: "Esc"})
    selected: "esc"
  }
  Air.LightingSlider { id: slider; width: 240; height: 28; value: 10 }
  Air.Service { id: service }
  Air.Editor {
    id: editor
    width: 760
    height: 420
    service: airService
  }
  Air.Air96Panel {
    id: panel
    width: 760
    height: 420
    service: airService
    anchorItem: plain
    bar: barStub
  }
  Air.Widget {
    id: widget
    width: 80
    height: 30
    bar: barStub
  }

  Timer {
    interval: 150
    running: true
    repeat: false
    onTriggered: {
      editor.loadForm()
      editor.tab = "keys"
      var problems = []
      if (editor.keymapLayer !== 2) problems.push("keymapLayer")
      if (!editor.loaded) problems.push("editor form did not load")
      if (widget.panelLoadError) problems.push(widget.panelLoadError)
      if (problems.length) console.warn("QMLLOAD_FAIL " + problems.join("; "))
      else console.log("QMLLOAD_OK")
      Qt.quit()
    }
  }
}
