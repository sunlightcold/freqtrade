try:
    from user_data.strategies.Intp20Stage51NativeTrailingGrid import (
        Intp20Stage51Trail024x006,
    )
except ModuleNotFoundError:
    from Intp20Stage51NativeTrailingGrid import Intp20Stage51Trail024x006


class Intp20Stage53Horizon060x090(Intp20Stage51Trail024x006):
    long_hold_minutes = 60
    short_hold_minutes = 90


class Intp20Stage53Horizon090x120(Intp20Stage51Trail024x006):
    long_hold_minutes = 90
    short_hold_minutes = 120


class Intp20Stage53Horizon120x180(Intp20Stage51Trail024x006):
    long_hold_minutes = 120
    short_hold_minutes = 180


class Intp20Stage53Horizon180x240(Intp20Stage51Trail024x006):
    long_hold_minutes = 180
    short_hold_minutes = 240
