from contextlib import nullcontext

from district_context import cli


def test_run_all_builds_before_requiring_an_existing_database(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(cli, "database_path", lambda: tmp_path / "missing.duckdb")
    monkeypatch.setattr(
        cli,
        "build_database",
        lambda **_: {"table_counts": {"mart_achievement": 1}},
    )
    monkeypatch.setattr(cli, "connect", lambda: nullcontext(object()))
    monkeypatch.setattr(cli, "run_qa", lambda _: [])
    monkeypatch.setattr(cli, "has_failures", lambda _: False)
    monkeypatch.setattr(cli, "_choose_demo_district", lambda *_: "0000001")
    monkeypatch.setattr(
        cli,
        "_run_profile",
        lambda target_id, grade, output: called.append((target_id, grade, output)),
    )

    cli.main(["run-all", "--skip-hash"])

    assert called == [("0000001", 4, None)]
