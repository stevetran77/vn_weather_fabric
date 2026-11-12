import re

import daily_aggregate
import schemas


def _aliases(sql: str) -> list[str]:
    select = sql.split("FROM")[0]
    names = []
    for line in select.splitlines()[1:]:
        line = line.strip().rstrip(",")
        names.append(re.split(r"\s+AS\s+", line, flags=re.I)[-1].strip("`") if " AS " in line
                     else line)
    return names


def test_build_daily_sql_columns_match_daily_ddl():
    sql = daily_aggregate.build_daily_sql("hourly", 15)
    assert _aliases(sql) == schemas.column_names(schemas.DAILY_DDL)


def test_build_daily_sql_uses_threshold_and_view():
    sql = daily_aggregate.build_daily_sql("hourly_view", 37.5)
    assert "AVG(pm2_5) > 37.5 AS is_above_pm2_5_threshold" in sql
    assert "FROM hourly_view" in sql


def test_build_daily_sql_groups_by_local_date_and_skips_forecast():
    sql = daily_aggregate.build_daily_sql("hourly", 15)
    assert "GROUP BY city_id, CAST(ts_local AS DATE)" in sql
    assert "WHERE source <> 'forecast'" in sql
