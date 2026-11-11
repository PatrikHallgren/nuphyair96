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
  readonly property real preferredWidth: Commons.Style.space(760)
  signal closeRequested()
  property string tab: "lighting"
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
  implicitHeight: body.implicitHeight
  contentWidth: availableWidth
  clip: true
  focus: true
  Keys.onEscapePressed: root.closeRequested()

  QtObject {
    id: popupPalette
    readonly property color foreground: Commons.Color.popups.text
    readonly property color background: Commons.Color.popups.background
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
    for (var i = 0; i < codes.length && found.length < 18; i++) {
      if (!needle || String(codes[i].name).toLowerCase().indexOf(needle) >= 0) found.push(codes[i])
    }
    return found
  }

  onSnapshotChanged: if (!loaded) loadForm()

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
    spacing: Commons.Style.space(8)

    PlainText {
      Layout.fillWidth: true
      text: root.snapshot.keyboardName || "NuPhy Air96 V2"
      font.bold: true
      font.pixelSize: Commons.Style.font.heading
    }
    PlainText {
      Layout.fillWidth: true
      color: (root.snapshot.error || (root.service && root.service.lastError)) ? Commons.Color.urgent : Commons.Color.muted
      text: {
        if (!root.service) return "Air96 service is not running"
        if (root.snapshot.setupIssue === "hid-permission") return "No permission on the VIA hidraw device. Install the udev rule, then replug the USB cable."
        if (root.snapshot.setupIssue === "not-found") return "Connect the Air96 with the USB cable. Bluetooth and the 2.4G dongle do not expose VIA."
        if (root.snapshot.setupIssue === "ambiguous") return "More than one Air96 VIA interface is connected."
        return root.snapshot.error || root.snapshot.message || root.service.lastError || "USB VIA backlight. Side strips stay on the keyboard's own controls."
      }
    }
    Rectangle {
      Layout.fillWidth: true
      implicitHeight: Commons.Style.space(5)
      radius: height / 2
      color: root.snapshot.theme || root.hex || Commons.Color.popups.text
    }

    RowLayout {
      Layout.fillWidth: true
      Repeater {
        model: [
          {id: "lighting", label: "Lighting"},
          {id: "keys", label: "Keys"}
        ]
        delegate: Ui.Button {
          required property var modelData
          Layout.fillWidth: true
          text: modelData.label
          bordered: root.tab === modelData.id
          focusable: true
          foreground: Commons.Color.popups.text
          onClicked: {
            root.tab = modelData.id
            if (modelData.id === "keys" && root.service && !root.service.keymap.known) root.service.request("keymap-load")
          }
        }
      }
    }

    KeyboardView {
      Layout.fillWidth: true
      Layout.preferredHeight: root.preferredWidth * 6 / 19
      layout: root.snapshot.layout || []
      labels: root.diagramLabels()
      selected: root.selectedId
      onKeyClicked: function(id) { root.selectedId = id }
    }

    ColumnLayout {
      id: lightingPage
      visible: root.tab === "lighting"
      Layout.fillWidth: true
      spacing: Commons.Style.space(6)
      function sendKeyboard() {
        if (!root.service) return
        root.service.request("apply", {
          brightness: root.brightness, speed: root.speed, hex: root.hex, follow_theme: root.follow
        })
      }
      function sendLamp() {
        if (!root.service) return
        root.service.request("settings", {home_assistant: {
          enabled: root.haEnabled, url: root.haUrl, hex: root.haHex, brightness: root.haBrightness,
          follow_theme: root.haFollow, sync_brightness: root.haSyncBrightness, only_when_on: root.haOnlyWhenOn,
          entities: root.haEntities.split(",").map(function(item) { return item.trim() }).filter(function(item) { return item.length > 0 })
        }})
      }
      Ui.Toggle {
        Layout.fillWidth: true
        label: "Keyboard follows the Omarchy theme"
        checked: root.follow
        foreground: Commons.Color.popups.text
        onClicked: { root.follow = !root.follow; parent.sendKeyboard() }
      }
      PlainText {
        visible: root.follow
        text: "Theme color " + (root.snapshot.theme || "not found") + ". Brightness still applies."
      }
      ColorPicker {
        id: keyboardColor
        visible: !root.follow
        Layout.fillWidth: true
        onPicked: function(next) { root.hex = next }
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
        onTextEdited: { root.hex = text; keyboardColor.setColor(text) }
      }
      PlainText { text: "Keyboard brightness " + root.brightness }
      LightingSlider {
        Layout.fillWidth: true
        bar: popupPalette
        scrollView: root
        minimum: 0; maximum: 255; step: 1; integer: true
        value: root.brightness
        fillColor: Commons.Color.accent
        knobColor: activeFocus ? Commons.Color.accent : Commons.Color.popups.text
        onMoved: function(value) { root.brightness = value }
      }
      Ui.Toggle {
        Layout.fillWidth: true
        label: "Light show while the screensaver is on"
        checked: root.screensaverOn
        foreground: Commons.Color.popups.text
        onClicked: {
          root.screensaverOn = !root.screensaverOn
          if (root.service) root.service.request("settings", {screensaver: {enabled: root.screensaverOn}})
        }
      }
      PlainText {
        Layout.fillWidth: true
        font.pixelSize: Commons.Style.font.caption
        opacity: 0.75
        text: "The whole board is one solid color. Screensaver uses the Breathing effect in that color and restores the solid color when org.omarchy.screensaver exits. It is not written to EEPROM."
      }
      Ui.Button {
        Layout.fillWidth: true
        text: root.service && root.service.actionBusy ? "Working" : "Apply keyboard"
        enabled: root.service && root.service.ready && !root.service.actionBusy
        bordered: true
        focusable: true
        foreground: Commons.Color.popups.text
        onClicked: parent.sendKeyboard()
      }

      PlainText { text: "Home Assistant"; font.bold: true }
      Ui.TextField {
        Layout.fillWidth: true
        text: root.haUrl
        placeholderText: "http://homeassistant.local:8123"
        foreground: Commons.Color.popups.text
        selectByMouse: true
        onTextEdited: root.haUrl = text
      }
      Ui.TextField {
        Layout.fillWidth: true
        text: root.haEntities
        placeholderText: "light.desk, light.room"
        foreground: Commons.Color.popups.text
        selectByMouse: true
        onTextEdited: root.haEntities = text
      }
      PlainText {
        Layout.fillWidth: true
        font.pixelSize: Commons.Style.font.caption
        opacity: 0.75
        text: "Token from $" + ((root.snapshot.homeAssistant && root.snapshot.homeAssistant.tokenEnv) || "HA_TOKEN") + " or token_file. The token is never shown. " + ((root.snapshot.homeAssistant && root.snapshot.homeAssistant.configured) ? "A token is configured. " : "No token configured. ") + ((root.snapshot.homeAssistant && root.snapshot.homeAssistant.lastError) || "")
      }
      Ui.Toggle {
        Layout.fillWidth: true
        label: "Lamp follows the Omarchy theme"
        checked: root.haFollow
        foreground: Commons.Color.popups.text
        onClicked: { root.haFollow = !root.haFollow; parent.sendLamp() }
      }
      ColorPicker {
        id: lampColor
        visible: !root.haFollow
        Layout.fillWidth: true
        onPicked: function(next) { root.haHex = next }
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
        onTextEdited: { root.haHex = text; lampColor.setColor(text) }
      }
      PlainText { text: "Lamp brightness " + root.haBrightness }
      LightingSlider {
        Layout.fillWidth: true
        bar: popupPalette
        scrollView: root
        minimum: 0; maximum: 255; step: 1; integer: true
        value: root.haBrightness
        fillColor: Commons.Color.accent
        knobColor: activeFocus ? Commons.Color.accent : Commons.Color.popups.text
        onMoved: function(value) { root.haBrightness = value }
      }
      Ui.Toggle {
        Layout.fillWidth: true
        label: "Push color to the lamp"
        checked: root.haEnabled
        foreground: Commons.Color.popups.text
        onClicked: { root.haEnabled = !root.haEnabled; parent.sendLamp() }
      }
      Ui.Toggle {
        visible: root.haFollow
        Layout.fillWidth: true
        label: "Also set lamp brightness while following the theme"
        checked: root.haSyncBrightness
        foreground: Commons.Color.popups.text
        onClicked: { root.haSyncBrightness = !root.haSyncBrightness; parent.sendLamp() }
      }
      Ui.Toggle {
        Layout.fillWidth: true
        label: "Only when the light is already on"
        checked: root.haOnlyWhenOn
        foreground: Commons.Color.popups.text
        onClicked: { root.haOnlyWhenOn = !root.haOnlyWhenOn; parent.sendLamp() }
      }
      PlainText {
        Layout.fillWidth: true
        font.pixelSize: Commons.Style.font.caption
        opacity: 0.75
        wrapMode: Text.WordWrap
        text: "While the lamp follows the theme, its own brightness stays unless Also set lamp brightness is on. A chosen color always sends the lamp brightness. An off light is skipped while Only when the light is already on is enabled. The token is never shown."
      }
      RowLayout {
        Layout.fillWidth: true
        Ui.Button {
          Layout.fillWidth: true
          text: "Save lights"
          focusable: true
          foreground: Commons.Color.popups.text
          onClicked: lightingPage.sendLamp()
        }
        Ui.Button {
          Layout.fillWidth: true
          text: "Push color now"
          focusable: true
          foreground: Commons.Color.popups.text
          onClicked: root.service && root.service.request("ha-push")
        }
      }
    }

    ColumnLayout {
      visible: root.tab === "keys"
      Layout.fillWidth: true
      spacing: Commons.Style.space(6)
      Flow {
        Layout.fillWidth: true
        spacing: Commons.Style.space(4)
        Repeater {
          model: root.snapshot.layers || []
          delegate: Ui.Button {
            required property var modelData
            text: modelData.name
            bordered: root.keymapLayer === modelData.id
            focusable: true
            foreground: Commons.Color.popups.text
            onClicked: root.keymapLayer = modelData.id
          }
        }
      }
      PlainText {
        Layout.fillWidth: true
        text: {
          var key = root.selectedKey()
          var current = root.assignment()
          if (!key) return "Choose a key. Layer 0 is Mac, layer 2 is Windows. Linux normally uses the Windows switch."
          var draft = root.service && root.service.drafts[root.keymapLayer + ":" + key.row + ":" + key.col]
          return key.label + "  matrix " + key.row + "," + key.col + "  LED " + key.led + "  " + (draft ? ("pending " + draft.value) : (current ? current.name : "unread"))
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
          text: "Read keymap"
          focusable: true
          foreground: Commons.Color.popups.text
          onClicked: root.service && root.service.request("keymap-load")
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
      PlainText {
        Layout.fillWidth: true
        font.pixelSize: Commons.Style.font.caption
        opacity: 0.75
        text: root.snapshot.backup ? ("Recovery copy " + root.snapshot.backup) : "Click a key on the Air96 picture, search a keycode, then Apply. The picture is the 96% layout, the same idea as the Air75 map in fldc/omarchy-nuphy. Apply writes only staged keys, after a JSON backup."
      }
    }
  }
}
