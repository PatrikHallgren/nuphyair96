pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import qs.Commons as Commons

ColumnLayout {
  id: root
  property string hex: "#ffffff"
  property var scrollView: null
  signal picked(string hex)
  spacing: Commons.Style.space(6)

  function clamp(number) { return Math.max(0, Math.min(1, number)) }
  function byteText(channel) {
    var text = Math.round(Math.max(0, Math.min(1, channel)) * 255).toString(16)
    return text.length < 2 ? "0" + text : text
  }
  function emitColor() {
    hex = "#" + byteText(selected.r) + byteText(selected.g) + byteText(selected.b)
    picked(hex)
  }

  readonly property color selected: Qt.hsva(hue, saturation, value, 1)
  property real hue: 0
  property real saturation: 0
  property real value: 1

  function setColor(next) {
    if (!/^#[0-9a-fA-F]{6}$/.test(next)) return
    hex = next
    var parsed = Qt.color(next)
    if (parsed.hsvHue >= 0) hue = parsed.hsvHue
    saturation = parsed.hsvSaturation
    value = parsed.hsvValue
  }

  Rectangle {
    id: field
    Layout.fillWidth: true
    implicitHeight: Commons.Style.space(90)
    color: Qt.hsva(root.hue, 1, 1, 1)
    Rectangle {
      anchors.fill: parent
      gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: "white" }
        GradientStop { position: 1; color: "transparent" }
      }
    }
    Rectangle {
      anchors.fill: parent
      gradient: Gradient {
        GradientStop { position: 0; color: "transparent" }
        GradientStop { position: 1; color: "black" }
      }
    }
    MouseArea {
      anchors.fill: parent
      onPositionChanged: function(mouse) { pick(mouse) }
      onPressed: function(mouse) { pick(mouse) }
      function pick(mouse) {
        root.saturation = root.clamp(mouse.x / width)
        root.value = root.clamp(1 - mouse.y / height)
        root.emitColor()
      }
    }
  }
  Rectangle {
    Layout.fillWidth: true
    implicitHeight: Commons.Style.space(14)
    radius: height / 2
    gradient: Gradient {
      orientation: Gradient.Horizontal
      GradientStop { position: 0.00; color: "#ff0000" }
      GradientStop { position: 0.17; color: "#ffff00" }
      GradientStop { position: 0.33; color: "#00ff00" }
      GradientStop { position: 0.50; color: "#00ffff" }
      GradientStop { position: 0.67; color: "#0000ff" }
      GradientStop { position: 0.83; color: "#ff00ff" }
      GradientStop { position: 1.00; color: "#ff0000" }
    }
    MouseArea {
      anchors.fill: parent
      onPositionChanged: function(mouse) { root.hue = root.clamp(mouse.x / width); root.emitColor() }
      onPressed: function(mouse) { root.hue = root.clamp(mouse.x / width); root.emitColor() }
    }
  }
  Rectangle {
    implicitWidth: Commons.Style.space(28)
    implicitHeight: Commons.Style.space(28)
    radius: Commons.Style.space(4)
    color: /^#[0-9a-fA-F]{6}$/.test(root.hex) ? root.hex : "transparent"
    border.color: Commons.Color.muted
    border.width: 1
  }
}
