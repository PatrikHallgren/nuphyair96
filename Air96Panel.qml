pragma ComponentBehavior: Bound
import QtQuick
import qs.Commons as Commons
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
    contentWidth: panel.fittedContentWidth(panel.loadedContent ? panel.loadedContent.preferredWidth : Commons.Style.space(760))
    contentHeight: panel.fittedContentHeight(panel.loadedContentHeight, Commons.Style.space(760))

    content: Item {
      id: page
      property var editorService: root.service
      property string editorError: ""
      readonly property real preferredWidth: Commons.Style.space(760)
      implicitWidth: preferredWidth
      implicitHeight: editor.item ? editor.item.implicitHeight : Math.max(Commons.Style.space(180), errorText.implicitHeight + Commons.Style.space(24))

      function applyService() {
        if (editor.item) editor.item.service = editorService
      }

      onEditorServiceChanged: applyService()

      Loader {
        id: editor
        anchors.left: parent.left
        anchors.right: parent.right
        onLoaded: page.applyService()
        onStatusChanged: {
          if (status !== Loader.Error) return
          var detail = ""
          if (sourceComponent && sourceComponent.errorString) detail = sourceComponent.errorString()
          page.editorError = detail || "The Air96 editor failed to load."
          console.warn(page.editorError)
        }
      }

      Component.onCompleted: editor.setSource(Qt.resolvedUrl("Editor.qml"), { service: page.editorService })

      Text {
        id: errorText
        width: parent.width
        visible: editor.status === Loader.Error
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
        color: Commons.Color.urgent
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.body
        text: page.editorError
      }
    }
  }
}
