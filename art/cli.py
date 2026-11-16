#!/usr/bin/env python3
"""Render wireframe loops.

  python3 art/cli.py <slug>               final render -> public/art/<slug>/
  python3 art/cli.py <slug> --preview     fast 600px render -> art/.cache/<slug>/preview/
  python3 art/cli.py --check <slug>       camera, loop, mesh, motion and output checks
  python3 art/cli.py <slug> --still 0 0.5 [--no-back-dim] [--preview]
                                          stills -> art/.cache/<slug>/stills/

Everything runs inside Blender (headless, --factory-startup, so the user's Blender config
is never read or written). All files are written inside the repo.
"""
import argparse
import os
import subprocess
import sys

ART = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ART)
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("slug", nargs="?")
    p.add_argument("--check", metavar="SLUG")
    p.add_argument("--preview", action="store_true")
    p.add_argument("--still", type=float, nargs="+", metavar="T")
    p.add_argument("--no-back-dim", action="store_true")
    p.add_argument("--encode-only", action="store_true", help="re-encode cached frames")
    a = p.parse_args()
    slug = a.check or a.slug
    if not slug:
        p.error("give a slug")
    subject = os.path.join(ART, "subjects", f"{slug}.py")
    if not os.path.exists(subject):
        p.error(f"no subject file {subject}")
    if a.check:
        mode = ["check"]
    elif a.encode_only:
        mode = ["encode"]
    elif a.still is not None:
        mode = ["still", "--t", *map(str, a.still)]
    else:
        mode = ["render"]
    args = [mode[0], subject, "--slug", slug, "--quality", "preview" if a.preview else "final", *mode[1:]]
    if a.no_back_dim:
        args.append("--no-back-dim")
    cmd = [BLENDER, "-b", "--factory-startup", "--python-exit-code", "1",
           "--python", os.path.join(ART, "framework", "main.py"), "--", *args]
    print("$ " + " ".join(cmd), flush=True)
    env = dict(os.environ)
    # keep Blender's per-user temp and cache inside the repo cache
    tmp = os.path.join(ART, ".cache", "_blender_tmp")
    os.makedirs(tmp, exist_ok=True)
    env["TMPDIR"] = tmp
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            stdin=subprocess.DEVNULL, env=env, cwd=REPO)
    for line in proc.stdout:
        if line.startswith(("Fra:", "Blender quit", "Saved:", "Time:")) or "| Saved:" in line \
                or "Rendering" in line and "/" in line and "render  " in line:
            continue
        sys.stdout.write(line)
        sys.stdout.flush()
    sys.exit(proc.wait())


if __name__ == "__main__":
    main()
