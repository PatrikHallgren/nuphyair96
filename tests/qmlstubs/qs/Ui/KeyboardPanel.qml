import QtQuick

Item {
  id: root
  property Item anchorItem: null
  property var owner: null
  property var bar: null
  property bool open: false
  property bool centerOnBar: false
  property real contentWidth: 280
  property real contentHeight: 200
  property Item focusTarget: null
  property Component content: null
  readonly property Item loadedContent: contentLoader.item
  readonly property real loadedContentHeight: contentLoader.item ? contentLoader.item.implicitHeight : 0

  function fittedContentWidth(requested) { return requested }
  function fittedContentHeight(requested) { return requested }

  Loader {
    id: contentLoader
    active: root.content !== null
    sourceComponent: root.content
  }
}
