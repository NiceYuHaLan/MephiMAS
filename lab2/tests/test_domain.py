import unittest

from src.domain.models import (
    Inventory,
    OrderStatus,
    StationKind,
    build_order_tasks,
)
from src.metrics.collector import gini, jain


class DomainTest(unittest.TestCase):
    def test_order_tasks_follow_recipes(self) -> None:
        tasks, price = build_order_tasks(["krabby_patty", "kelp_shake"])
        self.assertEqual([task.kind for task in tasks], [
            StationKind.GRILL,
            StationKind.ASSEMBLY,
            StationKind.SODA,
        ])
        self.assertEqual(price, 17)

    def test_inventory_consumes_and_rejects_shortage(self) -> None:
        inventory = Inventory({"patty": 2})
        self.assertTrue(inventory.consume({"patty": 2}))
        self.assertFalse(inventory.has({"patty": 1}))
        self.assertFalse(inventory.consume({"patty": 1}))
        self.assertEqual(inventory.stock["patty"], 0)

    def test_status_labels_are_russian(self) -> None:
        self.assertEqual(OrderStatus.SERVED.label, "подан")
        self.assertEqual(StationKind.FRYER.label, "фритюр")


class MetricsTest(unittest.TestCase):
    def test_gini_equal_distribution_is_zero(self) -> None:
        self.assertAlmostEqual(gini([5, 5, 5, 5]), 0.0)

    def test_gini_unequal_distribution_is_positive(self) -> None:
        self.assertGreater(gini([0, 0, 0, 10]), 0.5)

    def test_jain_bounds(self) -> None:
        self.assertAlmostEqual(jain([3, 3, 3]), 1.0)
        self.assertAlmostEqual(jain([10, 0, 0]), 1 / 3)
        self.assertEqual(jain([]), 0.0)


if __name__ == "__main__":
    unittest.main()
