import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from bodive import supervisor
from bodive.memory import Memory

class TelegramControls(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.memory = Memory("simulation", Path(directory.name) / "db.sqlite")
        self.telegram = Mock(operator=42)
        self.row = self.memory.propose("claude", {"model":"x","prompt":"test","max_tokens":2400},203)

    def callback(self, action, sender=42, prefix=None):
        data = supervisor.button("test", action, self.row)["callback_data"]
        if prefix is not None:
            data = data[:-24] + prefix
        return {"id":"callback", "data":data, "from":{"id":sender,"is_bot":False},
                "message":{"chat":{"id":42,"type":"private"}}}

    def test_button_authorization_and_replay(self):
        from bodive.memory import Refused
        cb = self.callback("a")
        self.assertLessEqual(len(cb["data"].encode()),64)
        supervisor.on_callback(self.memory,self.telegram,self.callback("a",sender=41))
        self.assertEqual(self.memory.get(self.row["id"])["status"],"pending")
        with self.assertRaises(Refused):
            supervisor.on_callback(self.memory,self.telegram,self.callback("a",prefix="0"*24))
        supervisor.on_callback(self.memory,self.telegram,cb)
        self.assertEqual(self.memory.get(self.row["id"])["status"],"approved")
        with self.assertRaises(Refused):
            supervisor.on_callback(self.memory,self.telegram,cb)

    def test_generation_requires_separate_action(self):
        self.telegram.updates.return_value = [{"update_id":1,"callback_query":self.callback("a")}]
        with patch("bodive.cli.execute") as execute:
            supervisor.poll(self.memory,self.telegram)
            execute.assert_not_called()
            self.telegram.updates.return_value = [
                {"update_id":2,"callback_query":self.callback("g")},
                {"update_id":3,"callback_query":self.callback("g")}]
            execute.return_value = {"complete_draft":True}
            supervisor.poll(self.memory,self.telegram)
            execute.assert_called_once()
            self.assertEqual(execute.call_args.args[0].id,self.row["id"])
