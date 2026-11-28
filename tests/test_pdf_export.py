import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from bodive import pdf_export, director
from bodive.connectors import Telegram
from bodive.memory import Memory, Refused

class PDFTests(unittest.TestCase):
    def test_render_literal_and_long_text(self):
        pdf = pdf_export.render("# Title\n\n<image src='file:///secret'/> & text\n" + "Example paragraph.\n"*200,
                                "Example")
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", pdf)

    def test_reject_incomplete(self):
        with tempfile.TemporaryDirectory() as d:
            memory = Memory("simulation", Path(d)/"db.sqlite")
            dossier = director.plan(memory, "onboarding", 1200, 400, 0, None)
            row = memory.propose("claude", {"dossier_id":dossier}, 203)
            memory.decide(row["id"], row["digest"], True, "telegram:42")
            memory.claim(row["id"], {"claude"})
            memory.record_draft(row["id"], {"draft":"Partial", "stop_reason":"max_tokens"})
            with self.assertRaises(Refused):
                pdf_export.from_approval(memory, row["id"])

    def test_upload_to_operator_only(self):
        http = Mock()
        http.request.return_value = {"ok":True}
        telegram = Telegram(http, "test", 42)
        telegram.document(b"%PDF-test", "bodive-review.pdf")
        args = http.request.call_args.args
        self.assertTrue(args[1].endswith("/sendDocument"))
        self.assertIn(b"\r\n42\r\n", args[2])
        self.assertIn(b"%PDF-test", args[2])
        with self.assertRaises(Refused):
            telegram.document(b"not pdf", "bodive-review.pdf")

    def test_inline_escapes_untrusted_markup(self):
        self.assertEqual(pdf_export.inline("**Bold** <img src='file:///secret'/>"),
                         "<b>Bold</b> &lt;img src='file:///secret'/&gt;")

    def test_workbook_table_and_writing_lines(self):
        source = "# Exercise\n**Goals**\n\n| Goal | Criterion |\n|---|---|\n"
        source += "| Scope | " + "Long example. "*45 + "|\n"
        source += "| Timing | Confirm milestones |\n\n**Goal 1:** ______________________\n"
        pdf = pdf_export.render(source, "Freelancer workbook")
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", pdf)
