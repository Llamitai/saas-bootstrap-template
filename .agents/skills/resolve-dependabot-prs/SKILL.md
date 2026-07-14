---
name: resolve-dependabot-prs
description: Resolve every open GitHub Dependabot pull request in the current repository with gh. Use when asked to triage, update, fix, merge, close, batch, or regenerate lockfiles for Dependabot dependency PRs. Stable patch and minor updates run autonomously; major or uncertain updates are prepared and verified but require explicit approval.
---

# Resolve Dependabot PRs

Resolve the complete bounded set of open Dependabot PRs for the repository
identified by `origin`. Prefer stable releases, regenerate affected lockfiles,
fix compatibility code when necessary, and verify before merging.

## Safety contract

- Use `gh` for every GitHub read or mutation and pass the verified repository
  explicitly. Use `git` only for local work and exact branch pushes.
- Never force-push, bypass protections, use admin merge, delete branches, stash,
  reset user work, or mutate another repository.
- Merge stable patch/minor updates autonomously after local and remote checks.
- Treat major, non-SemVer, and uncertain-impact updates as major. Prepare and
  validate them, then ask the user before any remote mutation.
- Never update to a known prerelease. Close its source PR only after the runner
  revalidates the version predicate.
- Close other nonapplicable PRs autonomously only when the runner can revalidate
  an exact merged replacement. Interpretive evidence requires explicit close
  approval. Network, auth, parser, or evidence failures leave the PR open.
- Never close a source before its replacement merge is confirmed.
- Reinspect after each remote mutation. A major sharing a lockfile with an
  unrelated patch/minor must not hold the patch/minor behind its approval gate.

## Locate the bundled runner

Resolve the absolute directory containing this loaded `SKILL.md`. Use:

```text
<skill-dir>/scripts/dependabot_prs.py
```

Do not assume the loaded copy is under `.claude`; the same skill is distributed
to `.codex`, `.opencode`, and `.agents`.

The JSON contracts live in `<skill-dir>/schemas/`. Read the candidate schema
before creating a candidate and the plan/state schemas before applying one.

## 1. Establish project rules and a clean workspace

1. Read the repository `AGENTS.md` plus any nested instructions for files that
   dependency work may touch.
2. Resolve the root with `git rev-parse --show-toplevel`.
3. Preserve all existing changes. If the main worktree is dirty, prepare each
   update in a temporary clone or worktree; never stash or reset it.
4. Create a private temporary working directory outside tracked project paths
   for inventory, candidates, plans, and runtime state. Name state files by
   their plan digest.
5. Verify `gh auth status` before attempting work. Do not request broader auth
   unless the runner reports that it is required.

## 2. Inspect the complete open set

Run from any directory:

```bash
python3 <skill-dir>/scripts/dependabot_prs.py inspect \
  --root "$(git rev-parse --show-toplevel)" \
  > "$workdir/inventory.json"
```

Stop without mutations if `complete` is false. Report every structured error
and its action. Do not substitute a manual partial PR list.

The runner accepts only REST author `dependabot[bot]` with type `Bot`, verifies
fetch/push identity for `origin`, paginates all open PRs, and emits singleton
groups. Overlaps are serialization hints, not approval groups.

Process in this order:

1. mechanically verifiable nonapplicable closures;
2. stable security patch/minor updates;
3. all other stable patch/minor updates;
4. major or uncertain proposals.

## 3. Classify stability and impact

Trust the runner's parsed inventory, then verify release information from an
official registry, release, or changelog before building the candidate.

- npm uses SemVer.
- Python/uv uses the supported PEP 440 release tuple.
- Docker digest-only changes under the same stable tag are patch.
- GitHub Action SHA changes within the same declared major are patch.
- `a`, `b`, `rc`, `dev`, and other recognized prerelease markers are not
  eligible for update.
- Unknown or non-SemVer impact is major; evidence cannot downgrade it in v1.
- Security updates use the same approval rules and receive higher priority.

When metadata cannot be parsed, leave the source open as blocked. Do not convert
a parser failure into a major proposal or closure.

## 4. Prepare and verify one candidate

Work on one singleton group at a time.

### Direct candidate

Use direct mode only when the Dependabot head already contains the complete
change, its head is based on the inventoried base snapshot, the lockfiles are
correct, and all applicable project checks pass. The candidate commit is the
exact Dependabot head; never push to its branch.

### Replacement candidate

Use replacement mode when lockfiles must be regenerated, compatibility code
must change, related lockstep packages are required, the source no longer
applies cleanly, or direct validation fails.

1. Start from the exact inventoried base SHA in an isolated clone/worktree.
2. Apply only the stable dependency versions needed for this source. Additional
   lockstep dependencies require an official compatibility URL and explicit
   candidate entry.
3. Update application code only as needed for compatibility.
4. Regenerate, never hand-edit, affected lockfiles. Detect the package manager
   from tracked manifests and repository instructions. Common commands include:

   ```bash
   uv lock
   pnpm install --lockfile-only
   pnpm -C frontend install --lockfile-only
   pnpm -C docs install --lockfile-only
   ```

5. Run the strongest checks required by project instructions for every affected
   surface. For this SaaS Bootstrap repository, use as applicable:

   ```bash
   just backend quality
   just backend test
   pnpm -C frontend verify
   pnpm -C docs types:check
   pnpm -C docs build
   python3 scripts/sync_skills.py --check
   ```

6. Run installs/builds/tests without GitHub, SSH-agent, or cloud credentials.
   If private dependencies require credentials, stop and request separate
   authorization.
7. Commit the verified candidate locally. Record the exact commit SHA, tree SHA,
   commands, exit codes, timestamps, versions, impact, and release evidence in a
   `candidate-v1` JSON object.

Do not include unrelated formatting, refactors, dependency upgrades, or user
work. If validation exposes a real compatibility break, fix and rerun it in the
same isolated candidate; do not weaken or skip the check.

## 5. Build the immutable plan

Run:

```bash
python3 <skill-dir>/scripts/dependabot_prs.py plan \
  --inventory "$workdir/inventory.json" \
  --candidate "$workdir/candidate.json" \
  --output "$workdir/plan.json"
```

The runner independently recomputes version impact, prerelease state, singleton
source membership, deterministic branch/marker identity, operations, approval
kind, and `planDigest`. A nonzero result is a blocker; do not hand-edit the plan
to bypass it.

## 6. Apply autonomous patch/minor work

If `approval.kind` is `none`, perform both phases without asking:

```bash
python3 <skill-dir>/scripts/dependabot_prs.py apply \
  --root "$repo" --candidate-root "$candidate_root" \
  --plan "$workdir/plan.json" --state "$workdir/<planDigest>.state.json" \
  --phase publish

python3 <skill-dir>/scripts/dependabot_prs.py apply \
  --root "$repo" --candidate-root "$candidate_root" \
  --plan "$workdir/plan.json" --state "$workdir/<planDigest>.state.json" \
  --phase finalize
```

For a closure plan, `publish` is the terminal phase and `finalize` is invalid.
For an update, `finalize` waits for checks and merge queue within the bounded
timeout, respects reviews/protections, merges with the first allowed method in
the runner's deterministic priority, and only then closes a superseded source.

If checks fail because of the candidate, correct it in the isolated workspace,
rerun all affected validation, create a new plan, and use the permitted
fast-forward correction path. A changed candidate invalidates any old approval.

## 7. Stop and ask for a major

For `approval.kind: update-major`, do not run `apply`. Present:

- repository and base ref/SHA;
- source PR and head SHA;
- from/to versions and why impact is major or uncertain;
- stability and compatibility evidence, including breaking changes;
- candidate commit/tree and concise diff;
- regenerated lockfiles and code changes;
- every validation result;
- destination branch and exact operations;
- the exact approve and reject tokens from the immutable plan.

Ask one explicit question: approve the exact plan, or reject and close it as a
declined major? End the turn and wait.

On a later unambiguous approval, pass `approve:<planDigest>` to both update
phases. If repo, base, source head, candidate, validation, or plan changed,
discard the approval and ask again with the new digest.

On an unambiguous rejection, create a `close-declined-major` candidate and plan
whose `parentPlanDigest` is the rejected update plan. Apply only the closure plan
with both `--parent-plan <original-plan>` and
`--approval-token reject:<parentPlanDigest>`. A rejection is not evidence of
technical incompatibility; label it only as a declined major.

## 8. Handle nonapplicable PRs

- `version-prerelease`: the runner reparses the exact target version and may
  close autonomously.
- `replacement-merged`: evidence must identify the exact replacement PR and
  merge SHA with the source marker; the runner requeries both before closing.
- Withdrawn releases, already-present changes, unsupported platforms, or other
  interpretive findings use `human-reviewed` evidence. Build the closure plan,
  show its URL/summary/digest, ask for the exact `close:<planDigest>` approval,
  and wait before applying.
- Never close on a transient error, unavailable evidence, or guess.

Every close is idempotently marked. If remote state or a marker conflicts with
the plan, leave the PR untouched and report the ambiguity.

## 9. Reinspect to a bounded fixed point

After every merge or closure, rerun `inspect`. Discard unapplied plans whenever
base SHA, source head, manifests, or state changed. Continue until a pass finds
no new Dependabot PR numbers, for at most three passes. If pass three still
discovers new numbers, report them as timeout-blocked for the next invocation.

Do not treat `queued`, `waiting-checks`, awaiting approval, or blocked as merged.

## 10. Report the outcome

Return one row per observed source PR with:

- number and dependency/version;
- stable impact classification;
- direct, replacement, close, awaiting-major-approval, or blocked action;
- local validations;
- replacement PR/merge SHA when applicable;
- final source state;
- blocker and exact next action when unfinished.

Clearly separate completed autonomous work from majors awaiting the user's
decision. Preserve any unpushed candidate workspace and report its path when a
failure makes it useful for recovery.
