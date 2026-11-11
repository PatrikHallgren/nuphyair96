import QtQuick
import qs.Commons
import qs.Ui

// Popup only. Widget.qml owns the bar button and the air96 IPC target.
// The editor is loaded by URL so an editor error still lets this panel open.
Panel {
  id: root
  moduleName: "local.nuphy-air96"
  manageIpc: false

  property var service: null
  property Item anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    centerOnBar: false
    focusTarget: panel.loadedContent
    contentWidth: panel.fittedContentWidth(panel.loadedContent ? panel.loadedContent.preferredWidth : Style.space(760))
    contentHeight: panel.fittedContentHeight(panel.loadedContentHeight, Style.space(760))

    content: Item {
      id: page
      property var editorService: root.service
      readonly property real preferredWidth: Style.space(760)
      implicitWidth: preferredWidth
      implicitHeight: editor.item ? editor.item.implicitHeight : Style.space(240)

      onEditorServiceChanged: if (editor.item) editor.item.service = editorService

      Loader {
        id: editor
        anchors.left: parent.left
        anchors.right: parent.right
        onLoaded: if (item) item.service = page.editorService
        onStatusChanged: if (status === Loader.Error) console.warn("Air96 editor failed to load")
      }

      Component.onCompleted: editor.setSource(Qt.resolvedUrl("Editor.qml"), { service: page.editorService })
      onEditorServiceChanged: if (editor.item) editor.item.service = editorService

      Text {
        anchors.fill: parent
        visible: editor.status === Loader.Error
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
        color: Color.urgent
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        text: "The Air96 panel did not load. journalctl --user -t omarchy-shell -n 200 --no-pager"
      }
    }
  }
}
