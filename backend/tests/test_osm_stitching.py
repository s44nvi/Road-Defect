"""
Pure-Python tests for import_osm_segments.stitch().

Overpass returns a road's ways in no guaranteed order (not necessarily
geographic) and does not guarantee a way's node order matches the direction of
travel, so stitch() must reassemble the corridor regardless of input order or
orientation, without ever bridging a genuine gap in the road.
"""

from __future__ import annotations

from itertools import permutations

import pytest

from backend.app.road_health.geo import linestring_length_km
from backend.scripts.import_osm_segments import stitch


# A single 4-leg corridor, split into 4 ways.
WAY_1 = [[72.80, 19.00], [72.805, 19.00]]
WAY_2 = [[72.805, 19.00], [72.81, 19.00]]
WAY_3 = [[72.81, 19.00], [72.815, 19.00]]
WAY_4 = [[72.815, 19.00], [72.82, 19.00]]
FULL_CORRIDOR = WAY_1 + WAY_2[1:] + WAY_3[1:] + WAY_4[1:]
FULL_LENGTH = linestring_length_km(FULL_CORRIDOR)


def _same_corridor(result: list[list[float]], expected_length: float) -> bool:
    """Two stitched results represent the same corridor if they measure the
    same length -- direction (forward vs reversed) is not meaningful here."""
    return abs(linestring_length_km(result) - expected_length) < 1e-6


# ---------------------------------------------------------------------------
# The exact case from the Step 5 verification: every ordering of 4 ways must
# fully stitch, not just the 6/24 that worked before the fix.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("order", list(permutations([WAY_1, WAY_2, WAY_3, WAY_4])))
def test_every_ordering_of_four_ways_fully_stitches(order):
    result = stitch(list(order))

    assert _same_corridor(result, FULL_LENGTH), (
        f"incomplete stitch for order {[id(w) for w in order]}: "
        f"got {linestring_length_km(result):.3f} km, expected {FULL_LENGTH:.3f} km"
    )


def test_all_24_permutations_now_succeed():
    """Directly reproduces the Step 5 measurement (was 6/24, must now be 24/24)."""
    complete = sum(
        1
        for order in permutations([WAY_1, WAY_2, WAY_3, WAY_4])
        if _same_corridor(stitch(list(order)), FULL_LENGTH)
    )

    assert complete == 24


# ---------------------------------------------------------------------------
# Reversed ways, in isolation
# ---------------------------------------------------------------------------
def test_a_single_reversed_way_in_the_middle_is_still_joined():
    ways = [WAY_1, list(reversed(WAY_2)), WAY_3, WAY_4]

    result = stitch(ways)

    assert _same_corridor(result, FULL_LENGTH)


def test_every_way_reversed_still_fully_stitches():
    ways = [list(reversed(w)) for w in (WAY_1, WAY_2, WAY_3, WAY_4)]

    result = stitch(ways)

    assert _same_corridor(result, FULL_LENGTH)


def test_the_first_way_in_the_list_being_reversed_does_not_break_stitching():
    ways = [list(reversed(WAY_3)), WAY_1, WAY_4, WAY_2]

    result = stitch(ways)

    assert _same_corridor(result, FULL_LENGTH)


# ---------------------------------------------------------------------------
# Extending from either end
# ---------------------------------------------------------------------------
def test_stitching_extends_from_the_head_not_just_the_tail():
    """Seed in the middle of the corridor; ways before it must be prepended."""
    ways = [WAY_3, WAY_4, WAY_1, WAY_2]

    result = stitch(ways)

    assert _same_corridor(result, FULL_LENGTH)


def test_the_seed_way_being_the_last_leg_still_grows_backward():
    ways = [WAY_4, WAY_3, WAY_2, WAY_1]

    result = stitch(ways)

    assert _same_corridor(result, FULL_LENGTH)


def test_stitched_coordinates_trace_the_real_geometry_in_some_direction():
    """The result must be the ACTUAL corridor coordinates -- not merely the
    right length, but forward or exactly reversed, nothing fabricated."""
    ways = [WAY_3, WAY_1, WAY_4, WAY_2]

    result = stitch(ways)

    assert result == FULL_CORRIDOR or result == list(reversed(FULL_CORRIDOR))


# ---------------------------------------------------------------------------
# Disconnected / gapped ways: must NOT be bridged
# ---------------------------------------------------------------------------
GAP_WAY_A = [[72.83, 19.00], [72.835, 19.00]]
GAP_WAY_B = [[72.835, 19.00], [72.84, 19.00]]
GAP_CLUSTER_LENGTH = linestring_length_km(GAP_WAY_A + GAP_WAY_B[1:])


def test_a_genuine_gap_is_not_bridged_result_is_the_larger_cluster():
    """WAY_1..4 form a 4-leg corridor; GAP_WAY_A/B are a separate 2-leg
    fragment ~2km away -- well past the default 0.05 km tolerance. The two
    must never be joined into one polyline."""
    ways = [WAY_4, GAP_WAY_A, WAY_1, GAP_WAY_B, WAY_3, WAY_2]

    result = stitch(ways)

    # The larger, real cluster must be the one returned.
    assert _same_corridor(result, FULL_LENGTH)
    # And it must not have silently absorbed the disconnected fragment.
    assert abs(linestring_length_km(result) - (FULL_LENGTH + GAP_CLUSTER_LENGTH)) > 1e-6


def test_gap_tolerance_is_still_respected_at_the_boundary():
    """A way just inside the tolerance is joined; just outside, it is not."""
    base = [[72.80, 19.00], [72.805, 19.00]]

    just_inside = [[72.805 + 0.0003, 19.00], [72.81, 19.00]]  # ~30m gap
    just_outside = [[72.805 + 0.002, 19.00], [72.81, 19.00]]  # ~200m gap

    inside_result = stitch([base, just_inside], gap_tolerance_km=0.05)
    outside_result = stitch([base, just_outside], gap_tolerance_km=0.05)

    assert linestring_length_km(inside_result) > linestring_length_km(base) + 0.001
    assert _same_corridor(outside_result, linestring_length_km(base)) or _same_corridor(
        outside_result, linestring_length_km(just_outside)
    )


def test_two_entirely_separate_two_way_clusters_each_stay_intact():
    """When no cluster is a clear 'main corridor', the function still returns
    a real, unfabricated cluster (the longer of the two) rather than
    inventing a connection between them."""
    ways = [WAY_1, WAY_2, GAP_WAY_A, GAP_WAY_B]

    result = stitch(ways)

    two_leg_length = linestring_length_km(WAY_1 + WAY_2[1:])
    assert _same_corridor(result, two_leg_length)


# ---------------------------------------------------------------------------
# Trivial cases
# ---------------------------------------------------------------------------
def test_empty_ways_list_returns_empty():
    assert stitch([]) == []


def test_a_single_way_is_returned_unchanged():
    result = stitch([WAY_1])

    assert result == WAY_1
