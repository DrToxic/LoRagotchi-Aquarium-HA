# Home Assistant preview 3

The **same Python/Panda3D application** is rendered once in a container and
streamed through noVNC. There is no second graphics implementation. `/view/`
is aquarium-only and **server-enforced view-only**; `/control/` is the full
operator desktop. Multiple viewers share one running application and collection.
Closing a browser does not stop intake. Operators share controls; this is not
per-user desktop isolation.

This preview targets **amd64 Linux**. HAOS and HA Container packaging are
provided; actual Supervisor installation and physical radio coexistence must be
checked on the owner's hardware. ARM64/Pi images are not claimed or published.
No HACS component is automatically installed or replaced, and no radio is
automatically flashed. Optional dashboard embedding uses a separate HACS card.

## Try without a radio

### Home Assistant OS / Supervised — repository install

Open Settings → Apps/Add-ons → Store → ⋮ → Repositories and add:

```text
https://github.com/DrToxic/LoRagotchi-Aquarium-HA
```

Refresh the store, install **LoRagotchi Aquarium Preview**, keep `mode: demo`,
then start and open the Web UI. The first install builds the image locally.
Enable Show in sidebar if desired. This is an HA app repository, not a HACS
repository. Only amd64 is supported in this preview.

If an earlier local ZIP copy is installed, stop it before starting this copy.
Repository and local installations have separate data directories: live data
does not migrate automatically. Do not run two live intake consumers.

### Local ZIP alternative

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
Use **Web UI → Dashboard cards** for ingress-aware Lovelace configurations, as
described below. Do not paste a temporary ingress URL into a dashboard.

## Lovelace dashboard cards

Preview 3 includes a **Dashboard cards** setup page in the add-on Web UI. It
supplies copyable configurations, not a new renderer or an automatically
installed dashboard resource. Reuse the open-source
[Ingress webpage card](https://github.com/lovelylain/ha-addon-iframe-card), which
resolves the installed add-on slug and creates/renews ingress sessions.

1. Install **Ingress webpage card** from HACS. If necessary, add
   `https://github.com/lovelylain/ha-addon-iframe-card` as a custom **Dashboard**
   repository, then download it. Reload your HA browser page after installation.
2. Open Aquarium's **Info** page in Settings → Apps/Add-ons. Its address has the
   form `/hassio/addon/REPOSITORYPREFIX_loragotchi_aquarium/info`.
3. Open Aquarium's Web UI → **Dashboard cards**, paste that Info URL or full
   slug, and copy the desired YAML. The repository prefix varies with how the
   app was installed; do not copy `loragotchi_aquarium` alone.
4. Open your dashboard → Edit → Add card → Manual. Paste the YAML and save.

For example, replace `YOURPREFIX_loragotchi_aquarium` with your installed slug:

```yaml
type: custom:addon-iframe-card
title: Aquarium
url: YOURPREFIX_loragotchi_aquarium/view/
aspect_ratio: "56.25%"
```

Optional full operator desktop:

```yaml
type: custom:addon-iframe-card
title: Aquarium controls
url: YOURPREFIX_loragotchi_aquarium/control/
aspect_ratio: "53.63%"
```

These ratios match the default 960×540 scene and 1432×768 operator desktop.
Change the ratio if you change the render size. Use a wide section or a panel
view for the operator card. All viewers share one aquarium and collection;
multiple operator cards share the same controls. The view-only endpoint rejects
input at the server, but is not a separate guest-access permission model.

This route requires **HAOS/Supervisor and an HA administrator account**. A plain
Webpage card cannot renew Supervisor ingress authentication by itself. Do not
paste temporary `/api/hassio_ingress/...` URLs or credentials into YAML. No host
port, long-lived token, or changes to MeshCore/Chat are needed for these cards.

If HA says `Custom element doesn't exist: addon-iframe-card`, check the HACS
installation/resource and reload the browser. If add-on lookup fails, verify
the complete slug and administrator login. If the aquarium says Disconnected
after an app restart, reload the dashboard. Preview 3 retains the existing
stream reconnect behavior; the setup page does not add transparent VNC recovery.

The setup page is checked locally in Chromium at root and nested ingress-style
paths, including clipboard fallback. Actual Lovelace, HA Companion apps and
Supervisor session renewal still require a test on the installed HA host.

### Could the Aquarium become a HACS integration?

HACS distributes custom integrations and dashboard resources, not this
Supervisor app's OS container. The current Aquarium needs Panda3D, Xvfb, VNC,
websockify and nginx; copying Python files into HA Core does not supply that
runtime. Keep these processes outside HA Core.

A **hybrid** is the practical extension: retain the app/container for rendering,
SQLite and durable fish returns; add a HACS companion integration/card for
entities, status, actions and a polished dashboard. This would need a supported,
authenticated backend API and integration lifecycle work; it is not implemented
in preview 3. The generic ingress card above already handles visual embedding.

A **HACS-only** product without a separate runtime is possible only with a
substantial redesign, such as a browser renderer plus a properly asynchronous
HA integration for fish handling/storage. It is not a packaging conversion and
would diverge from this project's single native graphics implementation.

## Home Assistant Container / independent Docker host

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

## Recommended: reuse the existing Home Assistant MeshCore connection

**No radio firmware replacement. No extra HACS integration.** MeshCore remains
sole owner of the radio connection; MeshCore Chat stays installed and unchanged.
Aquarium listens for ordinary `LFG1` direct messages through HA's supported API
and runs the fish receiver in its own headless process. It never opens a radio
socket in this mode. The native aquarium renderer and assets are unchanged.

The supported contract was reviewed against **meshcore-ha 3.0.3**
(`meshcore-dev/meshcore-ha`). Older integrations without `get_contacts`, stable
send events or the Companion Prefix sensor are not supported. Different forks
must provide that same contract. This is not a version test of your installation.

### HAOS: first verify the connection without sending

After installing/updating this preview, set these app Configuration options,
then Save and Restart:

```yaml
mode: home_assistant
ha_entry_id: ""
ha_receive_fish: false
```

Open **Controls → Radio → Connection**. It should show **HA MeshCore connected ·
read-only diagnostics**, the companion key prefix and entry ID. A single
MeshCore companion is selected automatically. If multiple companions exist,
the status/log lists entry IDs: copy the intended one into `ha_entry_id` and
restart. The Companion Prefix sensor must be enabled and available; entity
renaming is supported. No ordinary name, channel, RF or radio setting changes
are made. `radio_host`, `radio_port` and `radio_control` are unused in HA mode.

The app manifest requests `homeassistant_api: true`. HAOS supplies its injected
Supervisor token internally; **do not enter or share that token**. It is not
passed to the renderer/browser, logged, or saved in the application database.

### Enable fish visits

After the displayed node is correct, set **`ha_receive_fish: true`** and restart.
That permits only the receiver's automated `ACK`, `BUSY`, `ARRIVED` and `RETURN`
DM replies. Chat, contacts and all radio settings remain in MeshCore/Chat.

- Use ordinary compatible MeshCore/MeshCoMod companion firmware. Do **not** run
  this host receiver against a radio already handling LFG1 in RX/DX firmware,
  or run a second Aquarium receiver against the same HA entry. HA's API has no
  cross-application exclusive receiver lease. Within one database a process lock
  prevents two backend writers, and the original entry + full radio key are pinned.
- Save the visiting DX node as a companion contact on the HA radio; also save
  the HA radio on the visiting node. A discovered-only or ambiguous contact is
  refused. Names are not identities. Unknown routes can still fail on air.
- Current DX's destination picker requires a fish emoji (`🐟`, `🐠`, `🐡`, `🦈`)
  in the destination's advertised name. If needed, change the normal node name
  using your existing controls and refresh its advert/contact. Aquarium does
  not rename it automatically.
- The backend accepts four outstanding reservations/captured visits, uses a
  non-renewing five-minute reservation, atomically saves the copy before
  `ARRIVED`, then schedules `RETURN ... |C|AQUARIUM1` after a short hold.
  Return timing also respects pending HA send outcomes; four seconds is not a
  radio-delivery guarantee. Cancellation before capture uses `CANCEL1` and
  never claims a successful aquarium copy.
- Return jobs survive restart. The panel shows pending/unresolved counts and
  **Retry unresolved returns** re-arms exhausted return jobs only. Automatic
  send attempts are bounded at four; a call with no conclusive delivery event
  waits up to five minutes before paced retry. HA traffic policy is not bypassed.
- A radio ACK means **radio-delivery confirmed**, not application-level HOME
  confirmation. Check the sending DX fish returned during the first test.
- Removing a displayed copy or ending a display session never deletes pending
  returns. A renderer/VNC/web failure restarts the presentation independently;
  closing browsers does not affect the backend.
- **HA and the Aquarium backend must stay running.** Stopping the app, switching
  to demo/read-only/direct mode, or disabling intake suspends processing and
  replies, including saved pending returns. Restore HA mode with intake enabled
  to resume. Don't switch modes with pending visits unless intentionally pausing.
- HA events are live notifications, **not a replayable inbox**. Missed requests
  need sender protocol retry; Chat history is not replayed into the receiver.
  A sender reboot may clear its travel state. Do not promise lossless offline
  operation. Chat can display the LFG1 exchanges as ordinary DMs.
- Tombstones are retained to prevent stale COMMITs from recreating visits.
  New reservations stop at 10,000 retained transaction records per database;
  `journal-full` appears in the log/panel. Do not delete the journal while returns
  are pending. Automatic archival is deliberately not included in this preview.

### HA Container authentication

Keep Aquarium as a sibling container. Create a long-lived access token for a
local HA administrator, put it in `aquarium-data/ha-token` with mode `0600`,
and configure Compose environment values:

```yaml
AQUARIUM_MODE: home_assistant
AQUARIUM_HA_URL: http://your-ha-host:8123
AQUARIUM_HA_TOKEN_FILE: /data/ha-token
AQUARIUM_HA_ENTRY_ID: ""
AQUARIUM_HA_RECEIVE_FISH: "false"
```

Use the HA host's reachable name/address, not `localhost` inside Aquarium's
container. Use HTTPS when connecting outside a trusted local network. The token
is separate from Aquarium's web password. Keep it out of Git and URLs. Validate
read-only diagnostics, then set the receive flag to `"true"` and restart.

## Optional dedicated firmware receiver (legacy live mode)

`mode: live` retains the original direct MeshCoMod+LRX connection for a dedicated
receiver. **This optional mode still needs the explicit receiver extension**;
stock MeshCoMod cannot answer its LRX commands. The new recommended HA mode above
does not use those commands and does not need that firmware. Do not select both
receiver implementations for the same radio.

```yaml
mode: live
radio_host: 192.168.1.50
radio_port: 5000
radio_control: false
```

See `firmware/meshcomod-rx/README.md` in the full source for the separately tested
prototype and outstanding hardware/partition checks. Direct native
`meshcore:HOST:PORT`, USB/BLE RX and authenticated `tcp:` bridge support remain
unchanged. The latter is not unprotected radio TCP. Leave radio_control off
unless deliberately granting chat/configuration writes. Firmware-owned returns
in that optional mode do not require HA or the renderer to stay running.

## Storage, updates and rollback

- `/data/share/loragotchi-tank/ha-live.sqlite` holds the HA collection, full-key
  identity pin, reservations, tombstones and durable reply/return jobs.
- `/data/share/loragotchi-tank/live.sqlite` retains the separate direct-RX
  collection/chat. Preview 2 does not silently merge or delete either source.
- `/data/config/loragotchi-tank/` holds graphics settings, layout and connection
  preferences, including the non-secret stable client ID.
- Demo is memory-only and does not contaminate the live collection.
- Stop the app/container before taking a plain file backup of `/data`; include
  SQLite sidecars if any. HA app backup includes its data directory.
- After testing graphics changes, bump the version in
  `homeassistant/config.yaml.in`, run `python3 tools/sync_ha_repository.py`,
  and commit/publish the generated app context alongside its canonical source.
  `python3 tools/sync_ha_repository.py --check` detects packaging drift.
  HA can discover published app version changes through its repository refresh;
  each update builds locally. There is no prebuilt registry or automatic merge
  of future desktop changes. Updates replace the image, not `/data`; this
  preview creates additive HA tables in its separate live store; legacy data is preserved.
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

The container restarts the renderer/VNC/WebSocket/web presentation together on
a display failure. The HA receiver has its own supervised process and is not
stopped by a display restart. Backend failure is retried separately; accepted
work resumes from the journal. The entire container/HA stopping still interrupts
processing, and the HTTP health check describes presentation health only.
Basic aggregate HA sensors/automations, a bundled custom card, ARM builds,
registry publishing and OTA firmware updates are **not part of preview 3**.
Lovelace embedding uses the separate HACS Ingress webpage card described above.


## Verification boundary for preview 2

Automated receiver tests cover malformed messages, full identity binding,
capacity, reservation expiry, duplicate/reordered messages, storage rollback,
short appearance preservation, bounded unknown outcomes, restart and return
recovery. A real TCP/WebSocket **HA API fixture** checks authentication,
subscriptions, early send events, silent services, concurrent Chat listeners and
reconnect. A subprocess test kills the renderer client and backend, then verifies
captured state and return recovery; the native Panda3D panel is also exercised.
These are host/fixture results, **not** an actual Supervisor or physical RF trial.

Local container/browser checks qualify the packaged process and access boundary,
not Supervisor itself. Actual HAOS installation/token access and a controlled
one-fish trial remain required before calling the new integration hardware-proven.
