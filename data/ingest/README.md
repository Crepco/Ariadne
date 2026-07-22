# Ingesting BloodHound data

Ariadne reads the *same* graph whether it is the seeded synthetic one
([`data/generator/`](../generator/)) or a real
[BloodHound](https://github.com/SpecterOps/BloodHound) / SharpHound collection.
This directory is the bridge from a real export to that graph.

```
bloodhound.py         # real export  ->  Ariadne graph  ->  Neo4j
export_bloodhound.py  # Ariadne graph ->  BloodHound-CE JSON (the inverse; a safe sample)
```

## Ingest a real export

SharpHound / BloodHound-CE write a set of JSON files — `*_users.json`,
`*_groups.json`, `*_computers.json`, `*_domains.json` — usually inside one zip.
Point the ingest at the directory, the zip, or a single JSON file:

```bash
python data/ingest/bloodhound.py --from path/to/export_dir --wipe
python data/ingest/bloodhound.py --from collection.zip --dry-run   # parse + report only
```

Where to get a collection you are allowed to use:

- **Your own lab / an engagement you're authorised on.** Run SharpHound against a
  test domain (e.g. [GOAD](https://github.com/Orange-Cyberdefense/GOAD) or
  [DetectionLab](https://github.com/clong/DetectionLab)) and ingest the output.
- **A synthetic sample** minted by `export_bloodhound.py` (below) — realistic
  BloodHound-CE shape, zero sensitive data, fully offline.

> **Never commit a real collection to this repo.** Exports contain live
> hostnames, SIDs, and session data. Keep them outside the tree and ingest by path.

### What maps to what

The ingest keeps only the **canonical edges** (`schema.CANONICAL_EDGES`) — the
primitives BloodHound's own shortest-path query traverses — plus the node
properties the [inference rules](../../src/ariadne/inference.py) read. Everything
else is dropped.

| BloodHound source | Becomes |
| --- | --- |
| Group `Members`, `PrimaryGroupSID` | `MemberOf` edge |
| Object `Aces` (`RightName`) | the matching control edge (`GenericAll`, `ForceChangePassword`, `AddMember`, `GetChangesAll`→`DCSync`, …) |
| Computer `LocalAdmins` / `RemoteDesktopUsers` / `PSRemoteUsers` / `DcomUsers` | `AdminTo` / `CanRDP` / `CanPSRemote` / `ExecuteDCOM` |
| Computer `Sessions` / `PrivilegedSessions` / `RegistrySessions` | `HasSession` edge |
| Properties `hasspn`, `unconstraineddelegation`, `esc1`, … | inference-driving node properties |

Principal lists wrapped as `{"Results": [...]}` (BHCE) are unwrapped
automatically. Unrecognised edge types are ignored.

### The `crackable` heuristic

Whether a Kerberoastable account's password is actually **crackable** is an
offline fact BloodHound cannot collect, yet it gates the kerberoast inference
step. So the ingest sets it by a documented heuristic (`--crackable`):

| `--crackable` | Which SPN accounts are marked crackable |
| --- | --- |
| `spn-admincount` *(default)* | privileged ones (`admincount`) — the high-value roast targets |
| `all-spn` | every account with an SPN |
| `none` | none — rely only on properties already in the export |

`roastable_target` (the host→service-account link the kerberoast step needs) is
then derived from a crackable account's session on a host. An explicit value
already in the export always wins over the heuristic.

## Mint a safe sample (round-trip exporter)

`export_bloodhound.py` is the inverse of the ingest: it turns any Ariadne graph
into a BloodHound-CE-shaped JSON collection. Use it to get a realistic export
with no sensitive data, or to prove the pipeline round-trips:

```bash
python data/ingest/export_bloodhound.py --out /tmp/sample_export --seed 7
python data/ingest/bloodhound.py --from /tmp/sample_export --wipe   # re-ingest it
```

The round trip is loss-free: canonical edges and the inference properties
(`roastable_target`, `cred_target`, `unconstraineddelegation`, `esc1`) that make
the planted "beats BloodHound" chains solvable all survive
(`tests/unit/test_ingest.py::test_roundtrip_preserves_edges_and_reachability`).

## After ingesting

The reader pipeline runs unchanged on the ingested graph:

```bash
python data/generator/verify.py     # node/edge counts + ground-truth attack paths
python run.py                       # the agent, from a foothold
ariadne-chat                        # the grounded chat assistant
ariadne-web                         # the visualiser
```
