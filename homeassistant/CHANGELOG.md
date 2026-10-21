# Changelog

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
