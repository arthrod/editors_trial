"""Read-only inventory of independently hosted E2 campaign shards."""

import json
import re
from pathlib import Path


def campaign_provenance(roots):
    """Accept campaign directories, or Space directories containing runs/."""
    campaigns = set()
    for value in roots:
        root = Path(value).resolve()
        if (root / 'runs').is_dir():
            campaigns.update(p for p in (root / 'runs').iterdir() if p.is_dir())
        else:
            campaigns.add(root)
    records = []
    for root in sorted(campaigns):
        if not root.is_dir():
            raise ValueError(f'campaign root does not exist: {root}')
        space = root.parent.parent.name if root.parent.name == 'runs' else root.parent.name
        if re.fullmatch(r'shard[0-9]+', space):
            space = root.parent.parent.parent.name
        try:
            affinity = [line for line in (root / 'RUN.log').read_text().splitlines() if 'cpu_affinity_pinned=' in line]
        except OSError:
            affinity = []
        jobs = []
        for job in sorted(p for lane in root.iterdir() if lane.is_dir() for p in lane.iterdir() if p.is_dir()):
            if not ((job / 'summary.json').exists() or (job / 'cells').is_dir() or (job / 'samples').is_dir()):
                continue
            try:
                summary = json.loads((job / 'summary.json').read_text())
                if not isinstance(summary, dict):
                    summary = {}
            except (OSError, json.JSONDecodeError):
                summary = {}
            jobs.append(
                dict(
                    space=space,
                    campaign=str(root),
                    job=str(job),
                    run_id=summary.get('run_id', job.name),
                    runner=summary.get('runner', job.parent.name),
                    seed=summary.get('seed'),
                    status='summary available' if summary else 'incomplete',
                    cpu_accounting=summary.get('cpu_accounting'),
                    cpu_steal_percent=summary.get('cpu_steal_percent'),
                    cpu_throttle_refused_samples=summary.get('cpu_throttle_refused_samples'),
                )
            )
        if not jobs and not (root / 'RUN.log').is_file():
            raise ValueError(
                f'campaign root has no runs/ and no campaign jobs: {root} '
                '(pass a Space directory containing runs/, or a campaign directory)'
            )
        records.append(dict(space=space, campaign=str(root), cpu_affinity_pinned=affinity, jobs=jobs))
    return records
