try:
    from user_data.strategies.Intp20Stage31RelativeShockStrategy import (
        Intp20Stage31RelativeShockStrategy,
    )
except ModuleNotFoundError:
    from Intp20Stage31RelativeShockStrategy import Intp20Stage31RelativeShockStrategy


class Intp20Stage42TrailingShockStrategy(Intp20Stage31RelativeShockStrategy):
    """Relative-shock reversal with a leveraged trailing-profit exit."""

    stoploss = -0.80
    long_hold_minutes = 90
    short_hold_minutes = 120
    fixed_leverage = 4.0

    trailing_stop = True
    trailing_stop_positive = 0.008
    trailing_stop_positive_offset = 0.032
    trailing_only_offset_is_reached = True
