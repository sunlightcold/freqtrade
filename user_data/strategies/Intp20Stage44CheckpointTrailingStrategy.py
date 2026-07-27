from __future__ import annotations

from datetime import datetime

from Intp20Stage42TrailingShockStrategy import Intp20Stage42TrailingShockStrategy


class Intp20Stage44CheckpointTrailingStrategy(Intp20Stage42TrailingShockStrategy):
    """Stage42 with a one-time no-progress loss check after 30 minutes."""

    checkpoint_minutes = 30
    checkpoint_floor = -0.020
    activation_underlying = 0.008

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | None:
        age_minutes = (current_time - trade.open_date_utc).total_seconds() / 60.0
        if self.checkpoint_minutes <= age_minutes < self.checkpoint_minutes + 1:
            if trade.is_short:
                peak_rate = trade.min_rate or trade.open_rate
                peak_return = trade.open_rate / peak_rate - 1.0
                current_underlying = trade.open_rate / current_rate - 1.0
            else:
                peak_rate = trade.max_rate or trade.open_rate
                peak_return = peak_rate / trade.open_rate - 1.0
                current_underlying = current_rate / trade.open_rate - 1.0
            if (
                peak_return < self.activation_underlying
                and current_underlying <= self.checkpoint_floor
            ):
                return "stage44_no_progress_checkpoint"

        return super().custom_exit(
            pair,
            trade,
            current_time,
            current_rate,
            current_profit,
            **kwargs,
        )
