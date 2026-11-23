"""Balanced assignment of independent publication jobs to Spaces (Arthur, 2026-11-11).

Jobs differ by two orders of magnitude (a C10 scroll job takes minutes, a
document job on the 250k-word rung takes hours), so ``index % N`` leaves most
Spaces idle while a few finish. ``assign`` packs longest job first onto the
least-loaded Space, and never puts the two seeds of one cell on the same
Space: the two-seed reproduction check then also exposes a noisy machine.

    python -m perf.container.plan --spaces 20 [--seed 1 --seed2 2]

prints one ``--jobs`` list per Space. Estimates are minutes per one-editor
job, read off campaign 1 (2026-11-11); only their ratios matter.
"""
import argparse
import json

from perf.runner.browser_run import PUBLICATION_REPETITIONS

# Minutes per one-editor job by rung; 'C14' walks the whole ladder.
_RUNG = {'prose-500w': 1.0, 'prose-5kw': 1.3, 'prose-50kw': 2.2, 'prose-250kw': 6.0, 'complex-corpus': 1.3,
         'prose-500kw': 15.0}  # #188: extrapolated from 250kw (no campaign-1 timing)
_BASE = {'benchmark_warm_cold': 20, 'benchmark_document': 40, 'benchmark_input': 15,
         'adversarial_c10_scroll': 10, 'benchmark_memory': 20, 'benchmark_resources': 20}
_TYPING = 180  # campaign 1 calibrated 360 minutes for twelve sessions; scaled to six
_C14 = 150
# Campaign 1 (2026-11-11) timed one job over 30 repetitions. _BASE and _C14 are
# those minutes. PUBLICATION_REPETITIONS is how many a publication job runs now.
_CALIBRATED_REPS = 30


_BUILD = 3  # minutes: one production host build per one-editor run


def estimate(name, options, shakedown=None):
    """Minutes for one job; with ``shakedown=N``, N repetitions (+1 traced) of the calibrated 30."""
    if name == 'benchmark_typing':
        return 15 if shakedown else _TYPING
    if '--criteria' in options and 'C14' in options:
        full = _C14
    else:
        full = _BASE[name] * _RUNG[options[options.index('--workload') + 1]]
    if '--block' in options:
        # A block: every editor, its absolute repetition count out of the calibrated 30,
        # one host build each. Its first block is traced, which doubles the launches.
        from .policy import SHAKEDOWN_COUNT_FLAG, job_editors
        editors = len(job_editors(options))
        reps = int(options[options.index(SHAKEDOWN_COUNT_FLAG[name]) + 1])
        traced = 2 if '--chrome-profile' in options else 1
        if shakedown:
            # A rehearsal: N repetitions of every editor, plus the traced one.
            return full * editors * (shakedown + traced - 1) / _CALIBRATED_REPS + _BUILD * editors
        return full * editors * reps / _CALIBRATED_REPS * traced + _BUILD * editors
    # A one-editor job runs the publication schedule, not the 30 that were timed.
    if shakedown:
        return full * (shakedown + 1) / _CALIBRATED_REPS + _BUILD
    # A one-editor job builds its host like every other job; the 30-repetition
    # calibration carried that build inside _BASE, so scaling it down must add it back.
    return full * PUBLICATION_REPETITIONS / _CALIBRATED_REPS + _BUILD


def assign(jobs, costs, spaces):
    from .policy import job_key

    order = sorted(range(len(jobs)), key=lambda i: (-costs[i], i))
    plan = [[] for _ in range(spaces)]
    loads = [0.0] * spaces
    keys = [set() for _ in range(spaces)]
    for i in order:
        key = job_key(*jobs[i])
        free = [s for s in range(spaces) if key not in keys[s]]
        target = min(free, key=lambda s: (loads[s], s))
        plan[target].append(i)
        loads[target] += costs[i]
        keys[target].add(key)
    return [sorted(space) for space in plan]


def main(argv=None):
    from perf.runner.benchmark_warm_cold import BROWSER_TARGETS
    from perf.runner.browser_hosts import host_policy
    from .policy import publication_jobs

    parser = argparse.ArgumentParser()
    parser.add_argument('--spaces', type=int, required=True)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--seed2', type=int, default=2)
    parser.add_argument('--shakedown', type=int, default=None)
    parser.add_argument('--skip', default='', help='comma list of job indices already measured')
    parser.add_argument('--blocks', type=int, default=2, help='interleaved blocks per seed (publication layout)')
    parser.add_argument('--campaign', default='e2', choices=('e2', 'later'),
                        help="e2: the published campaign's editors; later: editors added after it")
    args = parser.parse_args(argv)
    from .policy import campaign_editors
    editors = campaign_editors(args.campaign)
    jobs = publication_jobs(editors, args.seed, args.seed2, 'shared_guarded', blocks=args.blocks)
    skip = {int(t) for t in args.skip.split(',') if t}
    todo = [i for i in range(len(jobs)) if i not in skip]
    costs = [estimate(*jobs[i], shakedown=args.shakedown) for i in todo]
    packed = assign([jobs[i] for i in todo], costs, args.spaces)
    out = [{'space': s, 'minutes': round(sum(costs[k] for k in space)),
            'jobs': ','.join(str(todo[k]) for k in space)} for s, space in enumerate(packed)]
    each = PUBLICATION_REPETITIONS // args.blocks
    print('publication: %d blocks of %d, %d jobs, %d minutes across %d spaces' % (
        args.blocks, each, len(todo), round(sum(costs)), args.spaces))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
