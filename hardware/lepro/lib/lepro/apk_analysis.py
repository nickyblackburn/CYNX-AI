#!/usr/bin/env python3
"""
APK / native analysis notes for Path B (offline reference).

Sources: Lepro_1.0.9.258_APKPure.xapk, tmp/libiot-core.so, tmp/libapp.so, Ghidra.
"""

from __future__ import annotations

# ── Java / Kotlin (classes.dex … classes5.dex) ───────────────────────────────

JAVA_IOT_NATIVE = "com.lepro.iot_native.IOTNativeUtil"

JNI_METHODS = (
    "bleInit",
    "bleSearchDeviceInfo",
    "bleSearchDeviceInfoV2",
    "bleRequestBond",
    "bleGetDpState",
    "bleDpValue",
    "bleGetDeviceState",
    "bleGetApInfo",
    "bleSendWifiMqttInfo",
    "bleQuitOnboardingMode",
    "bleOTAStart",
    "bleOTAProcess",
    "bleCmdReceive",
)

# Flutter/Kotlin callbacks invoked from native postJni* functions
NATIVE_TO_APP_CALLBACKS = (
    "processRevLeDeviceBondState",
    "processRevLeDeviceUnBondState",
    "processRevLeDeviceInfo",
    "processRevLeDeviceState",
    "processRevLeDeviceDpPRPGetResponse",
    "processRevLeDeviceDpPrpSetResponse",
    "processRevLeDeviceDpPrpReport",
    "processRevLeDeviceWiFiApInfo",
    "processRevLeDeviceWiFiMQTTSetResponse",
    "processRevLeDeviceLogReport",
    "processRevLeDeviceQuitOnboardingMode",
    "processRevLeDevImgResponse",
    "processRevLeDevImgData",
    "processRevLeDevImgDataResult",
    "processRevLeDeviceOTAStartReqResponse",
    "processRevLeDeviceOTADataResponse",
)

# ── libiot-core.so native opcodes (Ghidra) ───────────────────────────────────

NATIVE_OPCODES = {
    0x1000: "searchDeviceInfo",
    0x1001: "deviceInfoResponse",
    0x1002: "requestBond",
    0x1003: "bondResponse",
    0x1100: "dpValue",
    0x1101: "dpValueAck",
    0x1102: "getDpState / raw auth tokens",
    0x1103: "dpResponse",
    0x2000: "certConfig",
}

# Kotlin/Dart layer (com.lepro.home.apk classes.dex … classes5.dex):
#   IOTNativeUtil.bleInit, bleSearchDeviceInfo, bleRequestBond, bleGetDpState, bleDpValue
#   processRevLeDeviceBondState(mac, ackSn, result) — token persistence in Flutter
#   onRevLeDevBondState — bond callback handler
# Auth tokens are opaque blobs stored by Flutter after bond; sent raw on 0x1102.

BOND_SUCCESS = 0

# DP JSON wire bodies (jadx: TestProvisioningActivity, DpSwitchLedValue, DpColourValue)
DP_JSON_EXAMPLES = {
    "power_on": '{"d1":1}',
    "power_off": '{"d1":0}',
    "get_dp_state": '["d1","d2","d3","d4","d5"]',
    "color_hsv": '{"d1":1,"d2":1,"d3":1000,"d5":"HHHHSSSSVVVV"}',
}
# bleDpValue()/bleGetDpState() encrypt json_text + NUL with MAC key + MAIN_IV.
# Kotlin only iterates LeMsgBufList; multi-page TX is native-side for large ciphertext.

# Fancy modes (see modes.py):
#   d2=0 white (d3,d4), d2=1 color (d5), d2=2 scene (d50 RGB-IC or d6 legacy bulb), d2=3 music
#   ZB1 string: d50 + d52 (+ d53 neon_length); NOT TB1 196-LED topology.

# ── ZB1 (RGBIC_LIGHT_ZB1) — APK-validated mode catalog ───────────────────────
# Sources: AIOTSeriesType.java, MqttConnectionPool.java, Dp2WorkMode.java,
#   DpStatusData.java, DpRGBicValue.java, DpRGBICMusicParams.java,
#   SmartCommonLightActivity.java, PaletteRgbcwFragment.java,
#   PaletteDIYZBStringFragment.java, PaletteWarmWhiteFragment.java,
#   LightDiyModeAdapter.java, SceneEntityKt.java, BasicEffectBulbLampAdapter.java

ZB1_SERIES = "ZB1"

# ZB1 grouped with STV1/PG1 in DetectLightList (AIOTSeriesType.Companion f10093n)
# → length detect (LengthDetect), PaletteDIYZBStringFragment, neonlight effect class

ZB1_STATUS_QUERY = (
    "online",
    "d1",
    "d2",
    "d3",
    "d4",
    "d5",
    "d50",
    "d52",
)  # MqttConnectionPool.java — ZB1 branch; d53 not in this ble query list

# DpStatusData @SerializedName map (all fields the app understands):
DP_FIELDS = {
    "d1": "switch_led (power)",
    "d2": "work_mode (Dp2WorkMode 0–3)",
    "d3": "bright_value",
    "d4": "temp_value (CCT)",
    "d5": "colour_data (12-char HSV)",
    "d50": "neon_effect (RGB-IC d50 DSL string)",
    "d52": "neon_bright (scene brightness 100–1000)",
    "d53": "neon_length (bulb count; ZB1 default 15 in PaletteWarmWhiteFragment)",
    "d6": "legacy bulb scene blob (smartbulb path — not ZB1 primary)",
    "d60": "music params (DpRGBICMusicParams, d2=3)",
    "d61": "music effect id (optional)",
    "d15": "dpGroup (trace metadata)",
    "d29": "dpFlag",
    "d30": "trace",
}

# Four firmware work modes (Dp2WorkMode.java) — same for ZB1 as all LP lights:
WORK_MODES_APK = {
    0: ("WHITE", '{"d1":1,"d2":0,"d3":…,"d4":…}'),
    1: ("COLOR", '{"d1":1,"d2":1,"d3":…,"d5":"HHHHSSSSVVVV"}'),
    2: ("SCENE", '{"d1":1,"d2":2,"d50":"N01:…","d52":…} via DpRGBicValue'),
    3: ("MUSIC", '{"d1":1,"d2":3,"d60":"…","d61":…} via DpRGBICMusicParams'),
}

# App UI tabs for ZB1 (SmartCommonLightActivity + PaletteRgbcwFragment):
#   • Warm white  → PaletteWarmWhiteFragment (DIY d50 on warm palette)
#   • Color       → PaletteRgbFragment (d2=1)
#   • DIY string  → PaletteDIYZBStringFragment (per-bulb d50, d53 layout)
#   • Scenes      → SavedEffectsFragment (cloud EffectEntity.res → d50)
#   • Music       → MusicSyncRGBICFragment (device effect=neonlight → d60/d61)
#   • AI home     → LightAiHomeFragment (voice/photo effects — server-driven)

# DIY animation types (LightDiyModeAdapter.java type ids → d50 via native diyValue / diyValueCenterSide):
DIY_EFFECT_TYPES_APK = {
    1: "Steady",
    2: "Breathe",
    3: "Rightward",
    4: "Leftward",
    5: "Gradient",
    7: "Circle",
    # Type 9: diyValue case 9 — U3F300101E2{speed}; NO F21 length segment (libiot-core.so @ 0x1766d4)
    9: "Flash",
    # Types 12/13: diyValueCenterSide — #V:02 envelope + #I00/#I01 (libiot-core.so @ 0x176160)
    12: "CenterOut",  # sides→center; #I00=U3V300264, #I01=U3V300164
    13: "CenterIn",  # center→sides; #I00=U3V300164, #I01=U3V300264
}

# Native-only types (diyValue switch cases 10/11: E1R302011 / E1R302111) — no LightDiyModeAdapter entry
DIY_EFFECT_TYPES_NATIVE_ONLY = {
    10: "RightwardR30",  # not exposed on ZB1 UI
    11: "RightwardR31",  # not exposed on ZB1 UI
}

# Which ZB1 app fragment exposes each DIY effect (for live validation)
DIY_EFFECT_UI_ZB1 = {
    1: "PaletteDIYZBStringFragment (DIY tab)",
    2: "PaletteDIYZBStringFragment",
    3: "PaletteDIYZBStringFragment",
    4: "PaletteDIYZBStringFragment",
    5: "PaletteDIYZBStringFragment",
    7: "PaletteDIYZBStringFragment",
    9: "PaletteWarmWhiteFragment (warm white tab; initNewEffectItem, lightMode=2 in app)",
    12: "PaletteDoodle2Fragment (Doodle2 tab; getDiyTypeCenterSideMessage)",
    13: "PaletteDoodle2Fragment",
}

# d50 format notes from Ghidra decompile of libiot-core.so (tmp/libiot-core.so)
DIY_D50_NATIVE_FORMAT = {
    "flat": "N01:P1000{N}{colors}F21000{G}{lengths}U3V3{tail};  # types 1–7",
    "flash_9_diy": "N01:P10001{RGB6}U3F300101E2{speed:04X};  # no F21; lightMode=1",
    "flash_9_warm": "N01:P3…0000U3F300101E2{speed:04X};  # warm white; lightMode=2",
    "center_12_13": (
        "#V:02{ic1:02X}{all:02X}00000000{ic2:02X}00000000;"
        "#I00:N01:P1…U3V3{tail1}{speed:04X}E1;"
        "#I01:N01:P1…U3V3{tail2}{speed:04X}E1;"
    ),
}

# ZB1 bulb layout for d50 (PaletteWarmWhiteFragment.m14456t2):
#   C8031h(neon_length, 1, neon_length, 3, neon_length/3) — default length 15

# Cloud scenes (NOT in APK assets): SceneEntity.neonLight EffectEntity.res, dpType "d50"
#   Downloaded via RemoteDataSource.configEffect(); play sends DpRGBicValue(d2=2,d50,d52)

# Built-in d6 scenes (BasicEffectBulbLampAdapter) — smartbulb/music-bulb path only:
#   gradient + rainbow on d6. ZB1 product config uses effect=neonlight, not smartbulb.
#   modes.py includes these as reference; live ZB1 validation still needed.

# BLE OTA start JSON (FUN_42008eb0 flat parser — Ghidra on ZB1 v2.3.18 ELF):
OTA_START_JSON_FIELDS = {
    "version": "e.g. 2.3.19 (must differ from running fw when do_check=1)",
    "hash": "MD5 hex of image",
    "path": "CDN-relative path, e.g. pub/ota/3_le_light_zb1_pid_55_v2.3.18.bin",
    "size": 'firmware byte count as string, e.g. "1008368" (NOT a JSON number)',
    "secret": "cloud OTA secret; empty string for local BLE flash",
    "do_check": "optional JSON number, default 1",
    "fwType": "optional product type string (max 16 chars)",
}
OTA_START_JSON_EXAMPLE = (
    '{"version":"2.3.19","hash":"<md5>","path":"pub/ota/3_le_light_zb1_pid_55_v2.3.18.bin",'
    '"size":"1008368","secret":""}'
)

# Implementation coverage in lepro-local (Path B client):
ZB1_CLIENT_COVERAGE = {
    "bond_auth_dp": "implemented",
    "d1_on_off": "implemented",
    "d2_0_white": "implemented (white_mode)",
    "d2_1_color": "implemented (color_hsv)",
    "d2_2_d50_diy_6_effects": "implemented (diy_solid; APK types 1–7)",
    "d2_2_d50_per_bulb": "partial (build_d50_from_leds; no UI paint path)",
    "d2_2_cloud_scenes": "missing (need EffectEntity.res capture)",
    "d2_2_diy_types_12_13": "implemented (build_d50_center_solid; APK types 12/13)",
    "d2_2_flash_9": "implemented (build_d50_flash; APK type 9)",
    "d2_3_music_d60": "missing (mic + DpRGBICMusicParams)",
    "d53_length_detect": "missing (LengthDetect native)",
    "d6_gradient_rainbow": "implemented but APK path unverified on ZB1",
    "tb1_presets": "wrong device — reference only",
    "ble_ota": "implemented (ota.py — 0x1010/0x1012)",
}

# ── Control session order (captures.log [11:17:12]–[11:17:38]) ─────────────────

CONTROL_SESSION_ORDER = (
    "TX 0x1000 searchDeviceInfo (encrypt_search_hello, 32B)",
    "RX 0x1001 device info (80B)",
    "RX 0x2000 cert/config (may fragment)",
    "TX 0x1102 CMD_HS (16B raw)",
    "RX 0x1003 or 0x1103 LIGHT_ACK / auth response",
    "TX 0x1102 CMD_AUTH_32 (32B raw)",
    "RX 0x1103 (64B)",
    "TX 0x1100 dpValue pages (encrypt_dp_json)",
    "RX 0x1101 ACK per page",
    "TX 0x1102 CMD_AUTH_16 + CMD_AUTH_32",
    "TX 0x1102 CMD_CTRL_C / CMD_CTRL_D alternating",
    "RX 0x1103 commit responses",
)

# Token field names in ~/.lepro/<mac>.json (also ESP32 NVS keys)
TOKEN_FIELDS = ("hs", "auth_16", "auth_32", "ctrl_c", "ctrl_d")

if __name__ == "__main__":
    print("IOTNativeUtil JNI:", ", ".join(JNI_METHODS))
    print("\nBond → app callback:", "processRevLeDeviceBondState(mac, ackSn, result)")
    print(f"\nZB1 status query: {list(ZB1_STATUS_QUERY)}")
    print("\nWork modes (d2):", ", ".join(f"{k}={v[0]}" for k, v in WORK_MODES_APK.items()))
    print("\nDIY effect type ids:", DIY_EFFECT_TYPES_APK)
    print("\nClient coverage:")
    for k, v in ZB1_CLIENT_COVERAGE.items():
        print(f"  {k}: {v}")
    print("\nControl session:")
    for i, step in enumerate(CONTROL_SESSION_ORDER, 1):
        print(f"  {i}. {step}")
