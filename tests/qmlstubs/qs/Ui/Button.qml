import QtQuick

Item {
  property string text: ""
  property string tooltipText: ""
  property bool selected: false
  property bool focusable: false
  property bool bordered: false
  property color foreground: "#cacccc"
  property real fontSize: 12
  property real horizontalPadding: 0
  property real radius: 0
  signal clicked()
}
