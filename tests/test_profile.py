import json

import pytest

from filmengine.profile import FilmProfile, list_profiles, load_profile


def test_load_builtin_profile():
    p = load_profile("portra_400")
    assert isinstance(p, FilmProfile)
    assert p.type == "color_negative"
    assert len(p.gamma_rgb) == 3
    assert len(p.color_matrix) == 3 and all(len(r) == 3 for r in p.color_matrix)


def test_list_profiles_contains_generics():
    assert {"generic_color", "generic_bw", "portra_400", "hp5_400"} <= set(list_profiles())


def test_kodak_gold_profile_is_warmer_than_generic():
    gold, gen = load_profile("kodak_gold_100"), load_profile("generic_color")
    assert gold.type == "color_negative"
    assert gold.color_matrix[0][0] > gen.color_matrix[0][0] > gold.color_matrix[2][2]
    lum = 0.2126 * gold.color_matrix[0][0] + 0.7152 * gold.color_matrix[1][1] + 0.0722 * gold.color_matrix[2][2]
    assert abs(lum - 1.0) < 0.02  # cambia il colore, non l'esposizione


def test_unknown_profile_raises_clear_error():
    with pytest.raises(ValueError, match="Profilo sconosciuto"):
        load_profile("nope")


def test_load_profile_from_path(tmp_path):
    data = json.loads(json.dumps({
        "id": "x", "name": "X", "type": "bw_negative",
        "mask_rgb": [0.8, 0.8, 0.8], "gamma_rgb": [0.6, 0.6, 0.6],
        "print_contrast": 1.0,
        "color_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    }))
    f = tmp_path / "x.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    assert load_profile(str(f)).type == "bw_negative"


def test_bad_matrix_shape_rejected(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text(json.dumps({
        "id": "bad", "name": "Bad", "type": "color_negative",
        "mask_rgb": [0.8, 0.5, 0.3], "gamma_rgb": [0.6, 0.6, 0.6],
        "print_contrast": 1.0, "color_matrix": [[1, 0, 0], [0, 1, 0]],
    }), encoding="utf-8")
    with pytest.raises(ValueError):
        load_profile(str(f))


def test_bad_type_rejected(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text(json.dumps({
        "id": "bad", "name": "Bad", "type": "polaroid",
        "mask_rgb": [0.8, 0.5, 0.3], "gamma_rgb": [0.6, 0.6, 0.6],
        "print_contrast": 1.0, "color_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    }), encoding="utf-8")
    with pytest.raises(ValueError):
        load_profile(str(f))
