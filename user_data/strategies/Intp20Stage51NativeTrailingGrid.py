try:
    from user_data.strategies.Intp20Stage42TrailingShockStrategy import (
        Intp20Stage42TrailingShockStrategy,
    )
except ModuleNotFoundError:
    from Intp20Stage42TrailingShockStrategy import Intp20Stage42TrailingShockStrategy


class Intp20Stage51Trail016x004(Intp20Stage42TrailingShockStrategy):
    trailing_stop_positive = 0.004
    trailing_stop_positive_offset = 0.016


class Intp20Stage51Trail016x006(Intp20Stage42TrailingShockStrategy):
    trailing_stop_positive = 0.006
    trailing_stop_positive_offset = 0.016


class Intp20Stage51Trail020x006(Intp20Stage42TrailingShockStrategy):
    trailing_stop_positive = 0.006
    trailing_stop_positive_offset = 0.020


class Intp20Stage51Trail020x008(Intp20Stage42TrailingShockStrategy):
    trailing_stop_positive = 0.008
    trailing_stop_positive_offset = 0.020


class Intp20Stage51Trail024x006(Intp20Stage42TrailingShockStrategy):
    trailing_stop_positive = 0.006
    trailing_stop_positive_offset = 0.024


class Intp20Stage51Trail024x008(Intp20Stage42TrailingShockStrategy):
    trailing_stop_positive = 0.008
    trailing_stop_positive_offset = 0.024


class Intp20Stage51Trail028x006(Intp20Stage42TrailingShockStrategy):
    trailing_stop_positive = 0.006
    trailing_stop_positive_offset = 0.028


class Intp20Stage51Trail028x008(Intp20Stage42TrailingShockStrategy):
    trailing_stop_positive = 0.008
    trailing_stop_positive_offset = 0.028
