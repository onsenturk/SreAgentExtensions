"""Unit test for the cost_rank selection math. No Azure calls are made.

Run from the tools directory:
    python test_cost_rank.py
"""

from cost_rank import _select_top


def _make(n):
    return [{"name": f"item-{i}", "cost": float(n - i)} for i in range(n)]


def _selected_count(items):
    return sum(1 for item in items if item["selected"])


def test_floor_applies_for_three_subscriptions():
    items, count = _select_top(_make(3), top_percent=10, minimum=3)
    assert count == 3
    assert _selected_count(items) == 3


def test_floor_for_six_subscriptions():
    items, count = _select_top(_make(6), top_percent=10, minimum=3)
    assert count == 3
    assert _selected_count(items) == 3


def test_top_decile_for_two_hundred():
    items, count = _select_top(_make(200), top_percent=10, minimum=3)
    assert count == 20
    assert _selected_count(items) == 20


def test_resource_group_floor():
    items, count = _select_top(_make(6), top_percent=10, minimum=5)
    assert count == 5


def test_ranks_are_one_based_and_ordered():
    items, _ = _select_top(_make(4), top_percent=10, minimum=3)
    assert [item["rank"] for item in items] == [1, 2, 3, 4]


def test_empty_set():
    items, count = _select_top([], top_percent=10, minimum=3)
    assert count == 0
    assert items == []


if __name__ == "__main__":
    test_floor_applies_for_three_subscriptions()
    test_floor_for_six_subscriptions()
    test_top_decile_for_two_hundred()
    test_resource_group_floor()
    test_ranks_are_one_based_and_ordered()
    test_empty_set()
    print("All cost_rank selection tests passed.")
