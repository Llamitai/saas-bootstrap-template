# Acceptance evidence

Use one OpenSpec change for functional work: proposal is problem/scope, delta specs are normative criteria, design holds contracts/decisions, tasks link vertical work to criteria. Resolve actual artifact paths with the repository CLI status/instructions commands. Respect explicit planning-home restrictions; do not create a second local copy.

Add an Evidence and acceptance section to tasks.md (in the project's documentation language). Mechanical/docs work keeps this concise in its existing task/PR/conversation.

| Criterion / normative link | Expected scenario/result | Technical verification | Observed validation | Status / evidence |
| --- | --- | --- | --- | --- |
| AC-01 / spec scenario | Input, context, observable outcome | Command, environment, exit code | Observed API/data/UI result or explicitly reused technical evidence | pending / satisfied / failed / blocked; report or reproduction |

Record base and tested revision, definition artifact version, timestamp, fixtures/services, owner and limits. For committed sources use SHA; for dirty work use HEAD plus a digest covering the diff AND relevant untracked sources. Exclude generated reports/logs from the source digest. `python3 scripts/source_snapshot.py` records the local source snapshot. Keep bulky artifacts outside the repository and a durable concise result here.

Changed code, contracts, fixtures or config invalidates affected evidence. State what must rerun and why unaffected results remain applicable. Never attribute dirty results to clean HEAD or reuse another branch's green. Required criteria remain required unless scope is explicitly redefined before implementation.

Transitions: ready definition -> build -> refine -> technical verification -> acceptance -> close. Implementation failure returns to its owner; changed scope returns to definition. Pending environment remains pending. No extra interviews, duplicate specs or redundant permission requests for already authorized work. Delegation is optional, only if authorized and useful for independent work; no fixed model or worker count.
