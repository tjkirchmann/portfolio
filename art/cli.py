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
    p.add_argument("--workers", type=int, default=5, help="parallel Blender workers for renders")
    p.add_argument("--resume", action="store_true", help="keep frames already rendered")
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
    env = dict(os.environ)
    # keep Blender's per-user temp and cache inside the repo cache
    tmp = os.path.join(ART, ".cache", "_blender_tmp")
    os.makedirs(tmp, exist_ok=True)
    env["TMPDIR"] = tmp
    if mode[0] == "render" and a.workers > 1:
        sys.exit(parallel(subject, slug, args, a, env))
    sys.exit(run(args, env))


def blender_cmd(args):
    return [BLENDER, "-b", "--factory-startup", "--python-exit-code", "1",
            "--python", os.path.join(ART, "framework", "main.py"), "--", *args]


def run(args, env, prefix=""):
    cmd = blender_cmd(args)
    print("$ " + " ".join(cmd), flush=True)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            stdin=subprocess.DEVNULL, env=env, cwd=REPO)
    for line in proc.stdout:
        if line.startswith(("Fra:", "Blender quit", "Saved:", "Time:")) or "| Saved:" in line \
                or "Rendering" in line and "/" in line and "render  " in line \
                or "Video append" in line:
            continue
        sys.stdout.write(prefix + line)
        sys.stdout.flush()
    return proc.wait()


def parallel(subject, slug, args, a, env):
    """Split the frames across `a.workers` Blender processes, then loop-check and encode.

    1. prepare: build the subject once (framing, Life history cached in art/.cache/<slug>/)
    2. workers: each renders a contiguous frame range into the shared frames directory
    3. finish: loop check from the files, merged stats, encode, poster, meta.json
    """
    import math
    import re
    import threading
    base = args[1:]  # subject, --slug, ..., --quality ...
    if run(["prepare", *base], env) != 0:
        return 1
    secs = 10.0
    with open(subject) as f:
        m = re.search(r"^LOOP_SECONDS\s*=\s*([0-9.]+)", f.read(), re.M)
        if m:
            secs = float(m.group(1))
    n = int(round(secs * 30))
    k = max(1, min(a.workers, n))
    step = math.ceil(n / k)
    ranges = [(i, min(n, i + step)) for i in range(0, n, step)]
    extra = ["--resume"] if a.resume else []
    if not a.resume:
        root = os.path.join(ART, ".cache", slug, "preview" if a.preview else "")
        for d in ("frames", "black", "loopcheck"):
            dd = os.path.join(root, d)
            if os.path.isdir(dd):
                for fn in os.listdir(dd):
                    if fn.endswith(".png"):
                        os.remove(os.path.join(dd, fn))
    codes = [None] * len(ranges)

    def work(j, lo, hi):
        wargs = ["render", *base, "--frames", str(lo), str(hi), "--no-deliver", *extra]
        if j == 0:
            wargs.append("--loopcheck")
        codes[j] = run(wargs, env, prefix=f"[w{j}] ")

    threads = [threading.Thread(target=work, args=(j, lo, hi)) for j, (lo, hi) in enumerate(ranges)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    if any(c != 0 for c in codes):
        print(f"FAIL: worker exit codes {codes}")
        return 1
    return run(["finish", *base], env)


if __name__ == "__main__":
    main()
