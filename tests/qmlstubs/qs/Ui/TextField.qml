import QtQuick

Item {
  property color foreground: "#cacccc"
  property string text: ""
  property string placeholderText: ""
  property int maximumLength: 32767
  property bool selectByMouse: false
  signal textEdited()
}
