#!/usr/bin/env python3
"""Regression tests for the video-takeaways helper scripts."""

import os
from pathlib import Path
import stat
import subprocess
import tempfile
import textwrap
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "skills" / "video-takeaways" / "scripts"


def write_executable(path, content):
    path.write_text(textwrap.dedent(content))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class VideoTakeawaysHelpersTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.env = os.environ.copy()
        self.env["PATH"] = f"{self.bin_dir}:{self.env['PATH']}"
        self.env["TMPDIR"] = str(self.root)
        write_executable(self.bin_dir / "pandoc", "#!/usr/bin/env bash\nexit 99\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_script(self, name, *args):
        return subprocess.run(
            [SCRIPTS / name, *map(str, args)],
            capture_output=True,
            check=False,
            env=self.env,
            text=True,
        )

    def test_fetch_transcript_removes_automatic_caption_overlap(self):
        vtt = self.root / "captions.vtt"
        vtt.write_text(
            """WEBVTT

00:00:01.000 --> 00:00:02.000
hello world

00:00:02.000 --> 00:00:03.000
world how are you

00:00:03.000 --> 00:00:04.000
how are you

00:00:04.000 --> 00:00:05.000
you today
"""
        )
        write_executable(
            self.bin_dir / "yt-dlp",
            f"""\
            #!/usr/bin/env bash
            if [[ " $* " == *" --dump-single-json "* ]]; then
              printf '%s\n' '{{"id":"video","title":"Title","language":"en","automatic_captions":{{"en":[{{}}]}}}}'
              exit 0
            fi
            output=""
            while (($#)); do
              if [[ $1 == --output ]]; then output=$2; shift 2; else shift; fi
            done
            cp {vtt} "${{output//%(ext)s/vtt}}"
            """,
        )

        result = self.run_script("fetch-transcript", "https://example.com/video")

        self.assertEqual(result.returncode, 0, result.stderr)
        transcript_path = Path(
            next(line.removeprefix("transcript=") for line in result.stdout.splitlines() if line.startswith("transcript="))
        )
        self.addCleanup(transcript_path.unlink, missing_ok=True)
        self.assertEqual(
            transcript_path.read_text().splitlines(),
            [
                "1\t00:00:01\thello world",
                "2\t00:00:02\thow are you",
                "4\t00:00:04\ttoday",
            ],
        )

    def test_memos_helpers_reject_unsafe_tokens(self):
        token_file = self.root / "token"
        write_executable(self.bin_dir / "curl", "#!/usr/bin/env bash\nexit 99\n")

        for token in ("", "two words", 'bad"token', "bad\\token", "first\nsecond\n"):
            with self.subTest(token=repr(token)):
                token_file.write_text(token)
                list_result = self.run_script(
                    "list-memo-tags", "--base-url", "https://memos.example.com", "--token-file", token_file
                )
                epub_result = self.run_script(
                    "create-epub", "--base-url", "https://memos.example.com", "--token-file", token_file, "memos/1"
                )
                self.assertEqual(list_result.returncode, 1)
                self.assertIn("empty or invalid token", list_result.stderr)
                self.assertEqual(epub_result.returncode, 1)
                self.assertIn("empty or invalid token", epub_result.stderr)

    def test_memos_helper_accepts_trailing_newline(self):
        token_file = self.root / "token"
        token_file.write_text("valid-token\n")
        write_executable(
            self.bin_dir / "curl",
            """\
            #!/usr/bin/env bash
            output=""
            while (($#)); do
              if [[ $1 == --output ]]; then output=$2; shift 2; else shift; fi
            done
            printf '{"memos":[]}' >"$output"
            printf 200
            """,
        )

        result = self.run_script(
            "list-memo-tags", "--base-url", "https://memos.example.com", "--token-file", token_file
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no existing tags found", result.stderr)


if __name__ == "__main__":
    unittest.main()
