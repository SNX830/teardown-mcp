"""Rendering finish of a palette entry (MagicaVoxel ``MATL`` material).

The finish only changes how a voxel looks in Teardown, never its physical material.
Source and verification status: docs/TEARDOWN_REFERENCE.md §3.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Self


class FinishKind(StrEnum):
    """How a palette entry is rendered."""

    MATTE = "matte"
    """Diffuse: equivalent to metal with maximum roughness."""
    METAL = "metal"
    """The normal case. ``metallic`` 0 for painted surfaces, low values for raw metal."""
    GLASS = "glass"
    """Transparent glass rendering."""
    EMISSIVE = "emissive"
    """Glowing voxels (lamps, lights); ``emission`` and ``power`` set the intensity."""


# Most common key set and values of MATL entries in official version-150 game files
# (docs/TEARDOWN_REFERENCE.md §3).
_BASE_MATL: dict[str, str] = {
    "_weight": "1",
    "_rough": "0.1",
    "_spec": "0.5",
    "_spec_p": "0.5",
    "_ior": "0.3",
    "_att": "0",
    "_g0": "-0.5",
    "_g1": "0.8",
    "_gw": "0.7",
    "_flux": "0",
    "_ldr": "0",
}

# MATL `_weight` written for glass: the value of official transparent windows. Which value makes
# glass opaque is UNVERIFIED, so no opaque option is offered (docs/TEARDOWN_REFERENCE.md §3).
_GLASS_WEIGHT = 0.5

#: Highest emissive power: official files use `_flux` values 0 to 4.
MAX_EMISSIVE_POWER = 4.0


def _check_unit(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1, got {value}")


def _fmt(value: float) -> str:
    return f"{value:g}"


@dataclass(frozen=True)
class Finish:
    """Rendering finish of a palette entry. Build it with the class methods.

    Attributes:
        kind: Finish kind.
        roughness: 0 (polished) to 1 (dull). Used by metal and matte.
        metallic: 0 (painted) to 1 (mirror-like). Used by metal.
        emission: Emissive only: 0 to 1.
        power: Emissive only: intensity factor, 0 to 4 (official values; 2 is the most common).
    """

    kind: FinishKind = FinishKind.MATTE
    roughness: float = 1.0
    metallic: float = 0.0
    emission: float = 0.0
    power: float = 0.0

    def __post_init__(self) -> None:
        _check_unit("roughness", self.roughness)
        _check_unit("metallic", self.metallic)
        _check_unit("emission", self.emission)
        if not 0.0 <= self.power <= MAX_EMISSIVE_POWER:
            raise ValueError(f"power must be between 0 and {MAX_EMISSIVE_POWER}, got {self.power}")

    @classmethod
    def matte(cls) -> Self:
        """Plain, non-reflective surface."""
        return cls(FinishKind.MATTE)

    @classmethod
    def metal(cls, roughness: float = 0.5, metallic: float = 0.0) -> Self:
        """Standard surface. Keep ``metallic`` at 0 for painted surfaces."""
        return cls(FinishKind.METAL, roughness=roughness, metallic=metallic)

    @classmethod
    def glass(cls) -> Self:
        """Transparent glass rendering, as on official car windows."""
        return cls(FinishKind.GLASS, roughness=0.1)

    @classmethod
    def emissive(cls, emission: float = 0.5, power: float = 2.0) -> Self:
        """Glowing surface, for lamps and vehicle lights."""
        return cls(FinishKind.EMISSIVE, roughness=0.1, emission=emission, power=power)

    def to_matl(self) -> dict[str, str]:
        """Return the MagicaVoxel ``MATL`` dictionary for this finish (version-150 layout)."""
        matl = {"_type": "", **_BASE_MATL}  # "_type" first, as in official files
        match self.kind:
            case FinishKind.MATTE:
                matl.update(_type="_diffuse", _rough=_fmt(self.roughness))
            case FinishKind.METAL:
                matl.update(
                    _type="_metal", _weight=_fmt(self.metallic), _rough=_fmt(self.roughness)
                )
            case FinishKind.GLASS:
                matl.update(
                    _type="_glass", _weight=_fmt(_GLASS_WEIGHT), _rough=_fmt(self.roughness)
                )
            case FinishKind.EMISSIVE:
                matl.update(
                    _type="_emit",
                    _weight=_fmt(self.emission),
                    _rough=_fmt(self.roughness),
                    _flux=_fmt(self.power),
                )
        return matl
