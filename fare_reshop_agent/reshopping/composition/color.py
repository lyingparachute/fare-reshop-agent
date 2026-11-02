import os
import sys
from collections.abc import Mapping
from enum import StrEnum

NO_COLOR_VARIABLE = "NO_COLOR"


class ColorSetting(StrEnum):
    ON = "on"
    OFF = "off"


def color_setting(environ: Mapping[str, str], is_terminal: bool) -> ColorSetting:
    if environ.get(NO_COLOR_VARIABLE, "") or not is_terminal:
        return ColorSetting.OFF
    return ColorSetting.ON


def standard_output_color() -> ColorSetting:
    return color_setting(os.environ, sys.stdout.isatty())
