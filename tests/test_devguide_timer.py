import pytest

from devguide.recipes import Agitation, load_recipe
from devguide.timer import Session, Step, build_bw_session, build_c41_session

HP5 = load_recipe("bw_hp5_plus")
CS41 = load_recipe("c41_cinestill_cs41_liquid")
ILFORD = Agitation(initial_s=10, every_s=60, inversions=4, window_s=10)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _session(seconds=390, agitation=ILFORD):
    clock = Clock()
    s = Session([Step("Rivelatore", seconds, agitation), Step("Arresto", 10, None)], clock=clock)
    s.start()
    return s, clock


def test_agitation_windows_follow_ilford():
    s, clock = _session()
    pattern = {}
    for t in (0, 5, 9, 10, 30, 59, 60, 65, 70, 120, 125, 131):
        clock.t = 1000 + t
        pattern[t] = s.state().agitate_now
    assert [t for t, v in pattern.items() if v] == [0, 5, 9, 60, 65, 120, 125]


def test_next_agitation_countdown():
    s, clock = _session()
    clock.t = 1000 + 40
    assert s.state().next_agitation_in_s == 20


def test_pause_does_not_consume_bath_time():
    s, clock = _session()
    clock.t += 100
    s.pause()
    clock.t += 30
    assert s.state().paused is True and s.state().remaining_s == 290
    s.resume()
    clock.t += 10
    assert s.state().remaining_s == 280


def test_long_background_gap_is_recomputed_from_clock():
    s, clock = _session()
    clock.t += 600  # app sospesa 10 minuti
    st = s.state()
    assert st.remaining_s == 0 and st.overdue_s == 210 and st.agitate_now is False


def test_bath_waits_for_user_before_next_step():
    s, clock = _session(seconds=60)
    clock.t += 90
    assert s.state().step_index == 0 and s.state().overdue_s == 30
    s.next_step()
    st = s.state()
    assert st.step_index == 1 and st.step_name == "Arresto" and st.remaining_s == 10
    s.next_step()
    assert s.state().finished is True


def test_state_before_start_raises():
    with pytest.raises(RuntimeError):
        Session([Step("Rivelatore", 60, None)]).state()


def test_bw_sequence():
    steps, warnings = build_bw_session(HP5, "ilfosol3", "1+9", 400, 20.0)
    assert [s.name.split(" ")[0] for s in steps] == ["Rivelatore", "Arresto", "Fissaggio", "Lavaggio"]
    assert steps[0].seconds == 390 and steps[0].agitation == ILFORD
    assert warnings == []


def test_c41_sequence_with_derived_temperature_warning():
    steps, warnings = build_c41_session(CS41, 37.0, rolls_done=2)
    names = [s.name for s in steps]
    assert names[0].startswith("Pre-bagno") and names[1] == "Rivelatore"
    assert names[2].startswith("Sbianca") and names[3] == "Lavaggio" and names[4].startswith("Stabilizzatore")
    assert steps[2].agitation == steps[1].agitation   # scheda: blix "same as above"
    assert any("37" in w for w in warnings)            # tempo interpolato: segnalato


def test_c41_without_presoak():
    steps, _ = build_c41_session(CS41, 39.0, presoak=False)
    assert steps[0].name == "Rivelatore" and steps[0].seconds == 210
