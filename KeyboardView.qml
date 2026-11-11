pragma ComponentBehavior: Bound
import QtQuick
import qs.Commons as Commons
import qs.Ui as Ui

Item {
  id: root
  property var layout: []
  property var highlights: ({})
  property var labels: ({})
  property string selected: ""
  property bool showHighlights: false
  signal keyClicked(string id)
  readonly property real unit: width / 19
  implicitHeight: unit * 6
  clip: true
  LayoutMirroring.enabled: false
  LayoutMirroring.childrenInherit: true

  Repeater {
    model: root.layout
    delegate: Ui.Button {
      id: key
      required property var modelData
      readonly property var highlight: root.highlights[modelData.id] || null
      readonly property bool picked: root.selected === modelData.id
      x: modelData.x * root.unit
      y: modelData.y * root.unit
      width: Math.max(4, modelData.w * root.unit - 3)
      height: Math.max(4, modelData.h * root.unit - 3)
      radius: Commons.Style.space(2)
      horizontalPadding: Commons.Style.space(1)
      fontSize: Commons.Style.font.caption
      objectName: "key-" + modelData.id
      text: root.labels[modelData.id] || modelData.label
      tooltipText: modelData.label + (key.highlight && key.highlight.label ? " · " + key.highlight.label : "")
      selected: key.picked
      bordered: true
      focusable: true
      foreground: key.highlight && root.showHighlights ? key.highlight.color : (key.picked ? Commons.Color.accent : Commons.Color.popups.text)
      opacity: !root.showHighlights || !key.highlight ? 1 : (key.highlight.level === "idle" ? 0.62 : 1)
      onClicked: root.keyClicked(modelData.id)
    }
  }
}
