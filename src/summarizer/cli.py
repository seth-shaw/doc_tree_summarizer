"""Command line entry point for document tree summarization."""

import argparse
import logging
from pathlib import Path

import yaml

from .cache import Cache
from .models.ollama import Ollama
from .pipeline import run


def main(argv=None):
    """Parse command line options and run the summarization pipeline."""
    parser = argparse.ArgumentParser(
        description='Summarize a document directory bottom-up with local Ollama')
    parser.add_argument('directory', type=Path, help='Input directory')
    parser.add_argument('--config', type=Path, default=Path('config.yaml'))
    parser.add_argument('--output', type=Path, default=None)
    parser.add_argument('--database', type=Path, default=Path('state/cache.sqlite3'))
    parser.add_argument('--model', help='Override document model')
    parser.add_argument('--directory-model', help='Override directory model')
    parser.add_argument('--sample', type=int, default=100, metavar='PERCENT',
                        help=('Randomly summarize this percentage of files in each directory '
                              '(0-100; default: 100)'))
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args(argv)
    if not 0 <= args.sample <= 100:
        parser.error('--sample must be between 0 and 100')
    args.directory = args.directory.expanduser()
    if not args.directory.exists():
        parser.error(f'input directory does not exist: {args.directory}')
    if not args.directory.is_dir():
        parser.error(f'input path is not a directory: {args.directory}')
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')
    config = yaml.safe_load(args.config.read_text(encoding='utf-8'))
    if args.model:
        config['summarization']['document_model'] = args.model
    if args.directory_model:
        config['summarization']['directory_model'] = args.directory_model
    output = args.output or Path(config.get('output', {}).get('html', 'summary.html'))
    cache = Cache(args.database)
    try:
        result = run(args.directory, config, cache, Ollama(
            config['summarization']), output, sample=args.sample)
    finally:
        cache.close()
    print(f'Report: {output.resolve()}')
    return 1 if result['status'] == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
