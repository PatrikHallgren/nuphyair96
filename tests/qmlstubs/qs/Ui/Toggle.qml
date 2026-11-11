import QtQuick

Item {
  id: root
  property string label: ""
  property string description: ""
  property bool checked: false
  property color foreground: "#cacccc"
  signal clicked()
  implicitWidth: 200
  implicitHeight: description === "" ? 28 : 44

  Text {
    anchors.left: parent.left
    anchors.right: box.left
    anchors.rightMargin: 8
    anchors.verticalCenter: parent.verticalCenter
    text: root.description === "" ? root.label : root.label + "\n" + root.description
    color: root.foreground
    font.pixelSize: 12
    font.family: "monospace"
    wrapMode: Text.WordWrap
  }
  Rectangle {
    id: box
    width: 16
    height: 16
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    border.width: 1
    border.color: root.foreground
    color: root.checked ? root.foreground : "transparent"
  }
}
