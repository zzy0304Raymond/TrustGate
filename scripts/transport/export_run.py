"""Export a new transport run without replacing the published study results."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.transport import study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=ROOT / 'runs/transport_validation/live')
    parser.add_argument('--controls', type=Path, default=ROOT / 'runs/transport_validation/live-controls')
    parser.add_argument('--output', type=Path, default=ROOT / 'runs/transport_validation/export')
    args = parser.parse_args()
    output = args.output.resolve()
    if ROOT / 'runs' not in output.parents:
        raise ValueError('New exports must be stored under runs/')
    if output.exists():
        raise FileExistsError('Choose a fresh export directory')
    study.RESULTS = output
    study.export(args.run, args.controls)
    study.verify()


if __name__ == '__main__':
    main()
