import QtQuick
import Quickshell.Io

Item {
  id: root
  property var shell: null
  property var workerCommand: ["python3", "-u", Qt.resolvedUrl("air96_worker.py").toString().replace(/^file:\/\//, "")]
  property var snapshot: ({})
  property var keymap: ({})
  property var drafts: ({})
  property bool actionBusy: false
  property int nextId: 0
  property int pendingId: -1
  property string pendingAction: ""
  property string lastError: ""
  readonly property bool ready: process.running && !!snapshot.layout
  readonly property var changes: Object.keys(drafts).map(function(key) { return drafts[key] })

  function request(action, config) {
    if (!ready || actionBusy) return false
    pendingAction = action
    pendingId = ++nextId
    actionBusy = true
    lastError = ""
    process.write(JSON.stringify({id: pendingId, action: action, config: config || {}}) + "\n")
    return true
  }

  function stage(layer, row, col, value, original) {
    if (!keymap.known || actionBusy) return
    var address = layer + ":" + row + ":" + col
    var next = Object.assign({}, drafts)
    if (value === original) delete next[address]
    else next[address] = {
      layer: layer, row: row, col: col, value: value,
      original: next[address] ? next[address].original : original
    }
    drafts = next
  }

  function discard() { drafts = ({}) }

  function workerStopped() {
    actionBusy = false
    pendingId = -1
    snapshot = ({})
    keymap = Object.assign({}, keymap, {known: false})
    if (!lastError) lastError = "Air96 worker stopped; restarting"
    if (!restart.running) restart.start()
  }

  Process {
    id: process
    command: root.workerCommand
    stdinEnabled: true
    running: true
    stdout: SplitParser {
      onRead: function(line) {
        try {
          const value = JSON.parse(line)
          if (value.layout) root.snapshot = value
          if (value.keymap && value.keymap.keys && value.requestId === root.pendingId) {
            root.keymap = value.keymap
            if (root.pendingAction === "keymap-apply" && !value.error) root.discard()
          }
          if (value.requestId === root.pendingId || value.protocolError) {
            root.actionBusy = false
            root.pendingId = -1
          }
          root.lastError = value.layout ? (value.error || "") : String(value.error || "")
        } catch (error) { root.lastError = "Invalid Air96 worker response" }
      }
    }
    stderr: SplitParser { onRead: function(line) { root.lastError = line.slice(0, 600) } }
    onRunningChanged: if (!running) root.workerStopped()
    onExited: root.workerStopped()
  }
  Timer { id: restart; interval: 5000; onTriggered: process.running = true }
}
