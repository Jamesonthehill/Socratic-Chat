from __future__ import annotations

import json
from html import unescape
from http.server import ThreadingHTTPServer
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from trace_viewer import delete_trace, make_handler, render_page


class TraceViewerTests(unittest.TestCase):
    def test_delete_trace_removes_only_matching_snapshots(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            first = directory / "one-classifier.json"
            second = directory / "one-tutor-generation.json"
            other = directory / "other-classifier.json"
            for path, trace_id in ((first, "one"), (second, "one"), (other, "other")):
                path.write_text(json.dumps({"trace_id": trace_id}), encoding="utf-8")
            (directory / "invalid.json").write_text("not JSON", encoding="utf-8")

            self.assertEqual(delete_trace(directory, "one"), 2)
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())
            self.assertTrue(other.exists())
            self.assertTrue((directory / "invalid.json").exists())

    def test_page_keeps_long_prompt_collapsed_and_requires_confirmation(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            (directory / "example-tutor-generation.json").write_text(
                json.dumps({
                    "trace_id": "example",
                    "phase": "tutor-generation",
                    "request": {"model": "qwen", "messages": [{"role": "user", "content": "Question <one> & two"}]},
                }),
                encoding="utf-8",
            )

            page = render_page(directory, "example", "test-token")
            self.assertIn("Delete trace", page)
            self.assertIn("confirm(", page)
            self.assertIn('name="token" value="test-token"', page)
            self.assertIn("<details><summary>Exact messages sent to Qwen (1)</summary>", page)
            self.assertIn('id="sidebar-toggle"', page)
            self.assertIn('id="sidebar-backdrop"', page)
            self.assertIn("sessionStorage.setItem('trace-viewer-sidebar'", page)
            self.assertIn('class="copy-request"', page)
            copy_payload = re.search(r'<pre class="copy-payload" hidden>(.*?)</pre>', page, re.DOTALL)
            self.assertIsNotNone(copy_payload)
            copied_request = json.loads(unescape(copy_payload.group(1)))
            self.assertEqual(copied_request["messages"][0]["content"], "Question <one> & two")

    def test_delete_endpoint_requires_page_token(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            snapshot = directory / "example-classifier.json"
            snapshot.write_text(json.dumps({"trace_id": "example", "phase": "classifier"}), encoding="utf-8")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(directory))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with urlopen(url) as response:
                    page = response.read().decode("utf-8")
                token = re.search(r'name="token" value="([^"]+)"', page)
                self.assertIsNotNone(token)
                bad_request = Request(
                    url + "/delete",
                    data=urlencode({"trace": "example", "token": "wrong"}).encode(),
                    method="POST",
                )
                with self.assertRaises(HTTPError) as context:
                    urlopen(bad_request)
                self.assertEqual(context.exception.code, 403)
                self.assertTrue(snapshot.exists())

                good_request = Request(
                    url + "/delete",
                    data=urlencode({"trace": "example", "token": token.group(1)}).encode(),
                    method="POST",
                )
                with urlopen(good_request) as response:
                    self.assertEqual(response.status, 200)  # Follows the deletion redirect.
                self.assertFalse(snapshot.exists())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
