# Changelog

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
