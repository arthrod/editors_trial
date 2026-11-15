# HF browser measurement container (#127)

**Never run Docker, buildx, orb, or any container locally.** Hugging Face builds
this tools-only image. No editor or trial source belongs in the Space repository.
No local build, smoke, or timing result establishes HF acceptance.

## Image pin

The Dockerfile pins Playwright 1.64.1 Noble to the registry's verified
linux/amd64 manifest `sha256:ee15712262f017b8157421b212b12099146645f44b1bc5c0514cbbe6a229b1d0`.
An initial Docker-media-type HEAD returned 404; an OCI-index GET resolved the
pin on 2026-11-10. No image was pulled or run locally. Node is inherited from
that image (the UI harness has no engines or .nvmrc pin); setup records it.
Python is Ubuntu Noble's 3.12, pnpm is major 10.

## One private Space

Use one private Docker Space, **cpu-upgrade (8 vCPU, x86_64)**, with **Dev Mode**
enabled, for every publication editor. Put only this Dockerfile and the Space's
metadata README in its repository. HF builds it; the uid-1000 `user` owns `/app`,
HOME is `/home/user`, and Python serves port 7860. After HF starts Dev Mode, copy the SSH endpoint shown by HF.

From the committed trial worktree, export tracked code and the facts separately:

```bash
export HF_SSH='user@YOUR-HF-DEV-MODE-SSH-ENDPOINT'
export HF_PORT='YOUR-HF-SSH-PORT'
export B6_EXPORT="$(mktemp -d /tmp/b6-export.XXXXXX)"
git archive HEAD | tar -x -C "$B6_EXPORT"
mkdir -p "$B6_EXPORT/out"
cp out/facts.json "$B6_EXPORT/out/facts.json"
# Never dereference symlinks, export repos/, node_modules, .env or key files.
tar -C "$B6_EXPORT" --exclude='.env' --exclude='.env.*' --exclude='repos' \
  --exclude='node_modules' --exclude='*.pem' --exclude='*.key' -czf - . \
  | ssh -p "$HF_PORT" "$HF_SSH" 'tar -xzf - -C /app'
ssh -p "$HF_PORT" "$HF_SSH" 'cd /app && bash perf/container/setup.sh'
ssh -p "$HF_PORT" "$HF_SSH" 'cd /app && bash perf/container/run.sh --smoke'
ssh -p "$HF_PORT" "$HF_SSH" 'cd /app && LIBGL_ALWAYS_SOFTWARE=1 python3 -m perf.container.plate_check'
ssh -p "$HF_PORT" "$HF_SSH" 'cd /app && bash perf/container/run.sh --publish --host-class shared_guarded --seed 1 --seed2 2'
```

Use a fresh writable `/app` export, not host-mounted dependency directories.
`setup.sh --dry-run` lists all 17 Git pins and matching update-script install
commands without network. Facts currently store nine-character SHAs, not full
SHAs: actual setup fetches, resolves to a full 40-character SHA, verifies the
prefix and checkout, and records it. Missing pins abort before installations.
The six editor installs use exactly `build/update_editors.sh`'s package managers
and flags (including its explicit npm command for genoffice). Harness manifests use their lockfile owner: npm ci for package-lock.json,
pnpm install --frozen-lockfile for pnpm-lock.yaml, or bun install
--frozen-lockfile for bun.lock/bun.lockb. Missing locks refuse setup; npm takes
precedence where a legacy pnpm lock coexists. Explicit package pins are then
installed as in update_editors.sh. Playwright 1.64.1 comes from the existing
harness/ui frozen lock and is verified without adding to its manifest. The
transitive SuperDoc engine is not added as a top-level dependency. Wordcraft
builds both the release CLI and Trunk web application. Setup may change lockfiles
in this disposable HF copy. No source changes are pushed back.

Setup records tool versions, full commits and npm resolutions in
`perf/container/out/setup-<stamp>.json`. Apryse's production adapter rejects a
missing key; it is excluded and recorded `not_run: licence key not exported`.
Do not transfer or source `.env`. `run.sh` also removes known licence variables.
Docsplus and Fidus are excluded by B1's nonpublishable app-server policy.

## Smoke and publication evidence

Dry-run commands are safe locally:

```bash
bash -n perf/container/setup.sh perf/container/run.sh perf/container/pull.sh
shellcheck perf/container/setup.sh perf/container/run.sh perf/container/pull.sh
bash perf/container/setup.sh --dry-run
bash perf/container/run.sh --dry-run --smoke
bash perf/container/run.sh --dry-run --publish --host-class shared_guarded --seed 1 --seed2 2
```

The HF smoke uses one static fake page for all four runners. For the three
catalog-only runners, `plate` is explicitly a **driver alias**, not the measured
editor; the smoke's host metadata and summary mark the substitution and forbid
publication. C10 uses its native fake-host interface. Correctness refusals on the
fake page are retained. The fake page satisfies the shared adapter readiness
gate and C10's native gate. Each job checks lane-owned profile and host metadata,
including attempts in rejected evidence, against the wrapper flags; disagreement
is a profile_mismatch refusal. This adapter has
not been exercised on HF. A real Plate production-host check is separately
required: it builds through B1 and waits for the target's `ready_selector` and
`ready_js` when present, printing `reached: true`. A target with neither gate
is refused before launching Chromium. Keep that output and build log.

Publication runs every eligible host through all four runners twice with distinct
seeds, with `dedicated_publish` and its default 30 repetitions. C10 takes singular
`--editor`, so each editor has its own C10 run; the other runners interleave
editors. Every invocation gets a distinct run id and output directory. The host
check runs first and refuses busy/unreadable hosts. All runs are headless;
`LIBGL_ALWAYS_SOFTWARE=1` requests software rendering, and the actual renderer
string must be present in the run summary. This environment request alone is
not proof of the Chromium backend: verify that HF summaries identify SwiftShader
or another software renderer before publication. Never compare these figures
with headed results.

HF is a shared VM, not a dedicated machine. B1 requires readable cgroup v2
accounting for `shared_guarded`, brackets samples, refuses CPU throttling under
#129, and records steal time and refusal counts. Preserve every refusal and
report N of M throttled samples, stolen time, shared tenancy and reproduced
figures. Recorded failures/refusals (including cpu_throttled) and runner nonzero
exits do not stop the remaining jobs or the second seed. At the end,
`out/e2-publication.json` records each runner/seed invocation, its run directory,
exit code, outer cell total, trial-file total, and measured / refused-by-reason /
failed-by-reason / not-run-by-reason trial counts under `by_editor_criterion`.
Each canonical `attempts/*.json` file counts exactly once, including separate
rungs and repetitions. Lane summaries and diagnostics are not additional trials.
The aggregate measured and reason counts sum attempt files only, equal the sum
of `by_editor_criterion`, and partition `trials_total`; code asserts this invariant.
`run_refused_by_reason`, `run_failed_by_reason`, and `run_not_run_by_reason` count
only outer outcomes whose evidence was quarantined (`rejected_evidence_directory`)
or which have no attempt files (for example, a runner crash before writing one).
An outer folded `'; '.join(...)` reason is never counted when attempts are counted.
Outer `ok` alone is never measurement evidence. Trials are skipped only when
`rejected_evidence_directory` is set or `cell_directory` is absent, never because
of a failure-reason string. A live `cpu_throttled` cell keeps measured siblings.
The wrapper exits nonzero for missing/unreadable summaries, missing renderer
records, runs with no measured criterion trials, or profile_mismatch. These errors are
collected after all jobs; every original evidence file is retained. It does not
retry to select favorable samples.

HF acceptance remains pending: successful image build, setup, four-runner smoke,
real Plate readiness, and primary/reproduction publication evidence. Local tests
cover planning and refusal policy, not those integration claims.

## Data safety during a campaign

Three copies of every measurement:

1. **Space disk** (fragile): the campaign directory under `/app` while the Space
   is running. Rebuild or factory reboot can erase it.
2. **HF Storage Bucket** (survives restarts): the private bucket
   `arthrod/editors-trial-e2-runs` on Hugging Face. After each job is sealed,
   `run.py` starts `mirror.py` in a separate process after each `JOB-DONE`
   (timeout `HF_MIRROR_TIMEOUT_S`, default 300) which uploads the job's
   generated files to `runs/<space>/<campaign id>/<runner>/<job>/` and the
   campaign-level files (`RUN.log`, `RUN-DONE`, job manifests) to
   `runs/<space>/<campaign id>/`. The space name is `SPACE_ID` when set, else
   the hostname. After uploading it lists the remote prefix and compares
   paths and sizes, logging exactly one `BUCKET-OK <job> <n> <bytes>` or
   `BUCKET-ERROR <job> <reason>` line per job in `RUN.log`; failures are
   retried on the next seal and the campaign tail re-checks every sealed job
   and uploads what is missing. The bucket phase has its own deadline inside
   the mirror timeout (`HF_BUCKET_TIMEOUT_S`, default 90% of it): a stuck
   upload is interrupted and logged as `BUCKET-ERROR <job> bucket timeout`,
   and a hung mirror child is still killed by the outer timeout so the next
   runner can start. `mirror.py` also keeps the legacy sha256-verified copy
   under `HF_MIRROR_ROOT` (`/data/e2` by default) whenever that path exists
   and is writable; `MIRROR-OK` marks a good local mirror.
   The write token comes from the Space secret `HF_BUCKET_TOKEN`; a Dev Mode
   ssh session may not carry the Space's secrets, so `/proc/1/environ` is the
   fallback. The token is used in memory only — never written to `RUN.log`,
   stderr, or any run file, and exception text is redacted before logging.
   With no token (or no `huggingface_hub`) `BUCKET-SKIP no_token` /
   `BUCKET-SKIP no_huggingface_hub` is logged once per run and the
   measurement continues. `setup.sh` installs `huggingface_hub==2.4.0`
   with `/home/user/python-runtime/bin/pip`, the same pin and path as
   the image Dockerfile. The Spaces are not rebuilt from that Dockerfile
   during the campaign, so this setup install is what the mirror's
   interpreter gets. `check_host` refuses to start when a bucket copy is
   expected and that library is not exactly this version, or the token
   is absent. A copy is expected when `SPACE_ID` is set in the process
   environment or in `/proc/1/environ`, or when `HF_BUCKET_REQUIRED=1`.
   `HF_BUCKET_REQUIRED=0` does not turn the check off when `SPACE_ID`
   is set. The check reports the token as present or absent only.
   The bucket gets generated measurement data only. `mirror.BUCKET_EXCLUDES`
   (one constant, relative to each job or campaign root) drops
   `builds/*`, `*/builds/*`, `dist/*`, `*/dist/*`, `node_modules/*`,
   `*/node_modules/*`, `fixtures/*`, `*/fixtures/*`, `repos/*`, `*/repos/*`,
   and `*.docx`: editor builds, dist and dependency trees, job fixture
   copies, anything under `repos/`, and every `.docx` input document never
   leave the Space.
3. **Mac pull** (verified, now the second copy): `pull.sh` streams tar
   batches into a staging area, hashes each member against the remote
   listing, and only then moves bytes into place. `FINAL-VERIFIED` on the
   Mac rehashes every listed file and still is the only permission to
   restart, rebuild, or push the Space.

The Space has no durable disk: anything left only under `/app` is lost on rebuild
or factory reboot. Sleep is set to never (`gcTimeout` null as of 2026-11-10); still
treat the VM as fragile.

1. Start publication on the Space with `--detach` so the campaign survives an SSH
   drop (`perf/container/run.sh --detach --publish …`). Each finished job gets an
   atomic `MANIFEST.sha256` and `JOB-DONE`; the campaign directory gets `RUN-DONE`.
2. On the Mac, run `perf/container/pull.sh` for the whole campaign:

   ```bash
   perf/container/pull.sh --target "$HF_SSH" --remote /app/perf/container/out \
     --dest "$HOME/path/to/e2-logs/hf-data/e2-publish" --interval 60 \
     --until-run 20261110T203054948922Z-33514-935073
   ```

   The `--until-run` value is the campaign run id printed by `run.sh --detach`
   (`<UTC-stamp>-<pid>-<six-random-digits>`). Pull never deletes locally; changed
   bytes are kept as `name.prev-<UTC-stamp>`. One line is printed per newly
   verified job. When the remote lists `RUN-DONE`, pull prints that marker for
   visibility but keeps copying until one full cycle after that finds nothing new,
   every listed file is present and hashed, and every sealed job passes manifest
   verification. Only then it prints
   `FINAL-VERIFIED <run-id> files=<n> jobs=<k> run_exit=<s>` (pull exits 0; the
   run's own exit status is on that line).
3. To fetch a campaign from the bucket instead — the first copy, useful when
   the Space is paused or its disk was lost — run `bucket_pull.py` on the
   Mac with a read token in `HF_BUCKET_TOKEN`:

   ```bash
   HF_BUCKET_TOKEN=... python3 -I perf/container/bucket_pull.py \
     --dest "$HOME/path/to/e2-logs/bucket/e2-publish" \
     --space arthrod/e2-publish --run 20261110T203054948922Z-33514-935073
   ```

   Omit `--run` to fetch every run of the Space. Files land under
   `<dest>/runs/<space>/...` mirroring the bucket layout. Each sealed job is
   downloaded into a staging dir and verified against its `MANIFEST.sha256`
   (every listed file's sha256, no unlisted files, the `manifest_sha256`
   recorded in `JOB-DONE`) before it is installed; a job that fails stays
   quarantined under `.bucket-staging*`. Replaced local files are preserved
   as `name.prev-<UTC-stamp>` and nothing local is ever deleted. It prints
   `BUCKET-PULL-ERROR <job> <reason>` per failed job and one
   `BUCKET-PULL <scope> files=<n> bytes=<b> ok=<j> failed=<k>` summary line,
   exiting non-zero on any mismatch, download error, or missing token.
4. Do not restart, factory-reboot, or push the Space repository until pull
   prints `FINAL-VERIFIED` for that campaign (or `bucket_pull.py` has
   fetched and verified every sealed job of the run). A `RUN-DONE` line
   alone is not permission to change the Space.
5. The bucket token lives only in the Space secret `HF_BUCKET_TOKEN` — never
   in the container image or the checkout — and `BUCKET_EXCLUDES` keeps
   builds, fixtures, `repos/`, and `.docx` inputs out of the bucket. The
   periodic SSH from `pull.sh` still serves as a Dev Mode keepalive.
