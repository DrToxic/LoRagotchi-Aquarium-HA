# Home Assistant preview 1

The **same Python/Panda3D application** is rendered once in a container and
streamed through noVNC. There is no second graphics implementation. `/view/`
is aquarium-only and **server-enforced view-only**; `/control/` is the full
operator desktop. Multiple viewers share one running application and collection.
Closing a browser does not stop intake. Operators share controls; this is not
per-user desktop isolation.

This first preview targets **amd64 Linux**. HAOS and HA Container packaging are
provided; actual Supervisor installation and physical radio coexistence must be
checked on the owner's hardware. ARM64/Pi images are not claimed or published.
No HACS component is installed or replaced, and no radio is automatically flashed.

## Try without a radio

### Home Assistant OS / Supervised

Generate the local-app ZIP from the source checkout:

```sh
python3 tools/package_ha.py loragotchi-ha-local-app.zip
```

Extract `loragotchi_aquarium/` into Home Assistant's `addons` share (usually
`/addons/loragotchi_aquarium` from the SSH app). In Settings → Apps/Add-ons →
Store, refresh/check for updates, open **LoRagotchi Aquarium Preview** under
Local apps, and install. Leave `mode: demo`, then start and open the Web UI.
Select **View aquarium** or **Open controls**. This preview is admin-only.

Supervisor supplies authentication and ingress; port 8099 is not published.
Only its standard ingress proxy (`172.30.32.2`) is accepted by the container.
The UI and WebSockets use relative paths so ingress's session path is preserved.
Use the app's sidebar/Web UI first. A persistent Lovelace embed needs a proper
HA ingress-aware panel/card; do not paste a temporary ingress session URL into
a dashboard. This package does **not** yet include that custom card.

### Home Assistant Container / independent Docker host

Run the Aquarium as a **sibling container**, not inside HA Core. In its checkout:

```sh
mkdir -p aquarium-data
python3 -c 'import getpass,pathlib; p=pathlib.Path("aquarium-data/web-password"); p.write_text(getpass.getpass("Aquarium web password (12+ chars): ")+"\n"); p.chmod(0o600)'
docker compose up -d --build
```

Open `http://127.0.0.1:8099/` on that host; username **aquarium**, password as set.
By default the published port is loopback-only. To reach it from another LAN
machine, change the Compose port binding to your host's LAN IP. Use an existing
HTTPS/auth reverse proxy for normal browser access, especially when HA itself
uses HTTPS (browsers block an HTTP iframe inside HTTPS). Do not expose raw VNC
or the internal WebSocket ports. No unauthenticated standalone mode exists.

For a dashboard, the built-in Webpage card can point at the authenticated
`https://your-aquarium-host/view/`; visit it directly once to authenticate.
Cross-origin Basic authentication in an iframe varies by browser, so an
existing same-origin authenticated proxy is preferable. Full controls remain
at `/control/`. LAN/TLS/proxy configuration belongs to the user's installation;
the package doesn't alter Caddy, DNS, firewall or HA configuration.

## Live mode with the shared MeshCoMod radio

**Stock MeshCoMod cannot supply Aquarium snapshots.** Install/test the explicit
MeshCoMod + LRX prototype separately first; see `firmware/meshcomod-rx/README.md`
in the full source distribution. Do not point an unmodified radio at the
Aquarium expecting full functionality.

HA app options:

```yaml
mode: live
radio_host: 192.168.1.50  # your receiver, not a default discovered radio
radio_port: 5000
radio_control: false
```

Standalone equivalents are `AQUARIUM_MODE`, `AQUARIUM_RADIO_HOST`,
`AQUARIUM_RADIO_PORT`, `AQUARIUM_RADIO_CONTROL`. Restart after changing options.
The native desktop also supports:

```sh
python -m tank --connect meshcore:192.168.1.50:5000
```

Its Connection tab distinguishes **Radio Wi-Fi (MeshCoMod RX)** from
**Network bridge**. `tcp:` still means the original authenticated LRXB bridge;
it never falls back to unprotected radio TCP. Native radio TCP is plaintext
trusted-LAN transport and has no bridge token. Keep its existing LAN protections.

Leave the current HACS MeshCore/Chat configuration in place. HA and Aquarium
use independent companion TCP sessions; MeshCoMod has three TCP client slots.
Use exactly **one** LRX Aquarium intake consumer. Multiple browser viewers
connect to the same Aquarium and do not consume more radio slots. Aquarium
uses a saved client identity so reconnection on another slot preserves its
chat cursor. The firmware's chat history is bounded RAM, not a durable archive.

By default Aquarium cannot send chat or change radio/contact/channel settings
on a direct radio. LRX lease/read/ACK commands and inbox reads still happen;
this is not a passive packet sniffer. Explicit `radio_control: true` (native
`--radio-control`) permits operator writes. Radio settings are global; avoid
editing them concurrently in HA and Aquarium. No command is blindly resent
when its outcome is unknown. The receiver automatically returns original fish;
that return does not depend on HA, a browser or the container being online.

## Storage, updates and rollback

- `/data/share/loragotchi-tank/live.sqlite` holds the live collection and chat.
- `/data/config/loragotchi-tank/` holds graphics settings, layout and connection
  preferences, including the non-secret stable client ID.
- Demo is memory-only and does not contaminate the live collection.
- Stop the app/container before taking a plain file backup of `/data`; include
  SQLite sidecars if any. HA app backup includes its data directory.
- Rebuild both packages from the same accepted source/tag after graphics
  changes. User updates replace the image, not `/data`. This preview adds no
  database migration. Versioned registry publication/automatic update discovery
  is a later release step, not something this local preview silently sets up.
- To roll back, stop, restore the previous image/source, and retain the backup.
  Never erase `/data` just to reinstall. Firmware rollback is separate.

## Scope and practical limits

Default render size is 960×540 at a 20 FPS cap. Both streams show that same
rendering; the operator desktop is 1432×768. Hosted mode has one fixed output;
fullscreen, extra windows and drag/resize remain desktop-only features. Fish,
scenery, graphics presets, chat, radio tabs and masks use the existing native UI.
A browser cannot access arbitrary host paths or local hardware as the desktop
can; package assets and mounted data are available. BLE/USB forwarding is not
configured in this network-first container preview. Mobile input/clipboard may
need additional work; viewing is the primary touch use case.

Xvfb/Mesa currently use software rendering (two worker threads). LAN latency
isn't the only cost: host rendering/encoding and image bandwidth matter. Frame
caps are targets, not measured hardware guarantees. Native text stays sharp;
VNC animation can use substantially more bandwidth than a video codec. GPU or
WebRTC optimization should follow measurements on the actual HA host.

The container supervises the renderer, VNC, WebSockets and web server together;
a component exit stops the stack so the container manager can restart it.
Basic aggregate HA sensors/automations, a Lovelace ingress card, ARM builds,
registry publishing and OTA firmware updates are **not part of preview 1**.
