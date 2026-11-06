"""Riga di comando: python -m filmengine develop FOTO... --profile ID"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .calibration import correct_light, light_is_clipped, measure_base
from .imageio_ import load_image
from .pipeline import Calibration, develop_roll
from .profile import list_profiles, load_profile


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="filmengine", description="Sviluppo digitale di negativi")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("profiles", help="elenca i profili pellicola")
    d = sub.add_parser("develop", help="sviluppa un rullino nella versione Originale")
    d.add_argument("frames", nargs="+", type=Path, help="foto dei fotogrammi")
    d.add_argument("--profile", required=True, help="id del profilo o percorso di un .json")
    d.add_argument("--base", type=Path, help="foto della pellicola non esposta")
    d.add_argument("--light", type=Path, help="foto della fonte di luce senza pellicola")
    d.add_argument("--out", type=Path, default=Path("risultati"), help="cartella di uscita")
    d.add_argument("--no-crop", action="store_true", help="non cercare né ritagliare il fotogramma")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "profiles":
        for pid in list_profiles():
            print(f"{pid:16} {load_profile(pid).name}")
        return 0
    try:
        profile = load_profile(args.profile)
        light = load_image(args.light).rgb if args.light else None
        usable = None if light is None or light_is_clipped(light) else light
        base = measure_base(correct_light(load_image(args.base).rgb, usable)) if args.base else None
        results = develop_roll(args.frames, profile, Calibration(base, light), args.out,
                               crop=not args.no_crop)
    except (ValueError, FileNotFoundError) as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 2
    for r in results:
        print(f"{r.source.name} -> {r.outputs[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
