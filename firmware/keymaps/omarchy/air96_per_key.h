// Copyright 2026 Patrik Hallgren
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#define AIR96_CMD_PROBE 0xA6
#define AIR96_CMD_SET 0xA7
#define AIR96_CMD_CLEAR 0xA8
#define AIR96_CMD_MODS 0xA9
#define AIR96_PER_KEY_VERSION 1
#define AIR96_PER_KEY_KEYS 100
#define AIR96_PER_KEY_LEDS_PER_PACKET 9
#define AIR96_PER_KEY_TIMEOUT_MS 2000
#define AIR96_PER_KEY_FLAG_TIMEOUT 0x01
// Bit 1 used to mean "the keymap paints every basic key while Super is held".
// That mask is gone. The bit stays defined so an old host does not read a new flag.
#define AIR96_PER_KEY_FLAG_SUPER 0x02
#define AIR96_PER_KEY_FLAG_CLEAR 0x04
