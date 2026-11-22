import unittest

from src.core.message import Performative
from src.domain.models import OrderStatus
from src.mechanisms import (
    MECHANISMS,
    AuctionMechanism,
    CentralDispatchMechanism,
    ContractNetMechanism,
    get_mechanism,
)
from src.simulation import Simulation


class MechanismRegistryTest(unittest.TestCase):
    def test_all_mechanisms_registered(self) -> None:
        self.assertEqual(set(MECHANISMS), {"central", "contract_net", "auction"})

    def test_get_mechanism_returns_fresh_instance(self) -> None:
        first = get_mechanism("central")
        second = get_mechanism("central")
        self.assertIsInstance(first, CentralDispatchMechanism)
        self.assertIsNot(first, second)

    def test_unknown_mechanism_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_mechanism("nope")


class CentralMechanismTest(unittest.TestCase):
    def test_assigns_by_priority(self) -> None:
        simulation = Simulation("smoke", mechanism="central")
        self.addCleanup(simulation.close)
        simulation.run()
        assigns = {
            event["order_id"]: event["agent"]
            for event in simulation.trace.events
            if event["kind"] == "order_assigned"
        }
        self.assertEqual(assigns.get("O-001"), "spongebob")
        metrics = simulation.env.metrics.snapshot()
        self.assertEqual(metrics["mechanism"], "central")
        self.assertGreater(metrics["messages_total"], 0)


class ContractNetMechanismTest(unittest.TestCase):
    def test_uses_cfp_propose_accept(self) -> None:
        simulation = Simulation("dinner_rush", mechanism="contract_net")
        self.addCleanup(simulation.close)
        simulation.run()
        performatives = simulation.env.metrics.snapshot()["messages_by_performative"]
        self.assertIn("cfp", performatives)
        self.assertIn("propose", performatives)
        self.assertIn("accept", performatives)

    def test_all_orders_served(self) -> None:
        simulation = Simulation("dinner_rush", mechanism="contract_net")
        self.addCleanup(simulation.close)
        metrics = simulation.run()
        self.assertEqual(metrics["orders_served"], 7)
        self.assertEqual(metrics["orders_open"], 0)

    def test_single_open_cfp_at_a_time(self) -> None:
        simulation = Simulation("stress_rush", mechanism="contract_net")
        self.addCleanup(simulation.close)
        simulation.run()
        krabs = next(agent for agent in simulation.env.agents if agent.id == "krabs")
        self.assertEqual(len(krabs.mechanism.open_cfps), 0)


class AuctionMechanismTest(unittest.TestCase):
    def test_records_payments(self) -> None:
        simulation = Simulation("dinner_rush", mechanism="auction")
        self.addCleanup(simulation.close)
        metrics = simulation.run()
        self.assertGreater(metrics["coordination_spend"], 0)
        self.assertEqual(metrics["orders_served"], 7)

    def test_bids_have_prices(self) -> None:
        simulation = Simulation("smoke", mechanism="auction")
        self.addCleanup(simulation.close)
        simulation.run()
        bids = [
            event
            for event in simulation.trace.events
            if event["kind"] == "bid_received"
        ]
        self.assertGreater(len(bids), 0)
        self.assertTrue(all("price" in event for event in bids))


class ComparisonTest(unittest.TestCase):
    def test_mechanisms_produce_different_assignments(self) -> None:
        assignments = {}
        for mechanism in ("contract_net", "auction"):
            simulation = Simulation("dinner_rush", mechanism=mechanism)
            self.addCleanup(simulation.close)
            simulation.run()
            assignments[mechanism] = [
                (event["order_id"], event["agent"])
                for event in simulation.trace.events
                if event["kind"] == "order_assigned"
            ]
        self.assertNotEqual(
            assignments["contract_net"],
            assignments["auction"],
            "контрактная сеть и аукцион должны принимать разные решения",
        )

    def test_runs_are_deterministic_per_mechanism(self) -> None:
        for mechanism in MECHANISMS:
            first = Simulation("smoke", mechanism=mechanism)
            self.addCleanup(first.close)
            second = Simulation("smoke", mechanism=mechanism)
            self.addCleanup(second.close)
            first_metrics = first.run()
            second_metrics = second.run()
            self.assertEqual(first_metrics, second_metrics, mechanism)


class CoordinationMetricsTest(unittest.TestCase):
    def test_central_has_fewer_coordination_messages(self) -> None:
        counts = {}
        for mechanism in ("central", "contract_net"):
            simulation = Simulation("stress_rush", mechanism=mechanism)
            self.addCleanup(simulation.close)
            metrics = simulation.run()
            counts[mechanism] = metrics["coordination_messages"]
        self.assertLess(counts["central"], counts["contract_net"])

    def test_assignment_latency_recorded(self) -> None:
        simulation = Simulation("smoke", mechanism="central")
        self.addCleanup(simulation.close)
        metrics = simulation.run()
        self.assertGreater(metrics["assignment_latency_avg"], 0)
        orders = simulation.env.orders
        self.assertTrue(
            all(order.assigned_tick is not None for order in orders.values())
        )

    def test_served_orders_leave_assigned_state(self) -> None:
        simulation = Simulation("smoke", mechanism="auction")
        self.addCleanup(simulation.close)
        simulation.run()
        for order in simulation.env.orders.values():
            self.assertIn(
                order.status,
                (OrderStatus.SERVED, OrderStatus.CANCELLED),
            )


if __name__ == "__main__":
    unittest.main()
