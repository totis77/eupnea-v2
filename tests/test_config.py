"""Config loading: defaults when absent, partial overrides, unknown-key tolerance."""

from simsy.config import Config, load_config


def test_missing_file_falls_back_to_defaults(tmp_path):
    cfg = load_config(tmp_path / "does_not_exist.yaml")
    assert cfg == Config()


def test_partial_override_leaves_other_defaults_intact(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(
        "orca:\n"
        "  time_horizon: 5.0\n"
        "population:\n"
        "  max: 20\n"
        "  unknown_key: 99\n"  # unknown keys are ignored, not an error
    )
    cfg = load_config(p)
    assert cfg.orca.time_horizon == 5.0          # overridden
    assert cfg.orca.neighbor_distance == 10.0    # untouched default
    assert cfg.population.max == 20              # overridden
    assert cfg.population.initial == 3           # untouched default
