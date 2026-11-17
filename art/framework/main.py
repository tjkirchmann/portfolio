"""Blender-side entry point. Run by art/cli.py as:

Blender -b --factory-startup --python art/framework/main.py -- <mode> <subject.py> [options]
"""
import argparse
import json
import os
import sys

sys.dont_write_bytecode = True  # keep __pycache__ out of the repo

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.dirname(HERE)
sys.path.insert(0, ART)

from framework import scene as scenemod  # noqa: E402
from framework.render import Renderer  # noqa: E402


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:]
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["still", "render", "check", "encode"])
    p.add_argument("subject")
    p.add_argument("--slug", required=True)
    p.add_argument("--quality", default="final")
    p.add_argument("--t", type=float, nargs="*", default=[0.0])
    p.add_argument("--out", default=None)
    p.add_argument("--no-back-dim", action="store_true")
    p.add_argument("--public", default=None)
    return p.parse_args(argv)


def main():
    a = parse()
    cache = os.path.join(ART, ".cache", a.slug)
    if a.public is None:
        a.public = os.path.join(os.path.dirname(ART), "public", "art", a.slug)
    os.makedirs(cache, exist_ok=True)
    stage = scenemod.Stage(a.subject)
    if a.mode == "still":
        r = Renderer(stage, a.quality, os.path.join(cache, "tmp"), back_dim=not a.no_back_dim)
        out = a.out or os.path.join(cache, "stills")
        os.makedirs(out, exist_ok=True)
        for t in a.t:
            tag = f"t{t:.3f}" + ("_nodim" if a.no_back_dim else "")
            _, st = r.render(t, os.path.join(out, f"{tag}_rgba.png"), os.path.join(out, f"{tag}.png"))
            print("STILL", tag, json.dumps(st))
    elif a.mode == "render":
        from framework import pipeline
        sys.exit(pipeline.render_all(stage, a, cache))
    elif a.mode == "encode":
        from framework import pipeline
        sys.exit(pipeline.deliver(stage, a, cache))
    elif a.mode == "check":
        from framework import checks
        sys.exit(checks.run(stage, a, cache))


main()
