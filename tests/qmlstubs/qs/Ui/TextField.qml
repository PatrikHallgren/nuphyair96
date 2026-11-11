import QtQuick

Item {
  id: root
  property color foreground: "#cacccc"
  property string text: ""
  property string placeholderText: ""
  property int maximumLength: 32767
  property bool selectByMouse: false
  signal textEdited()
  implicitHeight: 28

  Rectangle {
    anchors.fill: parent
    color: "#111111"
    border.width: 1
    border.color: root.foreground
  }
  Text {
    anchors.fill: parent
    anchors.margins: 6
    text: root.text !== "" ? root.text : root.placeholderText
    color: root.text !== "" ? root.foreground : "#707880"
    font.pixelSize: 12
    font.family: "monospace"
    elide: Text.ElideRight
    verticalAlignment: Text.AlignVCenter
  }
}
