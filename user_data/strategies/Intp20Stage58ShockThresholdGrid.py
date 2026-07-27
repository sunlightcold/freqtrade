try:
    from user_data.strategies.Intp20Stage51NativeTrailingGrid import (
        Intp20Stage51Trail024x006,
    )
except ModuleNotFoundError:
    from Intp20Stage51NativeTrailingGrid import Intp20Stage51Trail024x006


class Intp20Stage58Shock020x050(Intp20Stage51Trail024x006):
    long_shock = -0.020
    short_shock = 0.050


class Intp20Stage58Shock020x060(Intp20Stage51Trail024x006):
    long_shock = -0.020
    short_shock = 0.060


class Intp20Stage58Shock025x050(Intp20Stage51Trail024x006):
    long_shock = -0.025
    short_shock = 0.050


class Intp20Stage58Shock030x070(Intp20Stage51Trail024x006):
    long_shock = -0.030
    short_shock = 0.070
