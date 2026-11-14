import json
import tempfile
import unittest
from pathlib import Path

from src.core.bus import MessageBus
from src.core.message import Performative
from src.core.trace import TraceRecorder


class MessageBusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.trace = TraceRecorder()
        self.bus = MessageBus(self.trace)
        self.bus.register("a", "b")

    def test_direct_message_is_delivered_once(self) -> None:
        self.bus.send(Performative.REQUEST, "a", "b", {"action": "do"})
        self.assertEqual(self.bus.pending("b"), 1)
        messages = self.bus.drain("b")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].sender, "a")
        self.assertEqual(messages[0].content["action"], "do")
        self.assertEqual(self.bus.pending("b"), 0)
        self.assertEqual(self.bus.drain("b"), [])

    def test_broadcast_reaches_registered_agents(self) -> None:
        self.bus.broadcast(Performative.INFORM, "a", {"event": "hello"})
        self.assertEqual(len(self.bus.drain("a")), 1)
        self.assertEqual(len(self.bus.drain("b")), 1)
        self.assertEqual(self.bus.history[0].receiver, "*")

    def test_stats_and_performatives(self) -> None:
        self.bus.send(Performative.REQUEST, "a", "b")
        self.bus.send(Performative.INFORM, "b", "a")
        self.assertEqual(self.bus.count_by_performative(), {"request": 1, "inform": 1})
        self.assertEqual(self.bus.stats[("a", "b", "request")], 1)

    def test_trace_records_message(self) -> None:
        self.bus.send(Performative.AGREE, "a", "b", {"event": "ok"}, "c-1")
        events = [event for event in self.trace.events if event["kind"] == "message"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["conversation_id"], "c-1")


class TraceRecorderTest(unittest.TestCase):
    def test_writes_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            with TraceRecorder(path) as trace:
                trace.event("tick", tick=1)
                trace.event("tick", tick=2)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["tick"], 1)


if __name__ == "__main__":
    unittest.main()
