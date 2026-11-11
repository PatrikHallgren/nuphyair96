import QtQuick

Item {
  property var bar: null
  property string text: ""
  property string labelText: ""
  property real slotSize: 27
  property string tooltipText: ""
  signal pressed(int button)
  implicitWidth: slotSize
  implicitHeight: slotSize
}
