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
    d = sub.add_parser("develop", help="sviluppa un rullino (Originale, e a richiesta Migliorata e AI)")
    d.add_argument("frames", nargs="+", type=Path, help="foto dei fotogrammi")
    d.add_argument("--profile", required=True, help="id del profilo o percorso di un .json")
    d.add_argument("--base", type=Path, help="foto della pellicola non esposta")
    d.add_argument("--light", type=Path, help="foto della fonte di luce senza pellicola")
    d.add_argument("--out", type=Path, default=Path("risultati"), help="cartella di uscita")
    d.add_argument("--no-crop", action="store_true", help="non cercare né ritagliare il fotogramma")
    d.add_argument("--stack", type=int, default=1,
                   help="multi-scatto: unisce ogni N file consecutivi (in ordine di nome) in un fotogramma")
    d.add_argument("--migliora", action="store_true",
                   help="salva anche la versione migliorata (polvere, rumore, nitidezza)")
    d.add_argument("--restauro", action="store_true",
                   help="salva anche la versione restaurata dalla rete addestrata (sperimentale)")
    d.add_argument("--super-ris", type=int, choices=(2, 4), default=0,
                   help="salva anche una versione ingrandita dall'AI (pixel inventati)")
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
        frames = sorted(args.frames, key=lambda p: (p.name, str(p)))
        if args.stack < 1 or len(frames) % args.stack:
            raise ValueError(f"Con --stack {args.stack} il numero di file deve esserne un multiplo "
                             f"(ricevuti {len(frames)})")
        groups = [frames[i:i + args.stack] for i in range(0, len(frames), args.stack)]
        results = develop_roll(groups, profile, Calibration(base, light), args.out,
                               crop=not args.no_crop, enhance=args.migliora,
                               super_res=args.super_ris, restore=args.restauro)
    except (ValueError, FileNotFoundError) as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 2
    for r in results:
        print(f"{r.source.name} -> {r.outputs[0]}")
        for extra in (r.enhanced, r.restored, r.ai):
            if extra:
                print(f"{'':{len(r.source.name)}}    {extra[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
