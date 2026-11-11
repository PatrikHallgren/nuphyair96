pragma Singleton
import QtQuick

QtObject {
  function space(px) { return px }
  property int cornerRadius: 0
  readonly property QtObject font: QtObject {
    readonly property string family: "monospace"
    readonly property int body: 12
    readonly property int caption: 10
    readonly property int heading: 16
  }
  readonly property QtObject bar: QtObject {
    readonly property int iconSlot: 27
    readonly property int sizeHorizontal: 26
  }
}
