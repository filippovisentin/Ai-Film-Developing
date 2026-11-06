"""Riga di comando: python -m devguide list | plan bw ... | plan c41 ..."""
from __future__ import annotations

import argparse
import sys

from .recipes import BWRecipe, C41Kit, list_recipes, load_recipe
from .timer import Step, build_bw_session, build_c41_session

SAFETY = [
    "Mai aprire alla luce un rullino non ancora sviluppato: va caricato nella spirale al buio (sacca o stanza buia).",
    "Indossa guanti e occhiali, lavora in un ambiente aerato, tieni i chimici lontani da cibo e bambini.",
    "Smaltimento: fissaggio e sbianca-fissaggio contengono argento, non versarli nello scarico; "
    "portali a un centro di raccolta secondo le regole locali.",
]


def _mmss(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _agitation_text(step: Step) -> str:
    a = step.agitation
    if a is None:
        return ""
    if a.every_s <= 0:
        return f"agita i primi {a.initial_s} s"
    return f"agita i primi {a.initial_s} s, poi {a.inversions} inversioni ogni {a.every_s} s"


def _print_plan(title: str, steps: list[Step], warnings: list[str], recipe) -> None:
    print(title)
    print()
    for i, s in enumerate(steps, 1):
        time_txt = _mmss(s.seconds) if s.seconds else "  -  "
        extra = "; ".join(x for x in (_agitation_text(s), s.note) if x)
        print(f"  {i}. {time_txt}  {s.name}" + (f"  ({extra})" if extra else ""))
    if warnings:
        print()
        for w in warnings:
            print(f"  ! {w}")
    if recipe.notes:
        print()
        for n in recipe.notes:
            print(f"  - {n}")
    print()
    print(f"Fonte: {recipe.source.title} ({recipe.source.date}) - {recipe.source.url}")
    print()
    print("Sicurezza:")
    for line in SAFETY:
        print(f"  * {line}")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="devguide", description="Guida allo sviluppo della pellicola a casa")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="elenca le ricette disponibili")
    plan = sub.add_parser("plan", help="calcola i passi e i tempi")
    proc = plan.add_subparsers(dest="process", required=True)
    bw = proc.add_parser("bw", help="bianco e nero")
    bw.add_argument("--recipe", required=True)
    bw.add_argument("--developer", required=True)
    bw.add_argument("--dilution", required=True)
    bw.add_argument("--ei", type=int, required=True)
    bw.add_argument("--temp", type=float, required=True)
    c41 = proc.add_parser("c41", help="colore C-41")
    c41.add_argument("--recipe", required=True)
    c41.add_argument("--temp", type=float, required=True)
    c41.add_argument("--push", type=int, default=0, help="-1 (pull) ... +3")
    c41.add_argument("--rolls-done", type=int, default=0, help="rullini già sviluppati con questi chimici")
    c41.add_argument("--volume", default="quart", choices=["pint", "quart", "gallon"])
    c41.add_argument("--no-presoak", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "list":
        for rid in list_recipes():
            r = load_recipe(rid)
            print(f"{rid:30} {getattr(r, 'film', getattr(r, 'name', ''))}")
        return 0
    try:
        recipe = load_recipe(args.recipe)
        if args.process == "bw":
            if not isinstance(recipe, BWRecipe):
                raise ValueError(f"{args.recipe} non è una ricetta bianco e nero")
            steps, warnings = build_bw_session(recipe, args.developer, args.dilution, args.ei, args.temp)
            title = f"{recipe.film} a EI {args.ei}, {args.developer} {args.dilution}, {args.temp:g} °C"
        else:
            if not isinstance(recipe, C41Kit):
                raise ValueError(f"{args.recipe} non è un kit C-41")
            steps, warnings = build_c41_session(recipe, args.temp, args.push, args.rolls_done,
                                                args.volume, presoak=not args.no_presoak)
            push = "" if args.push == 0 else f", push {args.push:+d}"
            title = f"{recipe.name}, {args.temp:g} °C{push}, rullini già sviluppati: {args.rolls_done}"
    except ValueError as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 2
    _print_plan(title, steps, warnings, recipe)
    return 0


if __name__ == "__main__":
    sys.exit(main())
