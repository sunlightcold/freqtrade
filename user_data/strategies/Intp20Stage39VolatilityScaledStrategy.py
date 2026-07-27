from __future__ import annotations

from datetime import datetime

from Intp20Stage38BalancedHorizonStrategy import Intp20Stage38BalancedHorizonStrategy
from pandas import DataFrame


class Intp20Stage39VolatilityScaledStrategy(Intp20Stage38BalancedHorizonStrategy):
    """Stage38 signals with volatility-scaled leverage to reduce tail exposure."""

    atr_period = 14
    risk_budget = 0.020
    min_dynamic_leverage = 2.0
    max_dynamic_leverage = 4.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        previous_close = dataframe["close"].shift(1)
        true_range = DataFrame(
            {
                "high_low": dataframe["high"] - dataframe["low"],
                "high_close": (dataframe["high"] - previous_close).abs(),
                "low_close": (dataframe["low"] - previous_close).abs(),
            },
            index=dataframe.index,
        ).max(axis=1)
        dataframe["stage39_atr_pct"] = (
            true_range.rolling(self.atr_period, min_periods=self.atr_period).mean()
            / dataframe["close"]
        )
        return dataframe

    def _atr_at_entry(self, pair: str, current_time: datetime) -> float | None:
        if not self.dp:
            return None
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty or "stage39_atr_pct" not in dataframe:
            return None

        eligible = dataframe.loc[dataframe["date"] <= current_time, "stage39_atr_pct"].dropna()
        if eligible.empty:
            return None
        value = float(eligible.iloc[-1])
        return value if value > 0.0 else None

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        atr_pct = self._atr_at_entry(pair, current_time)
        if atr_pct is None:
            target = self.min_dynamic_leverage
        else:
            target = self.risk_budget / atr_pct
            target = max(self.min_dynamic_leverage, min(target, self.max_dynamic_leverage))
        return max(1.0, min(target, max_leverage))
