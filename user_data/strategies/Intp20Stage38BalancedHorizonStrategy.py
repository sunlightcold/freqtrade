from Intp20Stage31RelativeShockStrategy import Intp20Stage31RelativeShockStrategy


class Intp20Stage38BalancedHorizonStrategy(Intp20Stage31RelativeShockStrategy):
    """Higher-risk balanced-horizon research variant of Stage31."""

    stoploss = -0.80
    long_hold_minutes = 45
    short_hold_minutes = 45
    fixed_leverage = 4.0
