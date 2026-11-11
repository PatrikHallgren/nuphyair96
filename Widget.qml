import QtQuick
import Quickshell.Hyprland
import qs.Commons
import qs.Ui

// Bar host, same shape as the clock widget. The popup file is loaded by URL
// next to this file (the plugin symlink and the real checkout resolve the
// same way). A load error still opens a popup, with the QML message in it.
BarWidget {
  id: root
  moduleName: "local.nuphy-air96"

  property bool fallbackOpen: false
  property bool openWhenReady: false
  property string panelLoadError: ""

  readonly property var service: {
    var host = bar && bar.shell
    if (!host || typeof host.serviceFor !== "function") return null
    return host.serviceFor(root.moduleName)
  }
  readonly property bool panelReady: panelLoader.status === Loader.Ready && panelLoader.item
  readonly property bool opened: fallbackOpen || (panelLoader.item ? panelLoader.item.opened === true : false)
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false

  function loaderError(loader) {
    var component = loader ? loader.sourceComponent : null
    var detail = component && component.errorString ? component.errorString() : ""
    return detail || "The Air96 panel did not load."
  }

  function copies() {
    var items = bar && typeof bar.moduleWidgets === "function" ? bar.moduleWidgets(moduleName) : null
    if (!items || !items.length) return [root]
    return items
  }

  function screenName(item) {
    var win = item && item.QsWindow ? item.QsWindow.window : null
    var screen = win ? win.screen : null
    return screen ? String(screen.name || "") : ""
  }

  function focusedScreenName() {
    var monitor = Hyprland.focusedMonitor
    return monitor ? String(monitor.name || "") : ""
  }

  // One widget is built per monitor, and only the first keeps the air96 IPC
  // handler. A command has no pointer, so it follows the open popup, then the
  // focused monitor. A click calls togglePanel on the instance under the pointer.
  function routedCopy() {
    var items = copies()
    var focused = focusedScreenName()
    var openedCopy = null
    var focusedCopy = null
    for (var i = 0; i < items.length; i++) {
      var item = items[i]
      if (!item || typeof item.togglePanel !== "function") continue
      if (item.opened === true) openedCopy = item
      if (focused && screenName(item) === focused) focusedCopy = item
    }
    return openedCopy || focusedCopy || root
  }

  function openHere() {
    fallbackOpen = false
    if (panelReady && panelLoader.item.open) {
      panelLoader.item.open()
      return
    }
    if (panelLoader.status === Loader.Loading || panelLoader.status === Loader.Null) {
      openWhenReady = true
      return
    }
    fallbackOpen = true
  }

  function closeHere() {
    openWhenReady = false
    fallbackOpen = false
    if (panelLoader.item && panelLoader.item.close) panelLoader.item.close()
  }

  function open() { openHere() }
  function close() { closeHere() }

  function togglePanel() {
    if (panelReady && panelLoader.item.toggle) {
      fallbackOpen = false
      panelLoader.item.toggle()
      return
    }
    if (panelLoader.status === Loader.Loading || panelLoader.status === Loader.Null) {
      openWhenReady = !openWhenReady
      return
    }
    fallbackOpen = !fallbackOpen
  }

  function closeForPopoutSwitch() {
    fallbackOpen = false
    if (panelLoader.item && panelLoader.item.closeForPopoutSwitch) panelLoader.item.closeForPopoutSwitch()
    else closeHere()
  }

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = button
    if ("service" in target) target.service = root.service
    if ("hostWidget" in target) target.hostWidget = root
  }

  visible: true
  implicitWidth: Math.max(Style.bar.iconSlot * 2, button.implicitWidth)
  implicitHeight: Math.max(Style.bar.sizeHorizontal, button.implicitHeight)

  onBarChanged: injectPanel()
  onServiceChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Air96Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
      if (root.openWhenReady && item && item.open) {
        root.openWhenReady = false
        item.open()
      }
    }
    onStatusChanged: if (status === Loader.Error) {
      root.panelLoadError = root.loaderError(panelLoader)
      console.warn(root.panelLoadError)
      if (root.openWhenReady) {
        root.openWhenReady = false
        root.fallbackOpen = true
      }
    }
  }

  KeyboardPanel {
    id: fallbackPanel
    anchorItem: button
    bar: root.bar
    owner: root
    open: root.fallbackOpen
    centerOnBar: false
    contentWidth: fallbackPanel.fittedContentWidth(Style.space(420))
    contentHeight: fallbackPanel.fittedContentHeight(Style.space(180))
    content: Item {
      implicitWidth: Style.space(420)
      implicitHeight: Style.space(160)
      Text {
        anchors.fill: parent
        anchors.margins: Style.space(12)
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
        color: Color.urgent
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        text: root.panelLoadError || "The Air96 panel did not load."
      }
    }
  }

  ShellIpc {
    target: "air96"

    function open(): void { root.routedCopy().openHere() }
    function close(): void { root.routedCopy().closeHere() }
    function show(): void { root.routedCopy().openHere() }
    function hide(): void { root.routedCopy().closeHere() }
    function toggle(): void { root.routedCopy().togglePanel() }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    // "K" is in the bar's monospace font. The nerd-font keyboard glyph is not.
    text: "K"
    labelText: "A96"
    slotSize: Style.bar.iconSlot * 2
    tooltipText: "Air96"
    onPressed: function(b) { root.togglePanel() }
  }
}
