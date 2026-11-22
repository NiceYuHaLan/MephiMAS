import unittest

from src.conflict import CONFLICT_MODES, get_resolver, list_resolvers
from src.conflict.base import REPUTATION_CAP, REPUTATION_FLOOR, STARVE_LIMIT
from src.scenarios.models import OrderSpec
from src.simulation import Simulation


class ConflictRegistryTest(unittest.TestCase):
    def test_all_modes_registered(self) -> None:
        self.assertEqual(set(CONFLICT_MODES), {"fcfs", "negotiation", "arbitration"})
        self.assertEqual(len(list_resolvers()), 3)

    def test_unknown_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_resolver("no_such_mode")

    def test_modes_have_labels(self) -> None:
        for name in CONFLICT_MODES:
            resolver = get_resolver(name)
            self.assertEqual(resolver.name, name)
            self.assertTrue(resolver.label)


class ResolverUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.simulation = Simulation("smoke")
        self.addCleanup(self.simulation.close)
        self.env = self.simulation.env
        self.krabs = next(agent for agent in self.env.agents if agent.id == "krabs")
        self.order_a = self.env.create_order(
            OrderSpec(0, "Тестовый А", 1, ("krabby_patty",))
        )
        self.order_b = self.env.create_order(
            OrderSpec(0, "Тестовый Б", 2, ("krabby_patty",), priority=1)
        )

    def test_reputation_is_clamped(self) -> None:
        resolver = get_resolver("fcfs")
        resolver.adjust("spongebob", 5.0, None, "test")
        self.assertEqual(resolver.reputation["spongebob"], REPUTATION_CAP)
        resolver.adjust("spongebob", -10.0, None, "test")
        self.assertEqual(resolver.reputation["spongebob"], REPUTATION_FLOOR)

    def test_fcfs_grants_in_arrival_order(self) -> None:
        resolver = get_resolver("fcfs")
        resolver.submit(
            {"station_kind": "grill", "order_id": self.order_a.order_id},
            "spongebob",
            1,
        )
        resolver.submit(
            {"station_kind": "grill", "order_id": self.order_b.order_id},
            "patrick",
            2,
        )
        order = [claim["agent"] for claim in resolver.grant_order(self.env)]
        self.assertEqual(order, ["spongebob", "patrick"])

    def test_arbitration_ranks_priority_first(self) -> None:
        resolver = get_resolver("arbitration")
        resolver.submit(
            {"station_kind": "grill", "order_id": self.order_a.order_id,
             "task_index": 0},
            "spongebob",
            1,
        )
        resolver.submit(
            {"station_kind": "grill", "order_id": self.order_b.order_id,
             "task_index": 0},
            "patrick",
            2,
        )
        ranked = resolver._rank(resolver.queue, self.env)
        self.assertEqual(ranked[0]["agent"], "patrick")
        self.assertEqual(ranked[1]["agent"], "spongebob")

    def test_starved_claim_is_counted(self) -> None:
        resolver = get_resolver("fcfs")
        resolver.submit(
            {"station_kind": "grill", "order_id": self.order_a.order_id},
            "spongebob",
            self.env.tick - STARVE_LIMIT - 1,
        )
        resolver.resolve(self.krabs, self.env)
        self.assertEqual(resolver.starved, 1)


class StationRushTest(unittest.TestCase):
    def run_mode(self, mode: str):
        simulation = Simulation("station_rush", conflict=mode)
        self.addCleanup(simulation.close)
        metrics = simulation.run()
        return simulation, metrics

    def assert_all_served(self, metrics: dict) -> None:
        self.assertEqual(metrics["orders_served"], 10)
        self.assertEqual(metrics["orders_cancelled"], 0)
        self.assertEqual(metrics["violations"], 0)

    def test_fcfs_is_baseline_without_negotiation(self) -> None:
        simulation, metrics = self.run_mode("fcfs")
        self.assert_all_served(metrics)
        self.assertGreaterEqual(metrics["conflict_events"], 1)
        self.assertEqual(metrics["conflict_mode"], "fcfs")
        self.assertEqual(metrics["negotiation_rounds"], 0)
        self.assertEqual(metrics["conflict_messages"], 0)

    def test_arbitration_resolves_by_rules(self) -> None:
        simulation, metrics = self.run_mode("arbitration")
        self.assert_all_served(metrics)
        self.assertGreaterEqual(metrics["conflict_events"], 1)
        self.assertEqual(metrics["negotiation_rounds"], 0)
        self.assertEqual(metrics["conflict_messages"], 0)

    def test_negotiation_runs_full_protocol(self) -> None:
        simulation, metrics = self.run_mode("negotiation")
        self.assert_all_served(metrics)
        self.assertGreaterEqual(metrics["negotiation_rounds"], 2)
        self.assertGreaterEqual(metrics["conflict_messages"], 4)
        self.assertGreaterEqual(
            metrics["agreements"] + metrics["sanctions"], 1
        )
        events = simulation.trace.events
        detected = [e for e in events if e["kind"] == "conflict_detected"]
        resolved = [e for e in events if e["kind"] == "conflict_resolved"]
        self.assertGreaterEqual(len(detected), 2)
        self.assertEqual(len(resolved), metrics["negotiation_rounds"])
        outcomes = {e["outcome"] for e in resolved}
        self.assertTrue(outcomes <= {"agreement", "sanctioned", "refusal", "timeout", "tie"})

    def test_positions_reflect_greediness(self) -> None:
        simulation, metrics = self.run_mode("negotiation")
        offers = [e for e in simulation.trace.events if e["kind"] == "negotiation_offer"]
        self.assertGreater(len(offers), 0)
        by_agent = {}
        for offer in offers:
            by_agent.setdefault(offer["agent"], set()).add(offer["can_yield"])
        self.assertEqual(by_agent.get("spongebob"), {True})
        self.assertEqual(by_agent.get("patrick"), {False})

    def test_greedy_loser_is_sanctioned(self) -> None:
        simulation, metrics = self.run_mode("negotiation")
        resolved = [
            e for e in simulation.trace.events if e["kind"] == "conflict_resolved"
        ]
        sanctioned = [e for e in resolved if e["outcome"] == "sanctioned"]
        self.assertGreaterEqual(len(sanctioned), 1)
        self.assertTrue(all(e["loser"] == "patrick" for e in sanctioned))
        self.assertLess(metrics["reputation"]["patrick"], 1.0)

    def test_metrics_expose_conflict_snapshot(self) -> None:
        _, metrics = self.run_mode("negotiation")
        for key in (
            "conflict_mode",
            "conflict_events",
            "contention_ticks",
            "negotiation_rounds",
            "negotiation_messages",
            "agreements",
            "yields",
            "sanctions",
            "violations",
            "starved",
            "station_wait_avg",
            "station_wait_max",
            "reputation_mean",
        ):
            self.assertIn(key, metrics)


if __name__ == "__main__":
    unittest.main()
