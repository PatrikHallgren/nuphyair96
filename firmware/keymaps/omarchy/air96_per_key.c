// Copyright 2026 Patrik Hallgren
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Host per-key overlay for the Air96 V2. Included from keymap.c so it is part
// of that translation unit.
//
// QMK's via.c declares a weak `bool via_command_kb`. If it returns true, QMK
// assumes this function already called raw_hid_send and does not send a reply.
// A `void` definition still links (the prototype is not in via.h). The caller
// then reads a leftover register as true, so every report, including the VIA
// version query, is accepted and never answered. Return false for anything
// this keymap does not own.

#include "air96_per_key.h"
#include "raw_hid.h"
#include "user_kb.h"
#include "via.h"

static uint8_t host_led[AIR96_PER_KEY_KEYS][3];
static bool host_active = false;
static uint32_t host_ms = 0;

static bool magic_ok(const uint8_t *data) {
    return data[1] == 'A' && data[2] == '9' && data[3] == '6' && data[4] == 'K';
}

// user_kb.h defines USB_ACTIVE as a link-and-charge expression and that macro
// also hides the ChibiOS USB_ACTIVE enumerator. Compare the fields directly.
static bool link_is_usb(void) {
    return dev_info.link_mode == LINK_USB && USB_DRIVER.state != USB_SUSPENDED;
}

static void host_clear(void) {
    host_active = false;
}

static void host_refresh(void) {
    if (!link_is_usb()) {
        host_clear();
        return;
    }
    host_active = true;
    host_ms = timer_read32();
    if (!rgb_matrix_is_enabled()) {
        rgb_matrix_enable_noeeprom();
    }
}

static void paint_host(void) {
    for (uint8_t index = 0; index < AIR96_PER_KEY_KEYS; index++) {
        rgb_matrix_set_color(index, host_led[index][0], host_led[index][1], host_led[index][2]);
    }
}

// Hyprland's modmask: shift 1, ctrl 4, alt 8, super 64. The host uses this
// with hyprctl's bind list. Lighting every non-modifier key while Super is
// held does not match those binds, and it ignores Shift, Ctrl, and Alt.
static uint8_t hypr_modmask(void) {
    uint8_t mods = get_mods() | get_oneshot_mods();
    uint8_t mask = 0;
    if (mods & MOD_MASK_SHIFT) {
        mask |= 1;
    }
    if (mods & MOD_MASK_CTRL) {
        mask |= 4;
    }
    if (mods & MOD_MASK_ALT) {
        mask |= 8;
    }
    if (mods & MOD_MASK_GUI) {
        mask |= 64;
    }
    return mask;
}

static bool command_probe(uint8_t *data) {
    if (!magic_ok(data)) {
        return false;
    }
    if (data[5] == 0) {
        host_clear();
    } else if (host_active) {
        host_ms = timer_read32();
    }
    data[0] = AIR96_CMD_PROBE;
    data[1] = 'A';
    data[2] = '9';
    data[3] = '6';
    data[4] = 'K';
    data[5] = AIR96_PER_KEY_VERSION;
    data[6] = AIR96_PER_KEY_KEYS;
    data[7] = AIR96_PER_KEY_LEDS_PER_PACKET;
    data[8] = AIR96_PER_KEY_FLAG_TIMEOUT | AIR96_PER_KEY_FLAG_CLEAR;
    data[9] = (AIR96_PER_KEY_TIMEOUT_MS >> 8) & 0xFF;
    data[10] = AIR96_PER_KEY_TIMEOUT_MS & 0xFF;
    return true;
}

static bool command_set(uint8_t *data, uint8_t length) {
    uint8_t offset = data[1];
    uint8_t count = data[2];
    if (count < 1 || count > AIR96_PER_KEY_LEDS_PER_PACKET || (uint16_t)3 + (uint16_t)count * 3 > length) {
        return false;
    }
    if (link_is_usb()) {
        for (uint8_t index = 0; index < count; index++) {
            uint8_t led = offset + index;
            if (led >= AIR96_PER_KEY_KEYS) {
                continue;
            }
            uint8_t base = 3 + index * 3;
            host_led[led][0] = data[base];
            host_led[led][1] = data[base + 1];
            host_led[led][2] = data[base + 2];
        }
        host_refresh();
    } else {
        host_clear();
    }
    return true;
}

static bool command_mods(uint8_t *data) {
    if (!magic_ok(data)) {
        return false;
    }
    data[0] = AIR96_CMD_MODS;
    data[5] = hypr_modmask();
    data[6] = get_mods() | get_oneshot_mods();
    return true;
}

static bool command_clear(uint8_t *data) {
    if (!magic_ok(data)) {
        return false;
    }
    host_clear();
    return true;
}

bool via_command_kb(uint8_t *data, uint8_t length) {
    bool handled = false;
    if (length < 6) {
        return false;
    }
    if (data[0] == AIR96_CMD_PROBE) {
        handled = command_probe(data);
    } else if (data[0] == AIR96_CMD_SET) {
        handled = command_set(data, length);
    } else if (data[0] == AIR96_CMD_CLEAR) {
        handled = command_clear(data);
    } else if (data[0] == AIR96_CMD_MODS) {
        handled = command_mods(data);
    } else {
        return false;
    }
    if (!handled) {
        return false;
    }
    raw_hid_send(data, length);
    return true;
}

bool rgb_matrix_indicators_user(void) {
    if (!host_active) {
        return false;
    }
    paint_host();
    return true;
}

void matrix_scan_user(void) {
    if (!host_active) {
        return;
    }
    if (!link_is_usb() || timer_elapsed32(host_ms) > AIR96_PER_KEY_TIMEOUT_MS) {
        host_clear();
    }
}
