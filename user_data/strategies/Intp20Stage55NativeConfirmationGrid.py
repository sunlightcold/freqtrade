from pandas import DataFrame


try:
    from user_data.strategies.Intp20Stage51NativeTrailingGrid import (
        Intp20Stage51Trail024x006,
    )
except ModuleNotFoundError:
    from Intp20Stage51NativeTrailingGrid import Intp20Stage51Trail024x006


class Intp20Stage55ConfirmationBase(Intp20Stage51Trail024x006):
    confirmation_mode = "delay"

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        raw_long = dataframe["enter_long"].eq(1).shift(1, fill_value=False)
        raw_short = dataframe["enter_short"].eq(1).shift(1, fill_value=False)
        raw_tag = dataframe["enter_tag"].shift(1, fill_value="")

        if self.confirmation_mode == "close":
            long_confirmation = dataframe["close"] > dataframe["close"].shift(1)
            short_confirmation = dataframe["close"] < dataframe["close"].shift(1)
        elif self.confirmation_mode == "body":
            long_confirmation = dataframe["close"] > dataframe["open"]
            short_confirmation = dataframe["close"] < dataframe["open"]
        elif self.confirmation_mode == "midpoint":
            shock_midpoint = (
                dataframe["open"].shift(1) + dataframe["close"].shift(1)
            ) / 2
            long_confirmation = dataframe["close"] > shock_midpoint
            short_confirmation = dataframe["close"] < shock_midpoint
        else:
            long_confirmation = True
            short_confirmation = True

        confirmed_long = raw_long & long_confirmation
        confirmed_short = raw_short & short_confirmation
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""
        dataframe.loc[confirmed_long, "enter_long"] = 1
        dataframe.loc[confirmed_short, "enter_short"] = 1
        confirmed = confirmed_long | confirmed_short
        dataframe.loc[confirmed, "enter_tag"] = raw_tag.loc[confirmed]
        return dataframe


class Intp20Stage55Delay1(Intp20Stage55ConfirmationBase):
    confirmation_mode = "delay"


class Intp20Stage55CloseReversal(Intp20Stage55ConfirmationBase):
    confirmation_mode = "close"


class Intp20Stage55BodyReversal(Intp20Stage55ConfirmationBase):
    confirmation_mode = "body"


class Intp20Stage55MidpointReclaim(Intp20Stage55ConfirmationBase):
    confirmation_mode = "midpoint"
