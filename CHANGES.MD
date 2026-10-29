# Changes

This file preserves the feature and preview notes previously in the README. The release history below is a snapshot of the authoritative [HA changelog](homeassistant/CHANGELOG.md) (also included in the generated app as `CHANGELOG.md`); update that source first when recording a release. Current setup and operation remain in the [README](README.md).

## Native controls

The optional desktop operator now opens at 1100×800 with a persistent sidebar,
readable pixel-sized controls and scrollable smaller-window layouts. See
[Controls and save scopes](docs/CONTROLS.md) for appearance drafts, previews,
separate save actions and the feature map. Home Assistant managed mode remains
display-only and continues to use HA Configuration, not this operator.

## Tidal Garden default scenery

Tidal Garden is now the default native reef with shaded animated seagrass.
Choose `classic` under Configuration → Scenery style to use the original scene,
then Save + Restart. [Scenery controls](docs/SCENERY.md).

## Themes and fish styles

Six built-in themes, persistent editable custom themes, JSON import/export, and
Classic/Rounded/Faceted fish styles. See [Themes](docs/THEMES.md) for controls,
HA configuration authority and the portable data-only format.


## Preview 7 configurable fish lifespan

Configuration → **Fish lifespan (hours)**: `0` is off (default), `24` is a day,
`168` is a week. Save + Restart. New shares renew copies; duplicate packets and
restarts do not. Expiry animates departures while preserving history and pending
radio returns. [Behavior and testing](docs/FISH-LIFESPAN.md).

## Preview 6 appearance controls

Lighting, automatic day/night (clock or HA sun), water backgrounds/fog, sand tint,
effect motion and stable pooled bubble columns are now configurable in HA.
Manual changes use Save + Restart; automatic cycles then run continuously.
See [Appearance](docs/APPEARANCE.md) and [HA setup](docs/HOME_ASSISTANT.md).

## Tidal Garden graphics

Tidal Garden is now the default scenery, including shaded animated seagrass. Classic remains available as the simpler alternative. Scenery style is separate from colour themes and quality presets. See [Scenery controls](docs/SCENERY.md).

## Living aquarium candidate

0.3.0-preview.10 adds dynamic/object bubbles, fish activities, animated water, an opt-in local nursery and manual mesh-message games. See [controls and boundaries](docs/LIVING-AQUARIUM.md). DX egg transfer is not connected.

## Home Assistant release history

## 0.3.0-preview.12

- Redesign the optional native/source operator with a stable sidebar, grouped
  appearance drafts, explicit save scopes, applied-scene preview and discard
  confirmation. Keep the managed HA aquarium display-only with HA Configuration.
- Preserve radio, receiver/persistence, games and juvenile genetic visuals.

## 0.3.0-preview.11

- Age-based genetic colours: ivory-tinted fry and softly coloured young, with readable neutral eyes.
- Preserve monochrome genetics and unchanged adult appearance; no persistence or radio protocol changes.
- Retire obsolete appearance/adoption handoffs and clarify approved, unimplemented adoption plans.

## 0.3.0-preview.10

- Dynamic, object-linked bubbles and optional static collision deflection.
- Independent fish activities and animated background water controls.
- Opt-in native breeding cave, persistent local eggs and frozen parent portraits. DX transfer remains gated.
- Separate manual mesh-message games page: noughts and crosses, guessing and open-deck blackjack. No automated sends.
- Existing read-only viewer, radio backend and firmware are unchanged.

## 0.3.0-preview.9

- Tidal Garden is now the default native reef, with shaded animated seagrass.
- Classic remains selectable through the new Scenery style option.
- Mesh-derived reef collision shapes replace the old fixed rock proxies.
- Optional standalone operator gains persistent Reef and Plants checkboxes.
- Managed aquarium stays display-only; receiver, stored fish and firmware are unchanged.

# Changelog

## 0.3.0-preview.8

- Six built-in themes, persistent data-only custom themes and a theme library page under setup.
- Duplicate/edit/import/export; immutable built-ins and guarded/conflict-aware saves.
- HA-owned theme_id, fish_style and theme_overrides with Save + Restart.
- Classic, rounded and faceted meshes preserve received identity/colours and lifecycle.
- Existing appearance, schedules, expiry and quality migrate unchanged by default.

## 0.3.0-preview.7

- Optional fish-copy lifespan in hours (0/off by default, fractions through 8760).
- Persisted UTC share time; new shares renew, duplicate COMMITs/replays/restarts do not.
- Expired copies animate out; history retained, manual hiding stays separate.
- Known deadlines continue during backend outages; pending original-pet returns
  remain independent. Logs report active/expired/undated counts.
- Existing databases keep their timestamps. No native operator, firmware, HACS
  or radio configuration change. Save + Restart to apply the HA option.

## 0.3.0-preview.6

- Added HA-owned appearance options: light strengths, clock/HA-sun day/night,
  water backgrounds/fog, sand tint, light shafts, caustics and plant motion.
- Stable floor/shelf/mixed bubble columns use a bounded total pool. HA has no
  shelves; floor or mixed placement is appropriate. Default columns: zero.
- HA sun/timezone observation is read-only and isolated from presentation;
  missing/stale state falls back to a documented clock schedule.
- Classic/static defaults retained; no native controls added to HA. Manual
  configuration still uses Save + Restart; cycles run without further restarts.
- Versioned field-level settings validation and preservation of malformed files.
  No fish database, firmware or radio protocol changes.

## 0.3.0-preview.5

- The HA Web UI and default ingress URL now open directly to the aquarium:
  no launcher, navigation, controls or persistent overlay in Lovelace cards.
- Existing `/view/` and `/control/` cards continue to show the read-only aquarium.
- Card setup stays separate at `setup.html#cards`; old `#cards` links still work.
  New card YAML omits the optional title for a clean display.
- Receiver, fish data, graphics and HA Configuration options are unchanged.

## 0.3.0-preview.4

- HA Configuration now owns graphics presets/overrides, resolution/FPS, fish
  labels, chat bubbles, decorations and arrival/departure styles. Save and restart.
- Removed the HA native operator window and all deadzone/mask/layout behavior.
  Standalone desktop behavior is retained; graphics assets are unchanged.
- Old controls cards resolve to the read-only aquarium. New card YAML uses the
  configured output aspect ratio. Connection diagnostics move to the Logs tab.
- Existing HA connection/output options and fish databases are preserved.
  Old in-app visual preferences are not imported; reapply them in Configuration.
  The old settings/layout files are left intact for rollback.
- Manual collection/retry actions are not mapped to persistent settings. Restart
  does not clear saved fish or re-arm exhausted return jobs.

## 0.3.0-preview.3

- Dashboard cards setup page in the Web UI generates aquarium-only and optional
  operator card YAML from the installed add-on slug or Info page URL.
- Reuses the separately installed HACS Ingress webpage card for managed ingress
  sessions; no temporary URLs, extra ports, or dashboard configuration writes.
- Native renderer, stream security, receiver, database, and dependencies unchanged.
- Setup-page browser checks are local; actual Lovelace/Supervisor embedding still
  needs validation on the installed HA instance.

## 0.3.0-preview.2

- New `home_assistant` mode shares the existing MeshCore integration through HA
  events/services. No replacement radio firmware or additional HACS component.
- Read-only diagnostics, explicit multi-radio selection and pinned full identity.
- Durable host-side LFG1 capture/returns with bounded retries and restart recovery.
- Receiver process survives renderer/stream restarts; native managed connection
  panel shows pending/unresolved returns and provides deliberate retry.
- HAOS API access uses the Supervisor token; standalone HA uses a token file.
- Default remains demo. Existing direct-RX mode/data are preserved. Read the
  updated Documentation before enabling fish reception.
- Local fixture/native validation only; actual HAOS build/API and physical
  one-fish trial are still required.

## 0.3.0-preview.1

- Original amd64 native Aquarium browser-streaming preview and optional direct
  MeshCoMod+LRX receiver mode.
