"""Measure read-only application HTTP latency; never creates an agent run."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time

import httpx


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--base-url', default='http://127.0.0.1:2024')
    cli.add_argument('--task-id')
    cli.add_argument('--samples', type=int, default=10)
    cli.add_argument('--concurrency', type=int, default=1)
    cli.add_argument('--output', default='tests/reports/http-latency.json')
    args = cli.parse_args()
    paths = ['/app/', '/api/health', '/api/tasks']
    if args.task_id:
        paths.append(f'/api/tasks/{args.task_id}')
    report = dict(at=datetime.now(timezone.utc).isoformat(), base_url=args.base_url,
                  scope='Read-only warm local HTTP; no new model/OCR calls',
                  samples=args.samples, concurrency=args.concurrency, routes={})
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        def fetch(path):
            start = time.perf_counter()
            response = client.get(path)
            response.raise_for_status()
            return round((time.perf_counter() - start) * 1000, 3)
        for path in paths:
            fetch(path)
            with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
                timings = list(executor.map(fetch, [path] * args.samples))
            report['routes'][path] = dict(milliseconds=timings, p50=statistics.median(timings),
                p95=sorted(timings)[max(0, __import__('math').ceil(.95 * len(timings)) - 1)])
    output = Path(args.output)
    if not output.is_absolute():
        output = BACKEND_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: {m: v[m] for m in ('p50', 'p95')} for k, v in report['routes'].items()}))


if __name__ == '__main__':
    main()
