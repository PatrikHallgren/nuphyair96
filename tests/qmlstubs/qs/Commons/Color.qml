pragma Singleton
import QtQuick

QtObject {
  property color foreground: "#cacccc"
  property color accent: "#cacccc"
  property color urgent: "#a55555"
  property color muted: "#707880"
  readonly property QtObject popups: QtObject {
    property color text: "#cacccc"
    property color background: "#101315"
  }
}
