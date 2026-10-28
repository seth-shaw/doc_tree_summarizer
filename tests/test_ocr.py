"""Unit tests for OCR backend selection and subprocess handling."""

# The private helper is exercised directly to isolate backend behavior.
# pylint: disable=protected-access

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from summarizer.extractors import builtin


class OCRTests(unittest.TestCase):
    """Exercise OCR configuration without requiring external services."""

    def setUp(self):
        """Create a temporary source PDF and Compose configuration."""
        self.directory = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        self.root = Path(self.directory).resolve()
        self.source = self.root / 'source with spaces.pdf'
        self.source.write_bytes(b'%PDF-input\x00\xff')
        self.target = self.root / 'output.pdf'
        self.compose = self.root / 'compose.yaml'
        self.compose.write_text('services: {}')

    @patch.object(builtin.shutil, 'which', return_value='/bin/docker')
    def test_docker_streams_binary_pdf_and_preserves_options(self, which):
        """Docker mode streams binary PDF data through standard streams."""
        original_run = subprocess.run

        def run(command, **kwargs):
            self.assertEqual(command[:9], ['docker', 'compose', '-f', str(self.compose),
                                          'run', '--rm', '--no-deps', '-T', 'ocrmypdf'])
            self.assertEqual(command[-2:], ['-', '-'])
            self.assertIn('--skip-text', command)
            self.assertIn('eng+fra', command)
            # Exercise real binary stdin/stdout handles, including non-UTF-8 bytes.
            kwargs.pop('check', None)
            return original_run(
                [
                    sys.executable, '-c',
                    'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())',
                ],
                check=False, **kwargs,
            )

        with patch.object(builtin.subprocess, 'run', side_effect=run):
            builtin._ocr_pdf(self.source, self.target,
                             {'compose_file': str(self.compose), 'language': 'eng+fra'}, 'auto')
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())
        which.assert_called_once_with('docker')

    @patch.object(builtin.shutil, 'which', return_value='/bin/docker')
    @patch.object(
        builtin.subprocess, 'run',
        return_value=subprocess.CompletedProcess([], 0, stderr=''),
    )
    def test_default_compose_path_and_forced_ocr(self, run, which):
        """The default Compose path and always-OCR flags are selected."""
        builtin._ocr_pdf(self.source, self.target, {}, 'always')
        command = run.call_args.args[0]
        self.assertEqual(Path(command[3]), Path(__file__).resolve().parents[1] / 'compose.yaml')
        self.assertIn('--force-ocr', command)
        self.assertNotIn('--skip-text', command)
        which.assert_called_once_with('docker')

    @patch.object(builtin.shutil, 'which', return_value='/bin/ocrmypdf')
    @patch.object(
        builtin.subprocess, 'run',
        return_value=subprocess.CompletedProcess([], 0, stderr=''),
    )
    def test_native_backend(self, run, which):
        """Native mode invokes ocrmypdf with the requested input and output."""
        builtin._ocr_pdf(self.source, self.target, {'backend': 'native'}, 'auto')
        command = run.call_args.args[0]
        self.assertEqual(command[0], 'ocrmypdf')
        self.assertEqual(command[-2:], [str(self.source), str(self.target)])
        run.assert_called_once()
        which.assert_called_once_with('ocrmypdf')

    @patch.object(builtin.shutil, 'which', return_value=None)
    def test_missing_executable(self, which):
        """Unavailable OCR executables produce actionable errors."""
        for backend, message in [('docker', 'Docker'), ('native', 'native ocrmypdf')]:
            with self.subTest(backend=backend), self.assertRaisesRegex(RuntimeError, message):
                builtin._ocr_pdf(self.source, self.target, {'backend': backend}, 'auto')
        self.assertEqual(which.call_count, 2)

    @patch.object(builtin.shutil, 'which', return_value='/bin/docker')
    def test_missing_compose_file(self, which):
        """Docker mode reports a missing Compose file."""
        with self.assertRaisesRegex(RuntimeError, 'extraction.ocr.compose_file'):
            builtin._ocr_pdf(
                self.source, self.target,
                {'compose_file': str(self.root / 'missing')}, 'auto',
            )
        which.assert_called_once_with('docker')

    def test_invalid_backend(self):
        """Unknown backend names are rejected."""
        with self.assertRaisesRegex(ValueError, 'extraction.ocr.backend'):
            builtin._ocr_pdf(self.source, self.target, {'backend': 'unknown'}, 'auto')

    @patch.object(builtin.shutil, 'which', return_value='/bin/docker')
    @patch.object(
        builtin.subprocess, 'run',
        return_value=subprocess.CompletedProcess([], 1, stderr='engine unavailable'),
    )
    def test_docker_failure_includes_diagnostics(self, run, which):
        """Docker failures include stderr in the raised error."""
        with self.assertRaisesRegex(RuntimeError, 'OCR failed: engine unavailable'):
            builtin._ocr_pdf(self.source, self.target, {'compose_file': str(self.compose)}, 'auto')
        run.assert_called_once()
        which.assert_called_once_with('docker')
