"""Portals / multi-venue: a guest crosses a gapless wall via a portal to reach
coffee in the other venue."""

from simsy.project import build_project
from simsy.world.smart_object import Portal, SmartObject


def test_portal_links_to_its_target():
    p = SmartObject("p", "Portal", (-3.0, 0.0), [], tags={"portal"})
    assert p.portal is None
    p.enable_portal(target=(3.0, 0.0))
    assert isinstance(p.portal, Portal)
    assert p.portal.target == (3.0, 0.0)


def test_guests_cross_to_the_other_venue_via_portal_and_get_served():
    sim = build_project("micro.venue", n_agents=2)
    crossed: set[str] = set()
    drank: set[str] = set()
    prev: dict[str, float] = {}
    for _ in range(500):
        sim.step()
        for a in sim.agents:
            if not a.id.startswith("g"):
                continue
            if a.position[0] > 1.0:  # only the portal can put them right of the wall
                crossed.add(a.id)
            c = a.drives.needs["Caffeine"]
            if a.id in prev and c < prev[a.id] - 1:
                drank.add(a.id)
            prev[a.id] = c

    assert crossed == {"g0", "g1"}, "both guests crossed into venue B (only via the portal)"
    assert drank == {"g0", "g1"}, "both got coffee in venue B"


def test_venue_scene_is_deterministic():
    def trace():
        sim = build_project("micro.venue", n_agents=2)
        out = []
        for _ in range(200):
            sim.step()
            out.append(tuple(round(c, 4) for a in sim.agents for c in a.position))
        return out

    assert trace() == trace()
