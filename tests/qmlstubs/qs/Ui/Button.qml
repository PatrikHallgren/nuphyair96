import QtQuick

Item {
  id: root
  property string text: ""
  property string tooltipText: ""
  property bool selected: false
  property bool focusable: false
  property bool bordered: false
  property color foreground: "#cacccc"
  property real fontSize: 12
  property real horizontalPadding: 0
  property real radius: 2
  signal clicked()
  implicitWidth: Math.max(28, label.implicitWidth + 16)
  implicitHeight: Math.max(28, label.implicitHeight + 8)

  Rectangle {
    anchors.fill: parent
    radius: root.radius
    color: root.selected ? "#2a2a2a" : "transparent"
    border.width: root.bordered || root.selected ? 1 : 0
    border.color: root.foreground
  }
  Text {
    id: label
    anchors.centerIn: parent
    width: Math.min(implicitWidth, parent.width - 4)
    text: root.text
    color: root.foreground
    font.pixelSize: root.fontSize
    font.family: "monospace"
    elide: Text.ElideRight
    horizontalAlignment: Text.AlignHCenter
  }
}
