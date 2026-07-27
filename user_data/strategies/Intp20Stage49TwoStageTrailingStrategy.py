from __future__ import annotations

from datetime import datetime

from freqtrade.strategy import stoploss_from_open


try:
    from user_data.strategies.Intp20Stage42TrailingShockStrategy import (
        Intp20Stage42TrailingShockStrategy,
    )
except ModuleNotFoundError:
    from Intp20Stage42TrailingShockStrategy import Intp20Stage42TrailingShockStrategy


class Intp20Stage49TwoStageTrailingStrategy(Intp20Stage42TrailingShockStrategy):
    """Stage42 trailing exit with a delayed first-stage profit protector."""

    use_custom_stoploss = True
    protection_activation_underlying = 0.005
    protection_floor_underlying = 0.003

    @staticmethod
    def _protection_key(pair: str, trade) -> tuple:
        return pair, trade.open_date_utc, trade.is_short

    def _protection_is_active(self, pair: str, trade, current_time: datetime) -> bool:
        armed_at = getattr(self, "_stage49_armed_at", {}).get(
            self._protection_key(pair, trade)
        )
        return armed_at is not None and current_time > armed_at

    def custom_stoploss(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float | None:
        key = self._protection_key(pair, trade)
        if self._protection_is_active(pair, trade, current_time):
            account_floor = self.protection_floor_underlying * trade.leverage
            return stoploss_from_open(
                account_floor,
                current_profit,
                is_short=trade.is_short,
                leverage=trade.leverage,
            )

        if trade.is_short:
            best_rate = trade.min_rate or trade.open_rate
            peak_return = trade.open_rate / best_rate - 1.0
        else:
            best_rate = trade.max_rate or trade.open_rate
            peak_return = best_rate / trade.open_rate - 1.0
        if peak_return >= self.protection_activation_underlying:
            if not hasattr(self, "_stage49_armed_at"):
                self._stage49_armed_at = {}
            self._stage49_armed_at[key] = current_time
        return None

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | None:
        if self._protection_is_active(pair, trade, current_time):
            if trade.is_short:
                underlying_return = trade.open_rate / current_rate - 1.0
            else:
                underlying_return = current_rate / trade.open_rate - 1.0
            if underlying_return <= self.protection_floor_underlying:
                return "stage49_protection_gap"
        return super().custom_exit(
            pair,
            trade,
            current_time,
            current_rate,
            current_profit,
            **kwargs,
        )
