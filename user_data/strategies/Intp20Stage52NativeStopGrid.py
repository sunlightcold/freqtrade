try:
    from user_data.strategies.Intp20Stage51NativeTrailingGrid import (
        Intp20Stage51Trail024x006,
    )
except ModuleNotFoundError:
    from Intp20Stage51NativeTrailingGrid import Intp20Stage51Trail024x006


class Intp20Stage52Stop040(Intp20Stage51Trail024x006):
    stoploss = -0.40


class Intp20Stage52Stop050(Intp20Stage51Trail024x006):
    stoploss = -0.50


class Intp20Stage52Stop060(Intp20Stage51Trail024x006):
    stoploss = -0.60


class Intp20Stage52Stop070(Intp20Stage51Trail024x006):
    stoploss = -0.70
