"""The sandbox runner must keep a child's whole stderr, tail included."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_bomb_sandbox as R  # noqa: E402

NODE = shutil.which("node")


@unittest.skipUnless(NODE, "node is needed: it writes pipes asynchronously on macOS")
class CaptureTest(unittest.TestCase):
    def test_error_after_a_large_stderr_dump_is_kept(self):
        # Node on macOS writes to a pipe asynchronously and loses what is past
        # the 64 KB pipe buffer when it dies on an uncaught exception. Editors
        # such as Docxodus print a 200 KB runtime dump before the message that
        # names their ceiling, so the message is the part that must survive.
        script = "process.stderr.write('x'.repeat(200000) + '\\n'); throw new Error('CEILING_NAMED_HERE')"
        with tempfile.TemporaryDirectory() as tmp:
            code, timed, out, err = R._run_captured(
                [NODE, "-e", script], cwd=tmp, env=None, timeout=30, work=Path(tmp))
        self.assertFalse(timed)
        self.assertNotEqual(code, 0)
        self.assertIn("CEILING_NAMED_HERE", err)
        self.assertGreater(len(err), 200000)

    def test_timeout_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, timed, out, err = R._run_captured(
                [NODE, "-e", "console.log('started'); setTimeout(() => {}, 60000)"],
                cwd=tmp, env=None, timeout=1, work=Path(tmp))
        self.assertTrue(timed)
        self.assertEqual(code, 124)
        self.assertIn("started", out)


if __name__ == "__main__":
    unittest.main()
