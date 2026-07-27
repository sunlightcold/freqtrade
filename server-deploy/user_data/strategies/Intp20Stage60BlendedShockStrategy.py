try:
    from user_data.strategies.Intp20Stage31RelativeShockStrategy import (
        Intp20Stage31RelativeShockStrategy,
    )
except ModuleNotFoundError:
    from Intp20Stage31RelativeShockStrategy import Intp20Stage31RelativeShockStrategy


class Intp20Stage60BlendedShockStrategy(Intp20Stage31RelativeShockStrategy):
    """Volume-backed relative-shock reversal validated on the 41-pair pool."""

    stoploss = -0.80
    long_hold_minutes = 90
    short_hold_minutes = 120
    fixed_leverage = 4.0

    trailing_stop = True
    trailing_stop_positive = 0.006
    trailing_stop_positive_offset = 0.024
    trailing_only_offset_is_reached = True
