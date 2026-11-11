import QtQuick

Item {
  id: root
  property var bar: null
  property real value: 0
  property real minimum: 0
  property real maximum: 1
  property real step: 0.05
  property bool integer: false
  property color fillColor: "#cacccc"
  property color knobColor: "#cacccc"
  signal moved(real value)
  implicitHeight: 22

  Rectangle {
    anchors.verticalCenter: parent.verticalCenter
    width: parent.width
    height: 4
    radius: 2
    color: "#333333"
    Rectangle {
      width: parent.width * Math.max(0, Math.min(1, (root.value - root.minimum) / Math.max(0.001, root.maximum - root.minimum)))
      height: parent.height
      radius: 2
      color: root.fillColor
    }
  }
  Rectangle {
    width: 12
    height: 12
    radius: 6
    color: root.knobColor
    y: (parent.height - height) / 2
    x: Math.max(0, parent.width * Math.max(0, Math.min(1, (root.value - root.minimum) / Math.max(0.001, root.maximum - root.minimum))) - width / 2)
  }
}
