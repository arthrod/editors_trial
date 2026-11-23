"""E2: every browser target declares its own port.

react-docx was first given 5221, Fidus's proxy port. Fidus attaches to an app
service that may already be running there, so on such a host react-docx's
``--strictPort`` server could not start (or the lane would measure Fidus).
"""

import re
import unittest

from perf.runner.benchmark_warm_cold import BROWSER_TARGETS


class TargetPorts(unittest.TestCase):
    def test_every_browser_target_has_its_own_port(self):
        seen = {}
        for editor, target in BROWSER_TARGETS.items():
            port = int(re.search(r":(\d+)/", target["url"]).group(1))
            self.assertNotIn(port, seen, "%s and %s both declare port %d" % (seen.get(port), editor, port))
            seen[port] = editor

    def test_the_command_serves_the_declared_port(self):
        for editor, target in BROWSER_TARGETS.items():
            command = target.get("command", [])
            if "--port" in command:
                port = re.search(r":(\d+)/", target["url"]).group(1)
                self.assertEqual(command[command.index("--port") + 1], port, editor)


if __name__ == "__main__":
    unittest.main()
