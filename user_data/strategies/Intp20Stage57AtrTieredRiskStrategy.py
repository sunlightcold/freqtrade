from __future__ import annotations

from datetime import datetime

from pandas import DataFrame


try:
    from user_data.strategies.Intp20Stage51NativeTrailingGrid import (
        Intp20Stage51Trail024x006,
    )
except ModuleNotFoundError:
    from Intp20Stage51NativeTrailingGrid import Intp20Stage51Trail024x006


class Intp20Stage57AtrTieredBase(Intp20Stage51Trail024x006):
    atr_period = 24
    low_atr_threshold = 0.004
    high_atr_threshold = 0.0075
    low_atr_leverage = 3.0
    middle_atr_leverage = 4.0
    high_atr_leverage = 5.0

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
        dataframe["stage57_atr_pct"] = (
            true_range.ewm(alpha=1 / self.atr_period, adjust=False).mean()
            / dataframe["close"]
        )
        return dataframe

    def _atr_at_entry(self, pair: str, current_time: datetime) -> float | None:
        if not self.dp:
            return None
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        eligible = dataframe.loc[
            dataframe["date"] <= current_time, "stage57_atr_pct"
        ].dropna()
        return float(eligible.iloc[-1]) if not eligible.empty else None

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
            target = self.middle_atr_leverage
        elif atr_pct < self.low_atr_threshold:
            target = self.low_atr_leverage
        elif atr_pct > self.high_atr_threshold:
            target = self.high_atr_leverage
        else:
            target = self.middle_atr_leverage
        return max(1.0, min(target, max_leverage))


class Intp20Stage57Tier3x5(Intp20Stage57AtrTieredBase):
    low_atr_leverage = 3.0
    high_atr_leverage = 5.0


class Intp20Stage57Tier2x5(Intp20Stage57AtrTieredBase):
    low_atr_leverage = 2.0
    high_atr_leverage = 5.0


class Intp20Stage57Tier3x6(Intp20Stage57AtrTieredBase):
    low_atr_leverage = 3.0
    high_atr_leverage = 6.0
