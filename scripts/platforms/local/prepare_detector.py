"""Download the published pinned detector; no LLM requests or frozen-file writes."""
import argparse
import concurrent.futures
import json
import urllib.request
from pathlib import Path
from runtime import ROOT, require_local, source_check, sha
from trustgate.planning import read_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--detector-dir', type=Path, default=ROOT / 'models/prompt_injection_detector')
    args = parser.parse_args()
    require_local()
    plan = read_plan(ROOT / 'assignments/formal/plan.json')
    source_check(plan)
    revision = (ROOT / 'models/detector_revision.txt').read_text().strip()
    if len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
        raise ValueError('Invalid published detector revision')
    args.detector_dir.mkdir(parents=True, exist_ok=True)
    def download(item):
        name, expected = item
        target = args.detector_dir / name
        if target.is_file() and sha(target) == expected:
            return name
        url = ('https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2/resolve/'
               + revision + '/' + name + '?download=true')
        temporary = target.with_suffix(target.suffix + '.partial')
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as stream:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                stream.write(chunk)
        if sha(temporary) != expected:
            raise RuntimeError('Downloaded detector hash mismatch: ' + name)
        temporary.replace(target)
        return name
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for name in pool.map(download, plan['detector_sha256'].items()):
            print('Verified detector file: ' + name, flush=True)
    from trustgate.formal_manifest import detector_hashes
    if detector_hashes(args.detector_dir) != plan['detector_sha256']:
        raise RuntimeError('Downloaded detector differs from frozen files')
    print(json.dumps(dict(verified=True, revision=revision, llm_requests=0)))


if __name__ == '__main__':
    main()
