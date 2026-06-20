"""Scene file I/O for the authoring tool: list, write (+backup), read round-trip."""

import shutil

from simsy import scene
from simsy.project import PROJECTS_DIR, scene_path


def test_list_scenes_finds_data_projects():
    names = scene.list_scenes()
    assert "coffee_shop" in names and "cafe" in names


def test_write_then_read_round_trips_and_keeps_one_backup():
    name = "_iotest"
    data = {
        "name": name,
        "world": {"bounds": [-5.0, -5.0, 5.0, 5.0]},
        "objects": [{"id": "o", "kind": "Thing", "pos": [1.0, 2.0], "slots": 2}],
    }
    try:
        scene.write_scene(name, data)
        assert scene_path(name).exists()
        assert scene.read_scene(name) == data  # exact round-trip

        scene.write_scene(name, data)  # a second save backs up the prior file
        assert scene_path(name).with_suffix(".yaml.bak").exists()

        # the written scene is also loadable into a Simulation
        from simsy.scene import load_scene_file
        sim = load_scene_file(scene_path(name))
        assert sim.world.get("o") is not None
    finally:
        shutil.rmtree(PROJECTS_DIR / name, ignore_errors=True)
