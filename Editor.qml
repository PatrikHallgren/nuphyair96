pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import qs.Commons as Commons
import qs.Ui as Ui

Controls.ScrollView {
  id: root
  required property var service
  readonly property var snapshot: service && service.snapshot ? service.snapshot : ({})
  readonly property real preferredWidth: Commons.Style.space(440)
  // ScrollView.contentHeight is FINAL. This is the column's own height.
  readonly property real documentHeight: body.implicitHeight
  signal closeRequested()
  property string tab: "keyboard"
  // Item.layer is a FINAL property on ScrollView. This is the keymap layer.
  property int keymapLayer: 2
  property string selectedId: ""
  property string query: ""
  property bool loaded: false
  property int effectIndex: 1
  property int brightness: 180
  property int speed: 128
  property string hex: "#ffffff"
  property bool follow: false
  property bool solidFollow: true
  property string haUrl: ""
  property string haEntities: ""
  property bool haEnabled: false
  property bool haSyncBrightness: false
  property bool haOnlyWhenOn: true
  property string haHex: "#ffffff"
  property int haBrightness: 180
  property bool haFollow: true
  property bool screensaverOn: false
  contentWidth: availableWidth
  clip: true
  focus: true
  Keys.onEscapePressed: root.closeRequested()

  QtObject {
    id: popupPalette
    readonly property color foreground: Commons.Color.popups.text
    readonly property color background: Commons.Color.popups.background
  }

  Timer {
    id: keyboardPush
    interval: 200
    onTriggered: root.sendKeyboard()
  }
  Timer {
    id: lampPush
    interval: 200
    onTriggered: root.sendLamp()
  }

  function titleText() {
    var name = String(snapshot.keyboardName || "Air96 V2").replace(/\s+/g, " ").replace(/^\s|\s$/g, "")
    var parts = name.split(" ")
    if (parts.length >= 2 && parts[0].toLowerCase() === parts[1].toLowerCase()) return parts.slice(1).join(" ")
    return name || "Air96 V2"
  }

  function loadForm() {
    var lighting = snapshot.lighting
    if (!lighting) return
    effectIndex = lighting.effect
    brightness = lighting.brightness
    speed = lighting.speed
    hex = lighting.hex || "#ffffff"
    follow = !!lighting.follow_theme
    solidFollow = lighting.solid_when_following !== false
    var ha = snapshot.homeAssistant || ({})
    haUrl = ha.url || ""
    haEntities = (ha.entities || []).join(", ")
    haEnabled = !!ha.enabled
    haSyncBrightness = !!ha.syncBrightness
    haOnlyWhenOn = ha.onlyWhenOn !== false
    haHex = ha.hex || "#ffffff"
    haBrightness = ha.brightness === undefined ? 180 : ha.brightness
    haFollow = ha.followTheme !== false
    screensaverOn = !!(snapshot.screensaver && snapshot.screensaver.enabled)
    loaded = true
    if (keyboardColor) keyboardColor.setColor(hex)
    if (lampColor) lampColor.setColor(haHex)
  }

  function selectedKey() {
    var rows = snapshot.layout || []
    for (var i = 0; i < rows.length; i++) if (rows[i].id === selectedId) return rows[i]
    return null
  }

  function assignment() {
    var key = selectedKey()
    if (!key || !service || !service.keymap || !service.keymap.keys) return null
    return service.keymap.keys[keymapLayer + ":" + key.row + ":" + key.col] || null
  }

  function diagramLabels() {
    var labels = ({})
    var rows = snapshot.layout || []
    var keys = service && service.keymap && service.keymap.keys ? service.keymap.keys : ({})
    var drafts = service && service.drafts ? service.drafts : ({})
    for (var i = 0; i < rows.length; i++) {
      var key = rows[i]
      var address = keymapLayer + ":" + key.row + ":" + key.col
      var current = keys[address]
      var draft = drafts[address]
      if (draft) labels[key.id] = "•"
      else if (current) labels[key.id] = current.short || current.name
      else labels[key.id] = key.label
    }
    return labels
  }

  function matches() {
    var codes = (service && service.keymap && service.keymap.codes) || []
    var found = []
    var needle = query.toLowerCase()
    for (var i = 0; i < codes.length && found.length < 12; i++) {
      if (!needle || String(codes[i].name).toLowerCase().indexOf(needle) >= 0) found.push(codes[i])
    }
    return found
  }

  function entityList() {
    return haEntities.split(",").map(function(item) { return item.trim() }).filter(function(item) { return item.length > 0 })
  }

  function sendKeyboard() {
    if (!service) return
    if (service.actionBusy) { keyboardPush.restart(); return }
    service.request("apply", {
      brightness: brightness, speed: speed, hex: hex, follow_theme: follow
    })
  }

  function sendLamp() {
    if (!service) return
    if (service.actionBusy) { lampPush.restart(); return }
    var entities = entityList()
    service.request("settings", {home_assistant: {
      enabled: haUrl.length > 0 && entities.length > 0,
      url: haUrl, hex: haHex, brightness: haBrightness,
      follow_theme: haFollow, only_when_on: haOnlyWhenOn, entities: entities
    }})
  }

  onSnapshotChanged: if (!loaded) loadForm()
  onTabChanged: if (tab === "keys" && service && service.keymap && !service.keymap.known) service.request("keymap-load")

  Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AlwaysOff
  Controls.ScrollBar.vertical: Controls.ScrollBar {
    id: verticalScroll
    parent: root
    x: root.mirrored ? 0 : root.width - width
    y: root.topPadding
    height: root.availableHeight
    visible: size < 1
    policy: Controls.ScrollBar.AsNeeded
    contentItem: Rectangle {
      implicitWidth: Commons.Style.space(5)
      implicitHeight: Commons.Style.space(24)
      radius: Commons.Style.cornerRadius
      color: verticalScroll.pressed ? Commons.Color.accent : Commons.Color.muted
    }
    background: Rectangle { color: "transparent" }
  }

  ColumnLayout {
    id: body
    width: root.availableWidth
    spacing: Commons.Style.space(6)

    PlainText {
      Layout.fillWidth: true
      text: root.titleText()
      font.bold: true
      font.pixelSize: Commons.Style.font.heading
      elide: Text.ElideRight
    }
    PlainText {
      Layout.fillWidth: true
      font.pixelSize: Commons.Style.font.caption
      color: (root.snapshot.error || (root.service && root.service.lastError)) ? Commons.Color.urgent : Commons.Color.muted
      elide: Text.ElideRight
      maximumLineCount: 2
      text: {
        if (!root.service) return "Air96 service is not running"
        if (root.snapshot.setupIssue === "hid-permission") return "No permission on the VIA hidraw device. Replug the USB cable after the udev rule."
        if (root.snapshot.setupIssue === "not-found") return "Connect the Air96 with the USB cable."
        if (root.snapshot.setupIssue === "ambiguous") return "More than one Air96 VIA interface is connected."
        return root.snapshot.error || root.snapshot.message || root.service.lastError || "USB VIA backlight"
      }
    }

    RowLayout {
      Layout.fillWidth: true
      spacing: Commons.Style.space(4)
      Repeater {
        model: [
          {id: "keyboard", label: "Keyboard"},
          {id: "lamp", label: "Lamp"},
          {id: "keys", label: "Keys"}
        ]
        delegate: Ui.Button {
          required property var modelData
          Layout.fillWidth: true
          text: modelData.label
          selected: root.tab === modelData.id
          bordered: true
          focusable: true
          foreground: Commons.Color.popups.text
          onClicked: root.tab = modelData.id
        }
      }
    }

    ColumnLayout {
      visible: root.tab === "keyboard"
      Layout.fillWidth: true
      spacing: Commons.Style.space(6)
      KeyboardView {
        Layout.fillWidth: true
        Layout.preferredHeight: Math.round(width * 6 / 19)
        layout: root.snapshot.layout || []
        labels: ({})
        selected: ""
      }
      Ui.Toggle {
        Layout.fillWidth: true
        label: "Follow the Omarchy theme"
        description: "Theme color. Brightness still applies."
        checked: root.follow
        foreground: Commons.Color.popups.text
        onClicked: { root.follow = !root.follow; root.sendKeyboard() }
      }
      PlainText {
        visible: root.follow
        text: "Theme " + (root.snapshot.theme || "not found")
        font.pixelSize: Commons.Style.font.caption
        color: Commons.Color.muted
      }
      ColorPicker {
        id: keyboardColor
        visible: !root.follow
        Layout.fillWidth: true
        onPicked: function(next) { root.hex = next; keyboardPush.restart() }
        onVisibleChanged: if (visible) setColor(root.hex)
      }
      Ui.TextField {
        visible: !root.follow
        Layout.fillWidth: true
        text: root.hex
        placeholderText: "#RRGGBB"
        maximumLength: 9
        foreground: Commons.Color.popups.text
        selectByMouse: true
        onTextEdited: { root.hex = text; keyboardColor.setColor(text); keyboardPush.restart() }
      }
      PlainText { text: "Brightness " + root.brightness; font.pixelSize: Commons.Style.font.caption }
      LightingSlider {
        Layout.fillWidth: true
        bar: popupPalette
        scrollView: root
        minimum: 0; maximum: 255; step: 1; integer: true
        value: root.brightness
        fillColor: Commons.Color.accent
        knobColor: activeFocus ? Commons.Color.accent : Commons.Color.popups.text
        onMoved: function(value) { root.brightness = value; keyboardPush.restart() }
      }
      Ui.Toggle {
        Layout.fillWidth: true
        label: "Light show while the screensaver is on"
        description: "Breathing in this color. Not written to EEPROM."
        checked: root.screensaverOn
        foreground: Commons.Color.popups.text
        onClicked: {
          root.screensaverOn = !root.screensaverOn
          if (root.service) root.service.request("settings", {screensaver: {enabled: root.screensaverOn}})
        }
      }
    }

    ColumnLayout {
      visible: root.tab === "lamp"
      Layout.fillWidth: true
      spacing: Commons.Style.space(6)
      Ui.Toggle {
        Layout.fillWidth: true
        label: "Follow the Omarchy theme"
        description: "Theme color, plus the brightness below."
        checked: root.haFollow
        foreground: Commons.Color.popups.text
        onClicked: { root.haFollow = !root.haFollow; root.sendLamp() }
      }
      ColorPicker {
        id: lampColor
        visible: !root.haFollow
        Layout.fillWidth: true
        onPicked: function(next) { root.haHex = next; lampPush.restart() }
        onVisibleChanged: if (visible) setColor(root.haHex)
      }
      Ui.TextField {
        visible: !root.haFollow
        Layout.fillWidth: true
        text: root.haHex
        placeholderText: "#RRGGBB"
        maximumLength: 9
        foreground: Commons.Color.popups.text
        selectByMouse: true
        onTextEdited: { root.haHex = text; lampColor.setColor(text); lampPush.restart() }
      }
      PlainText { text: "Brightness " + root.haBrightness; font.pixelSize: Commons.Style.font.caption }
      LightingSlider {
        Layout.fillWidth: true
        bar: popupPalette
        scrollView: root
        minimum: 0; maximum: 255; step: 1; integer: true
        value: root.haBrightness
        fillColor: Commons.Color.accent
        knobColor: activeFocus ? Commons.Color.accent : Commons.Color.popups.text
        onMoved: function(value) { root.haBrightness = value; lampPush.restart() }
      }
      Ui.Toggle {
        Layout.fillWidth: true
        label: "Only if the light is already on"
        description: "An off light stays off."
        checked: root.haOnlyWhenOn
        foreground: Commons.Color.popups.text
        onClicked: { root.haOnlyWhenOn = !root.haOnlyWhenOn; root.sendLamp() }
      }
      Ui.TextField {
        Layout.fillWidth: true
        text: root.haUrl
        placeholderText: "http://homeassistant.local:8123"
        foreground: Commons.Color.popups.text
        selectByMouse: true
        onTextEdited: { root.haUrl = text; lampPush.restart() }
      }
      Ui.TextField {
        Layout.fillWidth: true
        text: root.haEntities
        placeholderText: "light.floor_lamp_66fa"
        foreground: Commons.Color.popups.text
        selectByMouse: true
        onTextEdited: { root.haEntities = text; lampPush.restart() }
      }
      PlainText {
        Layout.fillWidth: true
        font.pixelSize: Commons.Style.font.caption
        color: (root.snapshot.homeAssistant && root.snapshot.homeAssistant.lastError) ? Commons.Color.urgent : Commons.Color.muted
        wrapMode: Text.WordWrap
        maximumLineCount: 2
        elide: Text.ElideRight
        text: {
          var ha = root.snapshot.homeAssistant || ({})
          if (ha.lastError) return ha.lastError
          var token = ha.configured ? "Token configured." : "No token."
          if (ha.lastStatus) return token + " HTTP " + ha.lastStatus + "."
          return token + " Brightness is sent with the color."
        }
      }
    }

    ColumnLayout {
      visible: root.tab === "keys"
      Layout.fillWidth: true
      spacing: Commons.Style.space(6)
      KeyboardView {
        Layout.fillWidth: true
        Layout.preferredHeight: Math.round(width * 6 / 19)
        layout: root.snapshot.layout || []
        labels: root.diagramLabels()
        selected: root.selectedId
        onKeyClicked: function(id) { root.selectedId = id }
      }
      Flow {
        Layout.fillWidth: true
        spacing: Commons.Style.space(4)
        Repeater {
          model: root.snapshot.layers || []
          delegate: Ui.Button {
            required property var modelData
            text: modelData.name
            selected: root.keymapLayer === modelData.id
            bordered: true
            focusable: true
            foreground: Commons.Color.popups.text
            onClicked: root.keymapLayer = modelData.id
          }
        }
      }
      PlainText {
        Layout.fillWidth: true
        font.pixelSize: Commons.Style.font.caption
        elide: Text.ElideRight
        text: {
          var key = root.selectedKey()
          var current = root.assignment()
          if (!key) return "Layer 0 is Mac, layer 2 is Windows."
          var draft = root.service && root.service.drafts[root.keymapLayer + ":" + key.row + ":" + key.col]
          return key.label + "  " + key.row + "," + key.col + "  " + (draft ? ("pending " + draft.value) : (current ? current.name : "unread"))
        }
      }
      Ui.TextField {
        Layout.fillWidth: true
        placeholderText: "Search keycodes"
        foreground: Commons.Color.popups.text
        selectByMouse: true
        onTextEdited: root.query = text
      }
      Flow {
        Layout.fillWidth: true
        spacing: Commons.Style.space(4)
        Repeater {
          model: root.matches()
          delegate: Ui.Button {
            required property var modelData
            text: modelData.short || modelData.name
            tooltipText: modelData.name
            focusable: true
            foreground: Commons.Color.popups.text
            onClicked: {
              var key = root.selectedKey()
              var current = root.assignment()
              if (key && current && root.service) root.service.stage(root.keymapLayer, key.row, key.col, modelData.value, current.value)
            }
          }
        }
      }
      RowLayout {
        Layout.fillWidth: true
        Ui.Button {
          Layout.fillWidth: true
          text: "Read"
          focusable: true
          foreground: Commons.Color.popups.text
          onClicked: {
            root.tab = "keys"
            if (root.service) root.service.request("keymap-load")
          }
        }
        Ui.Button {
          Layout.fillWidth: true
          text: "Apply " + (root.service ? root.service.changes.length : 0)
          enabled: root.service && root.service.changes.length > 0 && !root.service.actionBusy
          bordered: true
          focusable: true
          foreground: Commons.Color.popups.text
          onClicked: root.service.request("keymap-apply", {changes: root.service.changes})
        }
        Ui.Button {
          Layout.fillWidth: true
          text: "Discard"
          focusable: true
          foreground: Commons.Color.popups.text
          onClicked: root.service && root.service.discard()
        }
      }
    }
  }
}
