import unittest

from src.core.message import Message, Performative
from src.domain.models import Order, OrderStatus
from src.security import (
    ATTACKS,
    ATTACK_SCENARIOS,
    GUARDS,
    get_attack,
)
from src.security.base import Verdict, canonical_payload
from src.security.guards import (
    AuthenticationGuard,
    AuthorizationGuard,
    ConsistencyGuard,
    CycleGuard,
    IntegrityGuard,
    ProvenanceGuard,
    ReplayGuard,
)
from src.simulation import Simulation


def run_attack(name: str, defense: bool) -> dict:
    scenario = ATTACK_SCENARIOS[name]
    simulation = Simulation(scenario, attack=name, defense=defense)
    try:
        metrics = simulation.run()
    finally:
        simulation.close()
    return metrics


class RegistryTest(unittest.TestCase):
    def test_all_attacks_registered(self) -> None:
        self.assertEqual(len(ATTACKS), 8)
        for name in (
            "forgery",
            "tampering",
            "replay",
            "goal_substitution",
            "cyclic_delegation",
            "contradictory",
            "instruction_injection",
            "tool_unavailable",
        ):
            self.assertIn(name, ATTACKS)
            self.assertIn(name, ATTACK_SCENARIOS)

    def test_guards_registered(self) -> None:
        self.assertEqual(len(GUARDS), 7)
        for name in (
            "authentication",
            "integrity",
            "replay",
            "authorization",
            "provenance",
            "consistency",
            "cycle",
        ):
            self.assertIn(name, GUARDS)

    def test_unknown_attack_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_attack("nope")


class AttackSuiteTest(unittest.TestCase):
    def test_each_attack_causes_failure_without_defense(self) -> None:
        for name in ATTACKS:
            with self.subTest(attack=name):
                metrics = run_attack(name, defense=False)
                self.assertGreater(
                    metrics["failures_total"],
                    0,
                    f"атака {name} не привела к отказу",
                )

    def test_defense_blocks_or_recovers_each_attack(self) -> None:
        for name in ATTACKS:
            with self.subTest(attack=name):
                metrics = run_attack(name, defense=True)
                self.assertEqual(
                    metrics["failures_total"], 0, f"защита не справилась с {name}"
                )
                self.assertEqual(metrics["lost_orders"], 0)
                self.assertEqual(
                    metrics["orders_served"], metrics["orders_total"]
                )

    def test_clean_run_has_no_false_positives(self) -> None:
        for scenario in ("smoke", "dinner_rush", "stress_rush"):
            with self.subTest(scenario=scenario):
                off = Simulation(scenario, defense=False)
                metrics_off = off.run()
                off.close()
                on = Simulation(scenario, defense=True)
                metrics_on = on.run()
                on.close()
                self.assertEqual(metrics_on["attacks_blocked"], 0)
                self.assertEqual(metrics_on["failures_total"], 0)
                self.assertEqual(metrics_off["orders_served"], metrics_on["orders_served"])
                self.assertEqual(metrics_off["makespan"], metrics_on["makespan"])

    def test_attack_runs_are_deterministic(self) -> None:
        first = run_attack("contradictory", defense=False)
        second = run_attack("contradictory", defense=False)
        for key in ("orders_served", "failures_total", "double_assignment"):
            self.assertEqual(first[key], second[key])

    def test_metrics_contain_security_keys(self) -> None:
        metrics = run_attack("forgery", defense=True)
        for key in (
            "attack",
            "defense",
            "attacks_injected",
            "attacks_blocked",
            "auth_failures",
            "integrity_failures",
            "replay_blocked",
            "authorization_denied",
            "provenance_denied",
            "consistency_denied",
            "cycle_blocked",
            "phantom_served",
            "double_serve",
            "double_assignment",
            "cycle_events",
            "lost_orders",
            "failures_total",
            "integrity_score",
            "false_positives",
        ):
            self.assertIn(key, metrics)


class GuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sim = Simulation("smoke", defense=True)
        self.addCleanup(self.sim.close)
        self.env = self.sim.env

    def message(self, **kwargs) -> Message:
        defaults = dict(
            performative=Performative.INFORM,
            sender="spongebob",
            receiver="krabs",
            content={},
            tick=self.env.tick,
            nonce=1,
        )
        defaults.update(kwargs)
        return Message(**defaults)

    def test_authentication_rejects_unsigned(self) -> None:
        verdict = AuthenticationGuard().check(self.message(), self.env)
        self.assertFalse(verdict.allow)
        self.assertEqual(verdict.kind, "auth")

    def test_integrity_rejects_tampering(self) -> None:
        message = self.message(content={"event": "order_complete", "order_id": "O-001"})
        self.env.gateway.sign(message, "spongebob")
        self.assertTrue(
            IntegrityGuard().check(message, self.env).allow
        )
        message.content["order_id"] = "O-002"
        verdict = IntegrityGuard().check(message, self.env)
        self.assertFalse(verdict.allow)
        self.assertEqual(verdict.kind, "integrity")

    def test_replay_rejects_duplicate(self) -> None:
        guard = ReplayGuard()
        message = self.message(content={"event": "x"})
        first = guard.check(message, self.env)
        second = guard.check(message, self.env)
        self.assertTrue(first.allow)
        self.assertEqual(second.kind, "replay")

    def test_authorization_rejects_foreign_completion(self) -> None:
        message = self.message(
            sender="plankton",
            content={"event": "order_complete", "order_id": "O-001"},
        )
        verdict = AuthorizationGuard().check(message, self.env)
        self.assertFalse(verdict.allow)
        self.assertEqual(verdict.kind, "authorization")

    def test_provenance_rejects_untrusted_instruction(self) -> None:
        message = self.message(
            sender="plankton",
            content={"action": "station", "order_id": "O-001"},
        )
        verdict = ProvenanceGuard().check(message, self.env)
        self.assertFalse(verdict.allow)
        self.assertEqual(verdict.kind, "provenance")

    def test_consistency_rejects_double_assignment(self) -> None:
        order = Order(
            order_id="O-999",
            customer="Тест",
            table=1,
            items=["krabby_patty"],
            created_tick=0,
            deadline=100,
            status=OrderStatus.ASSIGNED,
            assignee="spongebob",
        )
        self.env.orders[order.order_id] = order
        message = self.message(
            performative=Performative.REQUEST,
            receiver="patrick",
            content={"action": "cook_order", "order_id": order.order_id},
        )
        verdict = ConsistencyGuard().check(message, self.env)
        self.assertFalse(verdict.allow)
        self.assertEqual(verdict.kind, "consistency")

    def test_cycle_rejects_duplicate_claim_in_tick(self) -> None:
        guard = CycleGuard()
        message = self.message(
            performative=Performative.REQUEST,
            content={"action": "station", "order_id": "O-001", "task_index": 0},
        )
        self.assertTrue(guard.check(message, self.env).allow)
        self.assertEqual(guard.check(message, self.env).kind, "cycle")

    def test_audit_recovers_substituted_goal(self) -> None:
        metrics = run_attack("goal_substitution", defense=True)
        self.assertEqual(metrics["phantom_served"], 0)
        self.assertGreater(metrics["audit_failures"], 0)
        self.assertGreater(metrics["reassignments"], 0)

    def test_fallback_repair_restores_station(self) -> None:
        metrics = run_attack("tool_unavailable", defense=True)
        self.assertEqual(metrics["lost_orders"], 0)
        self.assertGreater(metrics["fallback_repairs"], 0)

    def test_canonical_payload_stable(self) -> None:
        message = self.message(content={"b": 2, "a": 1})
        self.assertEqual(
            canonical_payload(message),
            canonical_payload(self.message(content={"a": 1, "b": 2})),
        )


if __name__ == "__main__":
    unittest.main()
