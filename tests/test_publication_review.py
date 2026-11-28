import unittest
from bodive.memory import Refused
from bodive.publication_review import review_scope, verify_artifact


class PublicationReviewTests(unittest.TestCase):
    def test_exact_bytes(self):
        identifier = "a" * 32
        scope = review_scope(identifier, "product.xlsx", b"original")
        self.assertEqual(scope, verify_artifact(scope, identifier, "product.xlsx", b"original"))
        for dossier, name, data in [
            (identifier, "product.xlsx", b"modified"),
            ("b" * 32, "product.xlsx", b"original"),
            (identifier, "other.xlsx", b"original"),
        ]:
            with self.assertRaises(Refused):
                verify_artifact(scope, dossier, name, data)

    def test_invalid_input(self):
        for name, data in [("../product.xlsx", b"x"), ("product.xlsx", b""), ("product.xlsx", b"x" * 5000001)]:
            with self.assertRaises(Refused):
                review_scope("a" * 32, name, data)


    def test_persistent_handoff(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from bodive.memory import Memory, MANUAL_KINDS
        from bodive.publication_review import request_review, handoff
        with TemporaryDirectory() as tmp:
            memory = Memory("simulation", str(Path(tmp) / "state.sqlite"))
            dossier = memory.save({"topic": "test"})
            data = b"final artifact"
            row = request_review(memory, dossier, "product.xlsx", data)
            args = (memory, row["id"], dossier, "product.xlsx")
            with self.assertRaises(Refused):
                handoff(*args, data)
            memory.decide(row["id"], row["digest"], True, "simulation")
            with self.assertRaises(Refused):
                memory.claim(row["id"], MANUAL_KINDS)
            with self.assertRaises(Refused):
                handoff(*args, b"changed")
            self.assertFalse(handoff(*args, data)["published"])
            with self.assertRaises(Refused):
                handoff(*args, data)
            second = request_review(memory, dossier, "product.xlsx", data)
            memory.decide(second["id"], second["digest"], True, "simulation")
            memory.stop("simulation")
            with self.assertRaises(Refused):
                handoff(memory, second["id"], dossier, "product.xlsx", data)
