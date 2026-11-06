import json

import pytest

from devguide.recipes import BWRecipe, C41Kit, list_recipes, load_recipe


def test_hp5_times_match_ilford_sheet():
    r = load_recipe("bw_hp5_plus")
    assert isinstance(r, BWRecipe)
    assert r.developers["ilfosol3"]["1+9"][400] == 6.5
    assert r.developers["ddx"]["1+4"][3200] == 20
    assert r.developers["id11"]["1+1"][800] == 16.5
    assert r.temp_range_c == (16.0, 23.0)  # intervallo coperto dagli esempi della scheda


def test_cs41_table_matches_cinestill_sheet():
    k = load_recipe("c41_cinestill_cs41_liquid")
    assert isinstance(k, C41Kit)
    i39, i27 = k.temps_c.index(39.0), k.temps_c.index(27.0)
    assert k.times["normal"][i39] == 3.5
    assert k.times["push2"][i27] == 37
    assert k.times["push3"][i27] is None
    assert k.reuse_pct_per_roll["quart"] == 2.0


def test_every_recipe_cites_a_source():
    ids = list_recipes()
    assert {"bw_hp5_plus", "c41_cinestill_cs41_liquid"} <= set(ids)
    for rid in ids:
        assert load_recipe(rid).source.url.startswith("https://")


def _write(tmp_path, data):
    f = tmp_path / "x.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return str(f)


def _minimal_bw():
    return {
        "id": "x", "process": "bw", "film": "X", "iso_box": 400,
        "developers": {"d": {"1+1": {"400": 6}}},
        "temp_ref_c": 20, "temp_range_c": [18, 24], "temp_examples": [[6, 23, 4.5]],
        "agitation": {"initial_s": 10, "every_s": 60, "inversions": 4, "window_s": 10},
        "stop": {"name": "Arresto", "minutes": 0.17, "note": ""},
        "fix": {"name": "Fissaggio", "minutes": 3, "note": ""},
        "wash": "lavaggio",
        "source": {"title": "T", "url": "https://example.org", "date": "2018-11"},
    }


def test_recipe_without_source_is_rejected(tmp_path):
    d = _minimal_bw()
    del d["source"]
    with pytest.raises(ValueError, match="fonte"):
        load_recipe(_write(tmp_path, d))


def test_non_positive_time_is_rejected(tmp_path):
    d = _minimal_bw()
    d["developers"]["d"]["1+1"]["400"] = 0
    with pytest.raises(ValueError):
        load_recipe(_write(tmp_path, d))


def test_unknown_recipe_lists_available(tmp_path):
    with pytest.raises(ValueError, match="bw_hp5_plus"):
        load_recipe("nope")
