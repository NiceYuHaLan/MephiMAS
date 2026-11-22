import unittest

from src.domain.models import OrderStatus
from src.simulation import Simulation


class SimulationTest(unittest.TestCase):
    def run_scenario(self, name: str) -> Simulation:
        simulation = Simulation(name)
        simulation.run()
        self.addCleanup(simulation.close)
        return simulation

    def test_smoke_scenario_completes(self) -> None:
        simulation = self.run_scenario("smoke")
        env = simulation.env
        self.assertTrue(env.finished)
        self.assertTrue(all(order.status == OrderStatus.SERVED for order in env.orders.values()))
        metrics = env.metrics.snapshot()
        self.assertEqual(metrics["orders_served"], 2)
        self.assertEqual(metrics["orders_cancelled"], 0)
        self.assertGreater(metrics["messages_total"], 0)
        self.assertGreater(metrics["revenue"], 0)

    def test_dinner_rush_uses_both_cooks(self) -> None:
        simulation = self.run_scenario("dinner_rush")
        metrics = simulation.env.metrics.snapshot()
        self.assertEqual(metrics["orders_served"], 7)
        self.assertIn("spongebob", metrics["workload"])
        self.assertIn("patrick", metrics["workload"])
        self.assertGreater(metrics["tasks_completed"], 0)

    def test_sandy_repairs_broken_station(self) -> None:
        simulation = self.run_scenario("sandy_check")
        events = simulation.trace.events
        broken = [event for event in events if event["kind"] == "station_broken"]
        repaired = [event for event in events if event["kind"] == "station_repaired"]
        self.assertEqual(len(broken), 1)
        self.assertGreaterEqual(len(repaired), 1)
        self.assertGreaterEqual(repaired[-1]["tick"], broken[0]["tick"])
        self.assertTrue(
            all(order.status == OrderStatus.SERVED for order in simulation.env.orders.values())
        )

    def test_plankton_request_is_refused(self) -> None:
        simulation = self.run_scenario("plankton_probe")
        messages = simulation.env.bus.history
        requests = [
            message
            for message in messages
            if message.sender == "plankton" and message.receiver == "krabs"
        ]
        refusals = [
            message
            for message in messages
            if message.sender == "krabs" and message.receiver == "plankton"
        ]
        self.assertEqual(len(requests), 1)
        self.assertEqual(len(refusals), 1)
        self.assertEqual(refusals[0].performative.value, "refuse")
        self.assertTrue(
            all(order.status == OrderStatus.SERVED for order in simulation.env.orders.values())
        )

    def test_runs_are_deterministic(self) -> None:
        first = self.run_scenario("smoke")
        second = self.run_scenario("smoke")
        self.assertEqual(first.snapshot(), second.snapshot())
        first_events = [(event["kind"], event.get("tick")) for event in first.trace.events]
        second_events = [(event["kind"], event.get("tick")) for event in second.trace.events]
        self.assertEqual(first_events, second_events)


if __name__ == "__main__":
    unittest.main()
