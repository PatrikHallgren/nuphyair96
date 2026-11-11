import QtQuick

Item {
  property var bar: null
  property real value: 0
  property real minimum: 0
  property real maximum: 1
  property real step: 0.05
  property bool integer: false
  property color fillColor: "#cacccc"
  property color knobColor: "#cacccc"
  signal moved(real value)
}
