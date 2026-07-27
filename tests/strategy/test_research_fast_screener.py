import json
from math import isclose
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from user_data.scripts.research_fast_screener import simulate
from user_data.scripts.research_stage35_event_walkforward import ExitProfile, future_outcomes
from user_data.scripts.research_stage36_path_exit import (
    ExitProfile as PathExitProfile,
)
from user_data.scripts.research_stage36_path_exit import (
    resolve_paths,
)
from user_data.scripts.research_stage41_trailing_exit import robust_score
from user_data.scripts.research_stage45_recovery_exit import (
    RecoveryProfile,
    resolve_recovery_checkpoint,
)
from user_data.scripts.research_stage46_loss_cooldown import (
    CooldownProfile,
    execute_with_cooldown,
)
from user_data.scripts.research_stage48_two_stage_trailing import (
    ProtectionProfile,
    resolve_two_stage,
)
from user_data.strategies.Intp20Stage49TwoStageTrailingStrategy import (
    Intp20Stage49TwoStageTrailingStrategy,
)
from user_data.strategies.Intp20Stage50MicroTrailingShockStrategy import (
    Intp20Stage50MicroTrailingShockStrategy,
)
from user_data.strategies.Intp20Stage51NativeTrailingGrid import (
    Intp20Stage51Trail016x004,
    Intp20Stage51Trail028x008,
)
from user_data.strategies.Intp20Stage52NativeStopGrid import (
    Intp20Stage52Stop040,
    Intp20Stage52Stop070,
)
from user_data.strategies.Intp20Stage53NativeHorizonGrid import (
    Intp20Stage53Horizon060x090,
    Intp20Stage53Horizon180x240,
)
from user_data.strategies.Intp20Stage54NativeLeverageGrid import (
    Intp20Stage54Leverage5x,
    Intp20Stage54Leverage6x,
)
from user_data.strategies.Intp20Stage55NativeConfirmationGrid import (
    Intp20Stage55CloseReversal,
    Intp20Stage55MidpointReclaim,
)
from user_data.strategies.Intp20Stage57AtrTieredRiskStrategy import (
    Intp20Stage57Tier2x5,
    Intp20Stage57Tier3x6,
)
from user_data.strategies.Intp20Stage58ShockThresholdGrid import (
    Intp20Stage58Shock020x050,
    Intp20Stage58Shock030x070,
)
from user_data.strategies.Intp20Stage60BlendedShockStrategy import (
    Intp20Stage60BlendedShockStrategy,
)


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


def test_stage60_keeps_the_validated_signal_and_risk_parameters():
    strategy = Intp20Stage60BlendedShockStrategy({})

    assert strategy.can_short is True
    assert strategy.timeframe == "1m"
    assert strategy.relative_lookback == 30
    assert strategy.long_shock == -0.025
    assert strategy.short_shock == 0.060
    assert strategy.volume_ratio_floor == 2.0
    assert strategy.fixed_leverage == 4.0
    assert strategy.long_hold_minutes == 90
    assert strategy.short_hold_minutes == 120
    assert strategy.stoploss == -0.80
    assert strategy.trailing_stop is True
    assert strategy.trailing_stop_positive == 0.006
    assert strategy.trailing_stop_positive_offset == 0.024
    assert strategy.trailing_only_offset_is_reached is True


def test_stage60_deploy_config_matches_the_validated_portfolio():
    config_paths = [
        Path("user_data/config_binance_stage60_blended_shock_41pair_1000u_dryrun.json"),
        Path(
            "server-deploy/user_data/config_binance_stage60_blended_shock_41pair_1000u_dryrun.json"
        ),
    ]
    configs = [json.loads(path.read_text(encoding="utf-8")) for path in config_paths]

    assert configs[0] == configs[1]
    config = configs[0]
    pairs = config["exchange"]["pair_whitelist"]
    assert config["strategy"] == "Intp20Stage60BlendedShockStrategy"
    assert config["dry_run"] is True
    assert config["dry_run_wallet"] == 1000
    assert config["stake_amount"] == 100
    assert config["max_open_trades"] == 9
    assert config["fee"] == 0.0007
    assert config["trading_mode"] == "futures"
    assert config["margin_mode"] == "isolated"
    assert len(pairs) == len(set(pairs)) == 41
    assert "MERL/USDT:USDT" in pairs
    assert "PUMP/USDT:USDT" in pairs


def test_stage60_deployment_reuses_the_single_server_deploy_stack():
    script = Path("server-deploy/apply-stage60-single.sh").read_text(encoding="utf-8")

    assert "/data/app/freqtrade" in script
    assert 'PROJECT="server-deploy"' in script
    assert 'CONFIG="config_binance_stage60_blended_shock_41pair_1000u_dryrun.json"' in script
    assert 'STRATEGY="Intp20Stage60BlendedShockStrategy"' in script
    assert "up -d --remove-orphans --no-deps freqtrade" in script
    assert 'set_env FREQUI_BIND "127.0.0.1"' in script
    assert 'set_env FREQUI_PORT "8081"' in script
    assert "up -d --no-deps frequi" in script
    assert "server-deploy-stage" not in script
    assert 'RESET_DB="${RESET_DB:-0}"' in script


def test_stage35_outcomes_enter_next_open_and_stop_wins_intrabar_tie():
    index = pd.date_range("2024-01-01", periods=5, freq="5min", tz="UTC")
    dataframe = pd.DataFrame(
        {
            "open": [100.0, 110.0, 100.0, 100.0, 100.0],
            "high": [100.0, 112.0, 100.0, 100.0, 100.0],
            "low": [100.0, 108.0, 100.0, 100.0, 100.0],
            "close": [100.0, 110.0, 100.0, 100.0, 100.0],
        },
        index=index,
    )

    outcomes = future_outcomes(
        dataframe,
        signal_indices=pd.Series([0]).to_numpy(),
        side=1,
        profile=ExitProfile(target=0.01, stop=0.01, hold=2),
        cost=0.0,
        leverage=1.0,
    )

    assert outcomes["entry_date"].tolist() == [index[1]]
    assert outcomes["exit_date"].tolist() == [index[1]]
    assert outcomes["profit"].tolist() == [-0.01]


def test_stage36_path_exit_uses_stop_for_tie_and_checkpoint_for_no_progress():
    favorable = pd.DataFrame(
        [
            [0.02, 0.02, 0.02, 0.02],
            [0.001, 0.002, 0.003, 0.004],
        ]
    ).to_numpy()
    adverse = pd.DataFrame(
        [
            [-0.02, -0.02, -0.02, -0.02],
            [-0.001, -0.002, -0.003, -0.004],
        ]
    ).to_numpy()
    close_return = pd.DataFrame(
        [
            [0.0, 0.0, 0.0, 0.0],
            [-0.0005, -0.002, -0.002, -0.002],
        ]
    ).to_numpy()
    profile = PathExitProfile(
        target=0.01,
        stop=0.01,
        checkpoint=2,
        checkpoint_floor=-0.001,
        hold=4,
    )

    offsets, profit, reason = resolve_paths(favorable, adverse, close_return, profile)

    assert offsets.tolist() == [0, 1]
    assert profit.tolist() == [-0.01, -0.002]
    assert reason.tolist() == ["stop", "checkpoint"]


def test_stage45_checkpoint_exits_only_a_losing_trade_without_recovery():
    event = type(
        "Event",
        (),
        {
            "side": "long",
            "entry_dates": pd.date_range("2024-01-01", periods=3, freq="1h"),
            "favorable": pd.DataFrame(
                [
                    [0.001] * 20,
                    [0.001] * 20,
                    [0.009] * 20,
                ]
            ).to_numpy(),
            "adverse": pd.DataFrame(
                [
                    [-0.001] * 20,
                    [-0.001] * 20,
                    [0.008] * 20,
                ]
            ).to_numpy(),
            "close_return": pd.DataFrame(
                [
                    [-0.005] * 10 + [-0.011, -0.012, -0.013, -0.014, -0.015] + [0.0] * 5,
                    [-0.020] * 10 + [-0.018, -0.016, -0.014, -0.012, -0.010] + [0.0] * 5,
                    [0.001] * 20,
                ]
            ).to_numpy(),
        },
    )()
    profile = RecoveryProfile(
        checkpoint=15,
        floor=-0.005,
        slope_window=5,
        slope_ceiling=0.0,
    )

    offsets, profit, reason = resolve_recovery_checkpoint(event, hold=20, profile=profile)

    assert offsets.tolist() == [14, 19, 19]
    assert profit.tolist() == [-0.015, 0.0, 0.001]
    assert reason.tolist() == ["recovery_checkpoint", "horizon", "horizon"]


def test_stage46_cooldown_uses_only_losses_closed_before_the_entry():
    base = pd.Timestamp("2024-01-01", tz="UTC")
    trades = pd.DataFrame(
        [
            ("A", "long", base, base + pd.Timedelta(minutes=10), -0.10),
            ("B", "long", base + pd.Timedelta(minutes=10), base + pd.Timedelta(minutes=11), 0.01),
            ("C", "long", base + pd.Timedelta(minutes=11), base + pd.Timedelta(minutes=12), 0.01),
            ("D", "short", base + pd.Timedelta(minutes=41), base + pd.Timedelta(minutes=42), 0.01),
        ],
        columns=["pair", "side", "entry_date", "exit_date", "profit"],
    )
    profile = CooldownProfile(loss_trigger=-0.05, cooldown_minutes=30, scope="global")

    selected = execute_with_cooldown(trades, profile, max_slots=2)

    assert selected["pair"].tolist() == ["A", "B", "D"]


def test_stage41_robust_score_prefers_the_better_worst_window():
    common = {"wr": 0.80, "tpd": 4.0, "pf": 1.3, "dd": 0.2}
    volatile = ({**common, "return": 2.0}, {**common, "return": 0.4})
    stable = ({**common, "return": 1.0}, {**common, "return": 0.8})

    assert robust_score(*stable) > robust_score(*volatile)


def test_stage48_protection_activates_on_the_bar_after_the_peak():
    event = type(
        "Event",
        (),
        {
            "side": "long",
            "entry_dates": pd.date_range("2024-01-01", periods=1),
            "favorable": pd.DataFrame([[0.001, 0.005, 0.006, 0.006]]).to_numpy(),
            "adverse": pd.DataFrame([[-0.001, -0.001, -0.001, -0.001]]).to_numpy(),
            "close_return": pd.DataFrame([[0.0, 0.004, 0.002, -0.001]]).to_numpy(),
        },
    )()

    offsets, profit, reason = resolve_two_stage(
        event,
        hold=4,
        profile=ProtectionProfile(activation=0.004, floor=0.0),
    )

    assert offsets.tolist() == [2]
    assert profit.tolist() == [0.0]
    assert reason.tolist() == ["protection"]


def test_stage49_native_protector_arms_before_it_moves_the_stop():
    strategy = Intp20Stage49TwoStageTrailingStrategy({})
    opened = pd.Timestamp("2024-01-01", tz="UTC").to_pydatetime()
    trade = SimpleNamespace(
        open_date_utc=opened,
        is_short=False,
        open_rate=100.0,
        max_rate=100.6,
        min_rate=100.0,
        leverage=4.0,
    )

    first = strategy.custom_stoploss(
        "TEST/USDT:USDT",
        trade,
        opened + pd.Timedelta(minutes=1),
        100.6,
        0.024,
        False,
    )
    second = strategy.custom_stoploss(
        "TEST/USDT:USDT",
        trade,
        opened + pd.Timedelta(minutes=2),
        100.4,
        0.016,
        False,
    )

    assert first is None
    assert second is not None and second > 0
    assert (
        strategy.custom_exit(
            "TEST/USDT:USDT",
            trade,
            opened + pd.Timedelta(minutes=2),
            100.2,
            0.008,
        )
        == "stage49_protection_gap"
    )


def test_stage50_uses_a_native_micro_trailing_exit():
    strategy = Intp20Stage50MicroTrailingShockStrategy({})

    assert strategy.trailing_stop is True
    assert strategy.trailing_only_offset_is_reached is True
    assert strategy.trailing_stop_positive == 0.006
    assert strategy.trailing_stop_positive_offset == 0.012


def test_stage51_grid_keeps_entry_logic_fixed_while_bounding_trailing_values():
    tight = Intp20Stage51Trail016x004({})
    wide = Intp20Stage51Trail028x008({})

    assert tight.long_shock == wide.long_shock == -0.025
    assert tight.short_shock == wide.short_shock == 0.060
    assert tight.fixed_leverage == wide.fixed_leverage == 4.0
    assert (tight.trailing_stop_positive_offset, tight.trailing_stop_positive) == (
        0.016,
        0.004,
    )
    assert (wide.trailing_stop_positive_offset, wide.trailing_stop_positive) == (
        0.028,
        0.008,
    )


def test_stage52_grid_changes_only_the_hard_stop():
    narrow = Intp20Stage52Stop040({})
    wide = Intp20Stage52Stop070({})

    assert narrow.stoploss == -0.40
    assert wide.stoploss == -0.70
    assert narrow.trailing_stop_positive == wide.trailing_stop_positive == 0.006
    assert narrow.trailing_stop_positive_offset == wide.trailing_stop_positive_offset == 0.024


def test_stage53_grid_changes_only_the_fixed_horizon():
    short = Intp20Stage53Horizon060x090({})
    long = Intp20Stage53Horizon180x240({})

    assert (short.long_hold_minutes, short.short_hold_minutes) == (60, 90)
    assert (long.long_hold_minutes, long.short_hold_minutes) == (180, 240)
    assert short.stoploss == long.stoploss == -0.80
    assert short.trailing_stop_positive == long.trailing_stop_positive == 0.006
    assert short.trailing_stop_positive_offset == long.trailing_stop_positive_offset == 0.024


def test_stage54_grid_scales_native_trailing_with_leverage():
    leverage5 = Intp20Stage54Leverage5x({})
    leverage6 = Intp20Stage54Leverage6x({})

    assert leverage5.fixed_leverage == 5.0
    assert leverage6.fixed_leverage == 6.0
    assert leverage5.stoploss == leverage6.stoploss == -0.90
    assert isclose(leverage5.trailing_stop_positive / 5, 0.0015)
    assert isclose(leverage6.trailing_stop_positive / 6, 0.0015)
    assert isclose(leverage5.trailing_stop_positive_offset / 5, 0.006)
    assert isclose(leverage6.trailing_stop_positive_offset / 6, 0.006)


def test_stage55_grid_keeps_risk_settings_while_changing_confirmation():
    close = Intp20Stage55CloseReversal({})
    midpoint = Intp20Stage55MidpointReclaim({})

    assert close.confirmation_mode == "close"
    assert midpoint.confirmation_mode == "midpoint"
    assert close.fixed_leverage == midpoint.fixed_leverage == 4.0
    assert close.stoploss == midpoint.stoploss == -0.80
    assert close.trailing_stop_positive == midpoint.trailing_stop_positive == 0.006


def test_stage57_grid_changes_only_outer_atr_risk_tiers():
    cautious = Intp20Stage57Tier2x5({})
    aggressive = Intp20Stage57Tier3x6({})

    assert cautious.low_atr_threshold == aggressive.low_atr_threshold == 0.004
    assert cautious.high_atr_threshold == aggressive.high_atr_threshold == 0.0075
    assert cautious.middle_atr_leverage == aggressive.middle_atr_leverage == 4.0
    assert (cautious.low_atr_leverage, cautious.high_atr_leverage) == (2.0, 5.0)
    assert (aggressive.low_atr_leverage, aggressive.high_atr_leverage) == (3.0, 6.0)


def test_stage58_grid_changes_only_shock_thresholds():
    broad = Intp20Stage58Shock020x050({})
    selective = Intp20Stage58Shock030x070({})

    assert (broad.long_shock, broad.short_shock) == (-0.020, 0.050)
    assert (selective.long_shock, selective.short_shock) == (-0.030, 0.070)
    assert broad.volume_ratio_floor == selective.volume_ratio_floor == 2.0
    assert broad.fixed_leverage == selective.fixed_leverage == 4.0
    assert broad.trailing_stop_positive == selective.trailing_stop_positive == 0.006
