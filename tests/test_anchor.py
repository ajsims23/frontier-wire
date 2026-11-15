from agent.recap import ANCHORS, anchor_for


def test_anchor_alternates_daily():
    a, b, c = anchor_for("2026-11-16"), anchor_for("2026-11-17"), anchor_for("2026-11-18")
    assert a != b and a == c
    assert {a["aura"], b["aura"]} == {ANCHORS["female"]["aura"], ANCHORS["male"]["aura"]}
    assert anchor_for("2026-12-31") != anchor_for("2027-01-01")  # no repeat across the year end
