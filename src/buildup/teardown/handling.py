"""Handling presets: the ``vehicle`` element's driving parameters, by kind of vehicle.

Each preset is the parameter set of one official vehicle of that kind (docs/TEARDOWN_REFERENCE.md
§6, ``FILES``): every combination is one the game's own vehicles drive with. On Buildup models
``car`` and ``sports`` are verified in game (protocol G2), the others not yet. ``basic`` is the
set of Buildup's calibration car (§5).
"""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Handling:
    """Driving parameters written on the skeleton's ``vehicle`` element.

    Attributes:
        name: Preset name.
        summary: One line for the AI: what it drives like and where the values come from.
        attributes: XML attributes, in the official files' order.
    """

    name: str
    summary: str
    attributes: dict[str, str]


HANDLING: Final[dict[str, Handling]] = {
    preset.name: preset
    for preset in (
        Handling(
            "car",
            "ordinary car: values of the official saloon car (topspeed 90, acceleration 6, "
            "spring 1.0, damping 1.5, steerassist 0.4)",
            {
                "sound": "small1 0.8",
                "spring": "1.0",
                "damping": "1.5",
                "topspeed": "90",
                "acceleration": "6",
                "strength": "4",
                "antiroll": "0.2",
                "difflock": "0.2",
                "steerassist": "0.4",
                "friction": "1.8",
            },
        ),
        Handling(
            "sports",
            "sports or racing car: values of the official Crownzygot (topspeed 120, "
            "acceleration 8, strength 8, friction 1.9)",
            {
                "sound": "racingcar",
                "spring": "1.2",
                "topspeed": "120",
                "acceleration": "8",
                "strength": "8",
                "antispin": "0",
                "antiroll": "0.2",
                "difflock": ".1",
                "steerassist": "0.4",
                "friction": "1.9",
            },
        ),
        Handling(
            "offroad",
            "pickup, SUV or 4x4: values of the official Taskmaster pickup (topspeed 75, "
            "acceleration 5, spring 0.6, steerassist 0.5)",
            {
                "sound": "pickup",
                "spring": "0.6",
                "damping": "0.8",
                "topspeed": "75",
                "acceleration": "5",
                "strength": "5",
                "antispin": "0",
                "antiroll": "0.4",
                "steerassist": "0.5",
            },
        ),
        Handling(
            "van",
            "van or minibus: values of the official van (topspeed 70, acceleration 4, strength 2)",
            {
                "sound": "van",
                "spring": "0.5",
                "damping": "0.7",
                "topspeed": "70",
                "acceleration": "4",
                "strength": "2",
                "antispin": "1",
                "antiroll": "0.25",
                "steerassist": "0.0",
            },
        ),
        Handling(
            "truck",
            "truck or bus: values of the official semi truck (topspeed 70, acceleration 5, "
            "antiroll 0.6)",
            {
                "sound": "semitruck",
                "spring": "0.5",
                "damping": "0.5",
                "topspeed": "70",
                "acceleration": "5",
                "strength": "5",
                "antispin": "1",
                "antiroll": "0.6",
                "difflock": "0.5",
                "steerassist": "0.2",
            },
        ),
        Handling(
            "basic",
            "Buildup's calibration car (topspeed 60, spring 0.5, damping 0.7 only; in "
            "protocol G Buildup vehicles with these values sat low, steered badly and all "
            "reached the same speed)",
            {"spring": "0.5", "damping": "0.7", "topspeed": "60"},
        ),
    )
}
HANDLING_NAMES: Final = tuple(HANDLING)
DEFAULT_HANDLING: Final = "car"


def handling(name: str) -> Handling:
    """A preset by name.

    Raises:
        KeyError: For an unknown name (the message lists the presets).
    """
    if name not in HANDLING:
        raise KeyError(f"unknown handling {name!r}; presets: {', '.join(HANDLING)}")
    return HANDLING[name]
