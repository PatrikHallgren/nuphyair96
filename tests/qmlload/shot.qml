import QtQuick
import QtQuick.Controls
import "board.js" as Board
import "../../" as Air

ApplicationWindow {
  id: window
  width: 440
  height: Math.min(Math.max(editor.documentHeight, 160), 520)
  visible: true
  color: "#161616"
  title: "Air96"

  QtObject {
    id: airService
    property var snapshot: ({
      keyboardName: "NuPhy NuPhy Air96 V2",
      layout: Board.keys,
      layers: [
        {id: 0, name: "Mac"},
        {id: 2, name: "Windows"}
      ],
      lighting: {effect: 1, brightness: 180, speed: 128, hex: "#ffffff", follow_theme: true, solid_when_following: true},
      homeAssistant: {
        url: "http://homeassistant.local:8123",
        entities: ["light.floor_lamp_66fa"],
        enabled: true, syncBrightness: false, onlyWhenOn: true,
        hex: "#ff8800", brightness: 140, followTheme: false,
        tokenEnv: "HA_TOKEN", configured: true, lastError: "", lastStatus: 200
      },
      screensaver: {enabled: false},
      theme: "#e68e0d",
      message: "USB VIA backlight"
    })
    property var keymap: ({known: true, keys: ({}), codes: [{name: "Escape", short: "Esc", value: 41}]})
    property var drafts: ({})
    property var changes: []
    property bool actionBusy: false
    property bool ready: true
    property string lastError: ""
    function request(action, config) { return false }
    function stage(layer, row, col, value, original) {}
    function discard() {}
  }

  Air.Editor {
    id: editor
    anchors.fill: parent
    service: airService
  }

  property var shots: ["keyboard", "lamp", "keys"]
  property int shotIndex: 0
  property string shotDir: "/tmp/air96-panel-shots"

  function saveCurrent() {
    editor.grabToImage(function(result) {
      result.saveToFile(window.shotDir + "/" + window.shots[window.shotIndex] + ".png")
      window.shotIndex += 1
      if (window.shotIndex >= window.shots.length) {
        console.log("QMLSHOT_OK")
        Qt.quit()
      } else {
        editor.tab = window.shots[window.shotIndex]
        settle.start()
      }
    })
  }

  Timer {
    id: settle
    interval: 250
    onTriggered: window.saveCurrent()
  }

  Component.onCompleted: {
    editor.loadForm()
    editor.tab = shots[0]
    settle.start()
  }
}
