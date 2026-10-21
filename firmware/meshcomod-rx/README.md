# MeshCoMod + LoRagotchi-RX: Heltec V4 OLED preview

**Prototype, not hardware-qualified.** This is an external, version-locked source
overlay, not an upstream MeshCoMod release or a replacement HACS integration.
Its single build target is `heltec_v4_companion_radio_usb_tcp_lrx` (ESP32-S3,
Heltec V4 **OLED**, 16 MB flash / 2 MB PSRAM board definition). It is intended
for the owner's V4.3 OLED trial; no physical V4.3 radio has been tested here.
Do not use it for TFT, Wireless Paper, V3 or other boards.

## Source provenance

- MeshCoMod companion v1.18.0.1:
  https://github.com/ALLFATHER-BV/meshcomod/commit/8aba438f452dfca5680d1c96b3e643e54f98cef3
- Released LoRagotchi-RX core, firmware-2026.10.20:
  https://github.com/DrToxic/LoRagotchi-RX/commit/49d3900595b85210fc19d8fbe51a829cf68cd726
- Custom version reported by this target: **v1.18.0.1-lrx1**.

Included license copies cover the upstream/RX source in the patch. Dependencies
retain their own licenses in the upstream PlatformIO project. Neither upstream
repository is modified by preparing this overlay in an isolated checkout.

## What changes

The released RX receiver, two-bank verified journal, full-owner binding,
colour metadata, durable upload-before-ACK behavior and automatic original-fish
return are retained. The node has no local pet. It can continue returning fish
when the Aquarium/HA host is offline. A full intake backlog rejects new visits;
it is not infinite storage. Corrupt/unmountable storage fails closed and is
**never auto-formatted** by this target.

Small MeshCoMod hooks receive plain-text LoRagotchi visits, run the RX state
machine, process return ACKs and dispatch LRX/1 commands. Replies use the
existing **origin-specific** `writeFrame` path, not unsolicited broadcast.
Existing USB/TCP/WS/BLE code remains MeshCoMod's. Radio pins, frequency defaults,
partitions, identities and saved Wi-Fi settings are not intentionally changed.
A free channel slot is used for `#loragotchi-dx`; occupied or conflicting private
channels are never overwritten. The existing OLED UI remains MeshCoMod's;
a custom RX queue/status screen is not included.

There is one additional tested history correction: a new client's cursor is
set **before** the oldest retained message. The unpatched baseline skipped that
message. HA and Aquarium keep independent ordinary-chat cursors. LRX still has
exactly one 15-second intake lease; a second Aquarium is rejected. Mandatory
snapshot acknowledgements are not the same thing as general radio-control
permission in the Aquarium UI.

## Reproduce

Use a fresh isolated checkout at the exact baseline (a sparse checkout may omit
`prebuilt` and `bootstrap-backup`; those are not needed for building):

```sh
git clone --no-checkout https://github.com/ALLFATHER-BV/meshcomod.git meshcomod-rx
cd meshcomod-rx
git sparse-checkout set --no-cone '/*' '!/prebuilt/' '!/bootstrap-backup/'
git checkout 8aba438f452dfca5680d1c96b3e643e54f98cef3
cd ..
python3 Aquarium/firmware/meshcomod-rx/prepare.py meshcomod-rx
python3 meshcomod-rx/test/rx/check_aquarium.py Aquarium
python3 Aquarium/firmware/meshcomod-rx/check_multiclient.py meshcomod-rx
pio run -d meshcomod-rx -e heltec_v4_companion_radio_usb_tcp_lrx -j 1
```

Replace `Aquarium` with this checkout's path. `prepare.py` refuses a different
revision or dirty source tree and does not flash/build. The patch is reviewable;
upgrade the baseline deliberately, reapply/review and rerun tests before using
a later MeshCoMod release. It does not automatically follow upstream main.

## Firmware handoff / rollback

The handoff contains **app-only `firmware.bin`**, checksums and the build's
partition table for comparison. No merged erase-and-install image is supplied.
A compiled binary is not proof of RF, Wi-Fi stability, power behavior or HACS
coexistence on the actual radio.

Before a physical trial, confirm exact board, flash capacity, current partition
table and active OTA slot. Take a full-flash backup and preserve the working
MeshCoMod image/settings. This build uses the stock V4 OLED `default_16MB.csv`:
app0 at `0x10000` (size `0x640000`), app1 at `0x650000` (same size), SPIFFS at
`0xc90000`. Those are **this build's** offsets, not verification of the installed
radio. Do not blindly write app0, replace partitions, erase flash or use a
factory-image workflow while preserving a running installation.

Use the existing app-only update route only after compatibility is confirmed.
For rollback, restore the saved compatible MeshCoMod app through the same route;
keep filesystem/NVS data. The stock firmware ignores the new `/lrx-a.dat` and
`/lrx-b.dat` journal files. If identity/settings/storage were damaged, restore
the full-flash backup. A new blank radio requires an explicitly planned initial
filesystem setup; this receiver will not auto-format it.

First physical acceptance: existing HA reconnects; Aquarium connects on another
TCP session; channel chat reaches both; USB remains functional; one actual fish
visit captures/returns with colours; restart Aquarium and radio separately;
saved copy remains and no duplicate appears. Interrupt the PC while the original
returns. Only then promote this prototype to a normal installed release.
