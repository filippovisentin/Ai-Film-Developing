import pytest

from devguide.calculator import bw_dev_time, c41_dev_time
from devguide.recipes import load_recipe

HP5 = load_recipe("bw_hp5_plus")
CS41 = load_recipe("c41_cinestill_cs41_liquid")


# --- bianco e nero (Ilford HP5 Plus) ---------------------------------------

def test_bw_reference_temperature_is_the_sheet_value():
    t = bw_dev_time(HP5, "ilfosol3", "1+9", 400, 20.0)
    assert t.seconds == 390 and t.derived is False


def test_bw_warmer_follows_ilford_example():
    # scheda: 6 min a 20 °C -> 4½ min a 23 °C (fattore 0,75)
    t = bw_dev_time(HP5, "ilfosol3", "1+9", 400, 23.0)
    assert abs(t.seconds - 6.5 * 60 * 0.75) <= 5 and t.derived is True


def test_bw_colder_inside_range():
    t = bw_dev_time(HP5, "ilfosol3", "1+9", 400, 18.0)
    assert abs(t.seconds - 6.5 * 60 * 0.906 ** -2) <= 2


def test_bw_range_is_what_the_sheet_examples_cover():
    # la scheda dà esempi a 16 e 23 °C: dentro si calcola, fuori si rifiuta
    assert abs(bw_dev_time(HP5, "ilfosol3", "1+9", 400, 16.0).seconds - 6.5 * 60 * 1.5) <= 6
    with pytest.raises(ValueError, match="16-23"):
        bw_dev_time(HP5, "ilfosol3", "1+9", 400, 24.0)


def test_bw_ei_not_in_sheet_is_refused():
    with pytest.raises(ValueError, match="non indicat"):
        bw_dev_time(HP5, "ilfosol3", "1+9", 1600, 20.0)


def test_bw_unknown_developer_lists_options():
    with pytest.raises(ValueError, match="ilfosol3"):
        bw_dev_time(HP5, "rodinal", "1+50", 400, 20.0)


def test_bw_agitation_is_ilford_intermittent():
    a = bw_dev_time(HP5, "ddx", "1+4", 400, 20.0).agitation
    assert (a.initial_s, a.every_s, a.inversions) == (10, 60, 4)


# --- colore C-41 (CineStill Cs41) -------------------------------------------

def test_c41_standard_time():
    t = c41_dev_time(CS41, 39.0)
    assert t.seconds == 210 and t.derived is False and t.warnings == []


def test_c41_reuse_matches_cinestill_examples():
    assert c41_dev_time(CS41, 39.0, rolls_done=4).seconds == 227   # 3,5 x 1,08 = 3,78 min
    assert c41_dev_time(CS41, 39.0, rolls_done=8).seconds == 244   # 3,5 x 1,16 = 4,06 min


def test_c41_reuse_pint_is_four_percent():
    assert c41_dev_time(CS41, 39.0, rolls_done=4, volume="pint").seconds == 244


def test_c41_capacity_warning():
    t = c41_dev_time(CS41, 39.0, rolls_done=8)
    assert any("capacità" in w for w in t.warnings)


def test_c41_between_columns_is_interpolated_and_marked():
    t = c41_dev_time(CS41, 37.0)
    assert t.derived is True and 210 < t.seconds < 345
    assert t.seconds == round(60 * (5.75 * 3.5) ** 0.5)


def test_c41_outside_table_is_refused():
    with pytest.raises(ValueError, match="22"):
        c41_dev_time(CS41, 20.0)


def test_c41_empty_cell_is_refused():
    with pytest.raises(ValueError, match="push"):
        c41_dev_time(CS41, 27.0, push=3)


def test_c41_push_with_reuse_is_refused():
    with pytest.raises(ValueError, match="riuso"):
        c41_dev_time(CS41, 39.0, push=1, rolls_done=2)


def test_c41_negative_rolls_is_refused():
    with pytest.raises(ValueError, match="rullini"):
        c41_dev_time(CS41, 39.0, rolls_done=-10)


def test_c41_no_interpolation_across_agitation_bands():
    with pytest.raises(ValueError, match="agitazione"):
        c41_dev_time(CS41, 28.0)            # 27 °C e 29,5 °C hanno agitazioni diverse
    with pytest.raises(ValueError, match="agitazione"):
        c41_dev_time(CS41, 34.0)            # 32 °C e 35 °C idem
    assert c41_dev_time(CS41, 25.5).derived is True   # 24 e 27 °C: stessa agitazione


def test_c41_reuse_explains_top_up():
    t = c41_dev_time(CS41, 39.0, rolls_done=3)
    assert any("rabbocc" in w for w in t.warnings)


def test_c41_agitation_by_temperature_band():
    a = c41_dev_time(CS41, 24.0).agitation
    assert (a.initial_s, a.every_s) == (60, 120)
    assert c41_dev_time(CS41, 39.0).agitation.every_s == 30


def test_c41_pull_and_push_rows():
    assert c41_dev_time(CS41, 39.0, push=-1).seconds == 165     # 2,75 min
    assert c41_dev_time(CS41, 35.0, push=2).seconds == 600      # 10 min
