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
    contentWidth: panel.fittedContentWidth(panel.loadedContent ? panel.loadedContent.preferredWidth : Commons.Style.space(440))
    contentHeight: panel.fittedContentHeight(panel.loadedContentHeight)

    content: Item {
      id: page
      property var editorService: root.service
      property string editorError: ""
      readonly property real preferredWidth: Commons.Style.space(440)
      readonly property real maxBody: Commons.Style.space(520)
      implicitWidth: preferredWidth
      implicitHeight: {
        var body = editor.item && editor.item.documentHeight ? editor.item.documentHeight : Commons.Style.space(180)
        if (editor.status === Loader.Error) body = Math.max(body, errorText.implicitHeight + Commons.Style.space(24))
        return Math.min(Math.max(body, Commons.Style.space(160)), page.maxBody)
      }
      clip: true

      function applyService() {
        if (editor.item) editor.item.service = editorService
      }

      onEditorServiceChanged: applyService()

      Loader {
        id: editor
        anchors.fill: parent
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
        anchors.fill: parent
        anchors.margins: Commons.Style.space(8)
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
