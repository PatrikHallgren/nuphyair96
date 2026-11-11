import QtQuick
import qs.Commons
import qs.Ui

// Bar host, same shape as the clock and weather widgets. The popup lives in
// Air96Panel.qml and is loaded by URL, so a panel or editor error cannot stop
// this file from instantiating. The icon stays up with or without a keyboard.
BarWidget {
  id: root
  moduleName: "local.nuphy-air96"

  readonly property var service: {
    var host = bar && bar.shell
    if (!host || typeof host.serviceFor !== "function") return null
    return host.serviceFor(root.moduleName)
  }
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false

  function open() {
    if (panelLoader.item) panelLoader.item.open()
  }

  function close() {
    if (panelLoader.item) panelLoader.item.close()
  }

  function togglePanel() {
    if (panelLoader.item && panelLoader.item.toggle) panelLoader.item.toggle()
  }

  function closeForPopoutSwitch() {
    if (panelLoader.item && panelLoader.item.closeForPopoutSwitch)
      panelLoader.item.closeForPopoutSwitch()
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
    }
    onStatusChanged: if (status === Loader.Error) console.warn("Air96 panel failed to load")
  }

  ShellIpc {
    target: "air96"

    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.togglePanel() }
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
