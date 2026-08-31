# Ariadne — GOAD-Light collection manifest

Collected: 2026-08-30 14:07 UTC

## Lab (ground truth source)
- GOAD lab: **GOAD-Light** (2-domain forest with parent-child trust)
- GOAD commit: **992307a** (github.com/Orange-Cyberdefense/GOAD)
- Domains: sevenkingdoms.local (parent) + north.sevenkingdoms.local (child)
- Hosts (Vultr private IPs): dc01=kingslanding 10.51.96.3 | dc02=winterfell 10.51.96.4 | srv02=castelblack 10.51.96.5
- Provisioned on Vultr Cloud VMs (Bangalore) via Ansible against pre-existing hosts (NOT Vagrant)

## Deviations from stock GOAD-Light (no effect on attack-path ground truth)
- SSMS (SQL Server Mgmt Studio, a GUI client) skipped — not collected by SharpHound; MSSQL server + its attack config are present.
- Windows Updates skipped — OS patch level, irrelevant to AD attack paths.

## Collectors
- bloodhound-ce-python 1.9.1 (BloodHound CE format) — primary dataset (collect_ce/*)
- bloodhound-python (legacy 4.2/4.3) 1.9.0 — secondary/compat (collect/*)
- certipy-ad 4.8.2 — ADCS (ESC1/4/7/8), BloodHound-CE zip (collect_ce/adcs/*)
- Collection method: -c All, over LDAP/SMB (NTLM), from ATTACK01 (10.51.96.7)

## Passes (vantage points)
| dir | domain | account | role |
|-----|--------|---------|------|
| seven_ea    | sevenkingdoms.local | administrator     | Enterprise/Domain Admin (ground truth) |
| north_ea    | north.sevenkingdoms.local | eddard.stark | Domain Admin (ground truth) |
| north_arya  | north.sevenkingdoms.local | arya.stark   | low-priv (attacker vantage) |
| seven_tyron | sevenkingdoms.local | tyron.lannister   | low-priv (attacker vantage) |
| adcs        | (ADCS via certipy)  | administrator     | ESC1/4/7/8 |

## Validation (confirmed present in collected data, by name)
- jaime.lannister --GenericWrite--> joffrey.baratheon --WriteDacl--> tyron.lannister
- kingsguard --GenericAll--> stannis.baratheon
- lord.varys --GenericAll--> Domain Admins
- DCSync rights on domain object; ESC1 (Domain Users can enroll, supplies subject, client auth)
