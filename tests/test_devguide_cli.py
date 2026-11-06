from devguide.__main__ import main


def test_list_recipes(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "bw_hp5_plus" in out and "c41_cinestill_cs41_liquid" in out


def test_plan_bw(capsys):
    rc = main(["plan", "bw", "--recipe", "bw_hp5_plus", "--developer", "ilfosol3",
               "--dilution", "1+9", "--ei", "400", "--temp", "20"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "06:30" in out and "Fissaggio" in out
    assert "ilfordphoto.com" in out                       # fonte sempre indicata
    assert "smalt" in out.lower() and "guanti" in out.lower()


def test_plan_c41_with_push_and_reuse(capsys):
    rc = main(["plan", "c41", "--recipe", "c41_cinestill_cs41_liquid", "--temp", "39",
               "--push", "1", "--rolls-done", "3"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "04:49" in out            # 4,55 min x 1,06
    assert "riuso" in out


def test_plan_not_covered_exits_2(capsys):
    rc = main(["plan", "bw", "--recipe", "bw_hp5_plus", "--developer", "ilfosol3",
               "--dilution", "1+9", "--ei", "1600", "--temp", "20"])
    assert rc == 2
    assert "non indicat" in capsys.readouterr().err


def test_plan_wrong_process_for_recipe(capsys):
    rc = main(["plan", "c41", "--recipe", "bw_hp5_plus", "--temp", "39"])
    assert rc == 2
    assert "C-41" in capsys.readouterr().err
