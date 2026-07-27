try:
    from user_data.strategies.Intp20Stage53NativeHorizonGrid import (
        Intp20Stage53Horizon090x120,
    )
except ModuleNotFoundError:
    from Intp20Stage53NativeHorizonGrid import Intp20Stage53Horizon090x120


class Intp20Stage54Leverage5x(Intp20Stage53Horizon090x120):
    fixed_leverage = 5.0
    stoploss = -0.90
    trailing_stop_positive = 0.0075
    trailing_stop_positive_offset = 0.030


class Intp20Stage54Leverage6x(Intp20Stage53Horizon090x120):
    fixed_leverage = 6.0
    stoploss = -0.90
    trailing_stop_positive = 0.009
    trailing_stop_positive_offset = 0.036
