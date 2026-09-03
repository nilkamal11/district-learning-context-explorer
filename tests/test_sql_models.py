import duckdb
import pandas as pd

from district_context.config import PROJECT_ROOT
from district_context.database import _render_sql, _sql_literal


def test_all_sql_models_compile_against_test_only_fixtures(tmp_path):
    achievement_path = tmp_path / "achievement.csv"
    context_path = tmp_path / "context.csv"
    crosswalk_path = tmp_path / "crosswalk.csv"

    pd.DataFrame(
        [
            {
                # Regression case for the quoted comma that broke the full-file load.
                "sedaadmin": "10003",
                "sedaadminname": "Test District, The",
                "subject": "mth",
                "grade": 4,
                "year": 2024,
                "fips": 17,
                "stateabb": "IL",
                "multi_comp_all": 0,
                "tot_asmt_all": 100,
                "flag_estasmt_all": 0,
                "cs_mn_all": 0.2,
                "cs_mn_se_all": 0.05,
                "cs_mn_se_adj_all": 0.07,
            }
        ]
    ).to_csv(achievement_path, index=False)
    pd.DataFrame(
        [
            {
                "sedaadmin": "10003",
                "year": 2024,
                "sedaadminname": "Test District, The",
                "gslo": "Kindergarten",
                "gshi": 12,
                "fips": 17,
                "stateabb": "IL",
                "urban": 0.70,
                "suburb": 0.20,
                "town": 0.05,
                "rural": 0.05,
                "pernam": 0.01,
                "perasn": 0.08,
                "perhsp": 0.20,
                "perblk": 0.15,
                "perwht": 0.50,
                "perell": 0,
                "perspeced": 0,
                "totenrl": 1000,
                "povertyall": 0.12,
                "sesall": 0.25,
                "urbanicity": "Suburb",
            }
        ]
    ).to_csv(context_path, index=False)
    pd.DataFrame(
        [
            {
                "geo": "sedaadmin",
                "id": "10002",
                "seda_id": "10003",
                "year": 2024,
                "name": "Test District, The",
                "stateabb": "IL",
                "fips": 17,
                "fips_op": 17,
                "last_virtual": None,
                "imputed": 0,
            }
        ]
    ).to_csv(crosswalk_path, index=False)

    replacements = {
        "achievement_path": _sql_literal(achievement_path),
        "context_path": _sql_literal(context_path),
        "crosswalk_path": _sql_literal(crosswalk_path),
        "context_year": "2024",
    }
    connection = duckdb.connect()
    for model in sorted((PROJECT_ROOT / "sql" / "models").glob("*.sql")):
        connection.execute(_render_sql(model, replacements))

    assert connection.execute("SELECT district_id FROM dim_district").fetchone()[0] == "0010003"
    assert connection.execute("SELECT district_name FROM stg_achievement").fetchone()[0] == (
        "Test District, The"
    )
    locale = connection.execute(
        "SELECT dominant_locale, share_argmax_locale FROM mart_context_snapshot"
    ).fetchone()
    assert locale == ("Suburb", "City")
    assert (
        connection.execute("SELECT sum(changed_stable_ids) FROM mart_crosswalk_audit").fetchone()[0]
        == 1
    )
