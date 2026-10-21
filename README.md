# LoRagotchi-Aquarium-HA

The Home-Assistant version of the Community Aquarium software for the LoRagotchi-DX firmware.

**Preview 1 · amd64 only · demo mode by default.** The original Python/Panda3D
Aquarium runs in a container and streams to your browser. There is no separate
browser renderer: the aquarium view and full operator controls use the same
native application, graphics, fish and saved collection.

## Install on Home Assistant OS

1. Open **Settings → Apps/Add-ons → Store → ⋮ → Repositories**.
2. Add this repository URL:

   ```text
   https://github.com/DrToxic/LoRagotchi-Aquarium-HA
   ```

3. Refresh the store, open **LoRagotchi Aquarium Preview**, and select **Install**.
   This builds the container locally; the first installation can take several minutes.
4. Keep **mode: demo**, then **Start → Open Web UI**. Optionally enable **Show in sidebar**.
5. Choose **View aquarium** for the view-only stream or **Open controls** for the
   interactive native operator interface.

Requires an Intel/AMD 64-bit (`amd64`) HA host. Raspberry Pi/HA Green ARM builds
are not included. HA supplies authentication; the app is admin-only and does not
publish a host port. Use the sidebar/Web UI first: a persistent Lovelace ingress
card is not included, and temporary ingress URLs are not permanent dashboard links.

If you already installed the local ZIP preview, stop it before starting this
repository-installed copy. They have separate HA app data directories; existing
live data is not automatically migrated. Do not run two live intake consumers.

## Home Assistant Container / Docker

HA Container does not have the Supervisor app store. Run Aquarium as a sibling
container on an amd64 Docker host:

```sh
git clone https://github.com/DrToxic/LoRagotchi-Aquarium-HA.git
cd LoRagotchi-Aquarium-HA
mkdir -p aquarium-data
python3 -c 'import getpass,pathlib; p=pathlib.Path("aquarium-data/web-password"); p.write_text(getpass.getpass("Aquarium password (12+ chars): ")+"\n"); p.chmod(0o600)'
docker compose up -d --build
```

Open `http://127.0.0.1:8099/` **on that host**; username `aquarium`, password as
set above. The default bind is loopback-only. LAN access, HTTPS, dashboard
embedding, persistent data and rollback are covered in the
[installation guide](https://github.com/DrToxic/LoRagotchi-Aquarium-HA/blob/main/docs/HOME_ASSISTANT.md).

## Existing MeshCore / MeshCore Chat integrations

Keep them installed and configured. HA uses one companion TCP connection and
Aquarium uses another to the same radio over WLAN. Browser viewers share the
Aquarium connection. Ordinary Aquarium chat/settings writes default off.

**Stock MeshCoMod does not implement Aquarium fish capture.** Live mode requires
the separate, pinned MeshCoMod + LoRagotchi-RX prototype. Its V4.3 OLED hardware,
installed partition layout and physical HACS coexistence still need validation.
Installing this HA app does not flash or configure your radio. Start with demo.

[Firmware source and prerequisites](https://github.com/DrToxic/LoRagotchi-Aquarium-HA/blob/main/firmware/meshcomod-rx/README.md)

## Verification and preview limits

The underlying preview passed 162 workspace tests; its fresh standalone source
archive passed 160 tests with two optional external-RX checks skipped. Native
graphics, both browser streams, operator input, server-side view-only behavior,
standalone authentication and a simulated Supervisor ingress proxy were checked.
Those are retained preview results, not a claim of physical HA/radio acceptance.

Actual HA installation, physical V4.3 WLAN/USB/RF coexistence, ARM builds,
Lovelace ingress cards and HA sensors remain follow-up work. No prebuilt image
registry, automatic upstream graphics sync or firmware updater is included.

## One graphics source

Root `tank/` and `container/` are the maintained application sources. The
`loragotchi_aquarium/` add-on directory is a **generated build context**, required
so Supervisor can build an app from this repository. Do not edit its copies.

After integrating and testing an update from the
[original Aquarium](https://github.com/DrToxic/LoRagotchi-Aquarium), regenerate:

```sh
python3 tools/sync_ha_repository.py
python3 tools/sync_ha_repository.py --check
```

The checker compares every packaged file against the canonical source. For an
update, also bump `homeassistant/config.yaml.in`'s version before regenerating;
HA then discovers the new version after it is published. Graphics updates are
deliberately integrated and tested, not fetched from a moving branch at runtime.
The original desktop documentation remains in
[docs/DESKTOP.md](https://github.com/DrToxic/LoRagotchi-Aquarium-HA/blob/main/docs/DESKTOP.md).

## Credits

LoRagotchi Aquarium is by DrToxic, for the LoRagotchi-DX firmware by
Robert Rayner / M0YNW. Thanks to Robert and the MeshCore team.

- [LoRagotchi-DX — original project](https://github.com/DarkButterfly85/LoRagotchi-DX)
- [LoRagotchi-DX — DrToxic's fork](https://github.com/DrToxic/LoRagotchi-DX)
- [LoRagotchi-RX](https://github.com/DrToxic/LoRagotchi-RX)

MIT licensed; bundled font and firmware notices remain with their sources.
