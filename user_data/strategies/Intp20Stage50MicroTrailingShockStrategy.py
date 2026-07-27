try:
    from user_data.strategies.Intp20Stage42TrailingShockStrategy import (
        Intp20Stage42TrailingShockStrategy,
    )
except ModuleNotFoundError:
    from Intp20Stage42TrailingShockStrategy import Intp20Stage42TrailingShockStrategy


class Intp20Stage50MicroTrailingShockStrategy(Intp20Stage42TrailingShockStrategy):
    """Stage42 entries with an earlier native trailing-profit trigger."""

    trailing_stop_positive = 0.006
    trailing_stop_positive_offset = 0.012
