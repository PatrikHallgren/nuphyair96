import QtQuick
import qs.Commons as Commons
import qs.Ui as Ui

// Wheel events scroll the popup. Adapted from fldc/omarchy-nuphy LightingSlider.qml.
Ui.PanelSlider {
  id: root
  property var scrollView: null

  function handleWheel(event) {
    const flick = scrollView ? scrollView.contentItem : null
    if (flick && typeof flick.contentY === "number") {
      const delta = event.pixelDelta.y || event.angleDelta.y / 120 * Commons.Style.space(48)
      const minimumY = flick.originY || 0
      const maximumY = minimumY + Math.max(0, flick.contentHeight - flick.height)
      flick.contentY = Math.max(minimumY, Math.min(maximumY, flick.contentY - delta))
    }
    event.accepted = true
  }

  MouseArea {
    anchors.fill: parent
    z: 1
    acceptedButtons: Qt.NoButton
    scrollGestureEnabled: true
    onWheel: function(event) { root.handleWheel(event) }
  }
}
