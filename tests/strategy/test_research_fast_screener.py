from pathlib import Path

import pandas as pd

from user_data.scripts.research_fast_screener import simulate


def test_vectorized_bracket_simulator_keeps_stop_tie_and_pair_lock():
    index = pd.date_range("2024-01-01", periods=8, freq="15min", tz="UTC")
    dataframe = pd.DataFrame(
        {
            "close": [100.0] * 8,
            "high": [100.0, 100.0, 102.0, 100.0, 100.0, 100.2, 100.2, 100.0],
            "low": [100.0, 100.0, 98.0, 100.0, 100.0, 99.8, 99.8, 100.0],
        },
        index=index,
    )
    signals = pd.Series([True, True, False, True, False, False, False, False], index=index)

    trades = simulate(
        dataframe,
        signals,
        side="long",
        hold=2,
        tp=0.01,
        sl=0.01,
        fee=0.0,
        leverage=1.0,
    )

    assert trades["date"].tolist() == [index[1], index[4]]
    assert trades["exit_reason"].tolist() == ["stop", "timeout"]
    assert trades["profit"].tolist() == [-0.01, 0.0]


def test_stage31_deployment_script_is_an_explicit_blocker():
    script = Path("server-deploy/apply-stage31-single.sh").read_text(encoding="utf-8")

    assert "DEPLOYMENT BLOCKED" in script
    assert "exit 2" in script
    assert "docker compose" not in script
