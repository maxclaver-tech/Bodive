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
