import tempfile
import unittest
from pathlib import Path
from bodive import chapters, cli, director, finance
from bodive.memory import Memory, Refused

class ChapterTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.memory = Memory("simulation", Path(directory.name) / "db.sqlite")
        self.dossier = director.plan(self.memory, "onboarding", 1200, 400, 0, None)

    def test_chapter_proposal_binds_limit_and_number(self):
        args = cli.parser().parse_args(["propose-chapter", self.dossier, "2"])
        import json
        payload = json.loads(cli.proposal(args, self.memory)["payload"])
        self.assertEqual(payload["max_tokens"], 2400)
        self.assertEqual(payload["chapter"], 2)
        self.assertEqual(finance.claude_commitment("claude-haiku-4-5-20251001",200,1000,2400),203)
        with self.assertRaises(Refused):
            chapters.prompt("x", 7)

    def test_assembly_and_truncation(self):
        ids = []
        # Seed historical results without calling the provider or changing production quota.
        for n in range(1,7):
            row = self.memory.propose("claude", {"dossier_id": self.dossier, "chapter": n}, 203)
            with self.memory.transaction() as query:
                import json
                query("update approvals set status='done', result=? where id=?",
                      json.dumps({"draft": f"Unique text {n}.", "stop_reason":"end_turn"}), row["id"])
            ids.append(row["id"])
        text = chapters.assemble(self.memory, self.dossier, ids)
        self.assertIn("Chapter 6", text)
        with self.assertRaises(Refused):
            chapters.assemble(self.memory, self.dossier, ids[:5]+ids[:1])
        with self.memory.transaction() as query:
            query("update approvals set result=? where id=?",
                  '{"draft":"Partial","stop_reason":"max_tokens"}', ids[-1])
        with self.assertRaises(Refused):
            chapters.assemble(self.memory, self.dossier, ids)
