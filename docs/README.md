# docs/

Project background, design notes, and the source plan.

## Contents

- **Project plan** — the original brief: *Autonomous LLM Agents for Active Directory Attack-Path Discovery (synthetic-data / Option 1 build).* Drop the PDF here (`AD_LLM_Synthetic_Data_Project_Plan.pdf`) so the repo is self-contained.

## To add as the project develops

- `design-notes.md` — decisions and their rationale (graph sizes, prompt format, tool signatures).
- `threat-model.md` — which BloodHound edge types / attack primitives are in scope (e.g. `GenericAll`, `ForceChangePassword`, `MemberOf`, `AddMember`, Kerberoasting hops).
- `related-work.md` — BloodHound internals and prior LLM-for-security work, for the paper's background section.
