# LoRagotchi-Aquarium-HA

The Home-Assistant version of the Community Aquarium software for the LoRagotchi-DX firmware.

**Preview 6 · amd64 only · demo mode by default.** The original Python/Panda3D
Aquarium runs in a container and streams to your browser. There is no separate
browser renderer. All add-on settings live in Home Assistant’s Configuration
tab; the native display has no operator window or deadzones.

## Preview 6 appearance controls

Lighting, automatic day/night (clock or HA sun), water backgrounds/fog, sand tint,
effect motion and stable pooled bubble columns are now configurable in HA.
Manual changes use Save + Restart; automatic cycles then run continuously.
See [Appearance](docs/APPEARANCE.md) and [HA setup](docs/HOME_ASSISTANT.md).

## Install on Home Assistant OS

1. Open **Settings → Apps/Add-ons → Store → ⋮ → Repositories**.
2. Add this repository URL:

   ```text
   https://github.com/DrToxic/LoRagotchi-Aquarium-HA
   ```

3. Refresh the store, open **LoRagotchi Aquarium Preview**, and select **Install**.
   This builds the container locally; the first installation can take several minutes.
4. Keep **mode: demo**, then **Start → Open Web UI**. Optionally enable **Show in sidebar**.
5. The aquarium opens directly, with no menu or controls over it. Change graphics,
   names, decorations, animations and
   connection options in the add-on’s **Configuration** tab, then **Save → Restart**.

Requires an Intel/AMD 64-bit (`amd64`) HA host. Raspberry Pi/HA Green ARM builds
are not included. HA supplies authentication; the app is admin-only and does not
publish a host port. For Lovelace, use the YAML below with the separately installed HACS
**Ingress webpage card**. See below;
never save a temporary ingress URL as a permanent dashboard link.

If you already installed the local ZIP preview, stop it before starting this
repository-installed copy. They have separate HA app data directories; existing
live data is not automatically migrated. Do not run two live intake consumers.

## Lovelace dashboard cards

1. Install [Ingress webpage card](https://github.com/lovelylain/ha-addon-iframe-card)
   through HACS and reload your Home Assistant browser page.
2. Open Aquarium's **Info** page in Settings → Apps/Add-ons. Copy its full slug
   from the URL, including the repository prefix.
3. In your dashboard, select **Edit → Add card → Manual**, paste this YAML with
   your installed slug, and save:

```yaml
type: custom:addon-iframe-card
url: YOURPREFIX_loragotchi_aquarium/view/
aspect_ratio: "56.25%"
```

Use `100 × height ÷ width` for the percentage if you changed the output dimensions.
The optional card setup helper remains at the add-on-relative `setup.html` route;
it is not part of the aquarium view.

The default HA Web UI, root ingress cards and `/view/` all show only the aquarium,
with no launcher, toolbar or persistent overlay. New card YAML has no title.
The aquarium card uses the server-enforced view-only stream. Old controls cards
now show that same read-only aquarium. The card handles ingress sessions
using your HA login; no tokens, exposed ports, or saved temporary URLs are needed.
This Supervisor route requires an administrator account. The external card is
installed through HACS, not automatically by Aquarium. All cards display the
same running native application; they do not create another receiver.

See [examples and HACS architecture](docs/HOME_ASSISTANT.md#lovelace-dashboard-cards).

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

**Keep your working radio firmware and HACS integrations.** The recommended
`mode: home_assistant` uses the existing MeshCore integration's supported HA
API. No second radio connection, replacement firmware, Chat fork or extra HACS
component is required. Aquarium owns durable fish capture and return jobs in a
headless process independent of its renderer.

Start with `ha_receive_fish: false` to check the selected node without sending;
then enable it after the identity in the add-on Logs is correct. HAOS uses the built-in
Supervisor authentication. Multiple companions require an explicit
`ha_entry_id`. MeshCore's documented 3.0.3 API contract is required.

```yaml
mode: home_assistant
ha_entry_id: ""
ha_receive_fish: false
```

**HA and the backend must stay online to handle visits and returns.** Browser
closures and renderer restarts do not stop the receiver. Old `mode: live`
remains an optional dedicated MeshCoMod+LRX path, not an HA prerequisite.
See the [setup and recovery guide](docs/HOME_ASSISTANT.md) before a one-fish trial.

## Verification and preview limits

The HA receiver, WebSocket adapter, durable restart handling and native managed
connection panel have local automated/fixture evidence. See
[the exact preview-2 validation boundary](docs/HOME_ASSISTANT.md#verification-boundary-for-preview-2).
A fixture is not Home Assistant or a physical radio. The owner reports preview 2
works on their HA installation. That report does not establish every recovery
or RF case. The owner also confirmed the preview-3 ingress card works.
Preview 4 moved configuration into HA. Preview 5 makes the root Web UI aquarium-only;
the latest update still needs an on-device check.

The HA stream is now entirely read-only, including the old controls route.
ARM builds, a bundled custom card, HA sensors, registry publishing,
automatic upstream graphics sync and firmware updating remain outside this preview.

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
