"""B9 LOCAL FALLBACK. Replace with B8 resources.ResourceSampler at integration.

Async interface: ResourceSampler(run,page,cdp); mark, sample, series, totals.
run supplies process_snapshot(), profile_size(), network and monotonic clock.
Missing OS counters remain null, never zero. CPU percent is one-core percent.
"""
from copy import deepcopy

RESOURCE_SCRIPT = '''async () => { // B9_RESOURCE
 const estimate = await navigator.storage.estimate();
 return {long_tasks_count: window.__b9long?.count ?? null,
 long_tasks_ms: window.__b9long?.ms ?? null,
 storage_usage_bytes: estimate.usage ?? null,
 storage_usage_details: estimate.usageDetails ?? null};
}'''
INIT_SCRIPT = '''() => {
 window.__b9long = {count:0, ms:0};
 if (!PerformanceObserver.supportedEntryTypes.includes('longtask')) {window.__b9long=null; return;}
 new PerformanceObserver(list => { for (const e of list.getEntries()) {
 window.__b9long.count++; window.__b9long.ms += e.duration;
 }}).observe({type:'longtask', buffered:true});
}'''

class ResourceSampler:
    def __init__(self, run, page, cdp):
        self.run, self.page, self.cdp = run, page, cdp
        self.rows = []; self.phase = 'load'; self.started = run.clock()
        self.previous = {}; self.previous_at = None
        self.characters_typed = 0; self.selector = '[contenteditable="true"]'
    async def mark(self, phase):
        self.phase = phase
        row = await self.sample()
        self.phase = "periodic"
        return row
    async def sample(self):
        metrics = {m['name']: m['value'] for m in (await self.cdp.send('Performance.getMetrics'))['metrics']}
        page = await self.page.evaluate(RESOURCE_SCRIPT)
        present = await self.page.evaluate('(selector) => document.querySelector(selector)?.innerText ?? ""', self.selector)
        at = self.run.clock()
        processes = await self.run.process_snapshot()
        for proc in processes:
            old = self.previous.get(proc['pid'])
            proc['cpu_percent'] = (100 * (proc['cpu_ms'] - old) / ((at - self.previous_at) * 1000)
                if old is not None and self.previous_at is not None and at > self.previous_at else None)
        self.previous = {p['pid']: p['cpu_ms'] for p in processes}
        self.previous_at = at
        rss = {}
        for p in processes:
            role = p['role']
            if p.get('rss_bytes') is None or (role in rss and rss[role] is None): rss[role] = None
            else: rss[role] = rss.get(role, 0) + p['rss_bytes']
        row = dict(at_s=at-self.started, phase=self.phase, characters_typed=self.characters_typed,
            characters_present=len(present), backlog_chars=self.characters_typed-len(present),
            heap_used_bytes=metrics.get('JSHeapUsedSize'), heap_total_bytes=metrics.get('JSHeapTotalSize'),
            main_thread_ms={name: metrics[name]*1000 if name in metrics else None for name in
                ('ScriptDuration', 'LayoutDuration', 'RecalcStyleDuration', 'TaskDuration')},
            processes=processes, rss_by_role_bytes=rss, profile_bytes=self.run.profile_size(),
            network=deepcopy(self.run.network), **page)
        self.rows.append(row)
        return row
    def series(self):
        return deepcopy(self.rows)
    def totals(self, phase=None):
        rows = [r for r in self.rows if phase is None or r['phase'] == phase]
        peaks = {key: max((r[key] for r in rows if r.get(key) is not None), default=None)
                 for key in ('heap_used_bytes', 'heap_total_bytes', 'profile_bytes', 'storage_usage_bytes')}
        # Process identity is retained: summing peaks across PIDs invents a peak.
        process_peaks = {}
        for row in rows:
            for proc in row['processes']:
                peak = process_peaks.setdefault(str(proc['pid']), {'role':proc['role']})
                for key in ('rss_bytes','cpu_ms','cpu_percent','read_bytes','write_bytes'):
                    value = proc.get(key)
                    if value is not None: peak[key] = max(peak[key], value) if peak.get(key) is not None else value
                    else: peak.setdefault(key, None)
        if rows:
            peaks['processes'] = process_peaks
            peaks['main_thread_ms'] = {key:max((r['main_thread_ms'][key] for r in rows
                if r['main_thread_ms'][key] is not None), default=None) for key in rows[0]['main_thread_ms']}
            for key in ('long_tasks_count','long_tasks_ms'):
                peaks[key] = max((r[key] for r in rows if r.get(key) is not None), default=None)
        return {'last': deepcopy(rows[-1]) if rows else None, 'peaks': peaks}
