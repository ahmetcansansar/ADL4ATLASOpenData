#!/usr/bin/env python3
"""Run CutLang with an analysis ADL over its samples.

Each sample runs in its own scratch directory (CLA.sh writes its output to the
current directory under a name derived from the ADL, which is shared by all
samples); the result is moved to <outdir>/histoOut-<ntuple stem>.root.

Two levels of parallelism:
  --jobs N              N samples run at the same time (one CLA.sh each)
  --cutlang-parallel M  each sample is split by CutLang into M processes over
                        event ranges (CLA.sh -j M); jobs x M processes in total

While samples run, a status block with events processed, rate and ETA per
running sample is updated every --progress-interval seconds (0 disables it):
redrawn in place in a terminal, appended when output goes to a file.
Progress is read from the CutLang logs.

Usage:
  run_analysis.py <analysis> --outdir RUN/samples [--samples k1,k2] [--jobs N]
                  [--cutlang-parallel M] [--events N] [--input-dir DIR]
                  [--cutlang DIR] [--progress-interval SEC]
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchlib import load_config, output_name, sample_url  # noqa: E402

# What CutLang prints while running (CLA/atlasopenR2.C, runs/CLA.sh)
N_ENTRIES = re.compile(r"number of entries (\d+)")
START = re.compile(r"starting entry (\d+)")
EVENT = re.compile(r"Processing event (\d+)")
TOTAL = re.compile(r"Total number of events: (\d+)")  # CLA.sh -j only
EMPTY_INPUT = "No events found in files"

running = {}  # sample key -> {"start": time, "pid": CLA.sh pid, "log": Path}


def run_one(cfg, key, args):
    sample = cfg["samples"][key]
    target = Path(args.outdir) / output_name(sample)
    empty_marker = target.with_name(target.name + ".empty")
    if not args.force:
        if target.exists():
            return key, "exists", None
        if empty_marker.exists():
            return key, "empty (0 events)", None
    src = (str(Path(args.input_dir) / sample["file"]) if args.input_dir
           else sample_url(cfg, sample))
    cmd = [str(Path(args.cutlang) / "runs" / "CLA.sh"), src, "ATLASODR2",
           "-i", str(cfg["adl_path"])]
    if args.events:
        cmd += ["-e", str(args.events)]
    if args.cutlang_parallel > 1:
        cmd += ["-j", str(args.cutlang_parallel)]
    log = Path(args.outdir) / "logs" / f"{key}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"cla_{key}_") as work:
        with open(log, "w") as fh:
            proc = subprocess.Popen(cmd, cwd=work, stdout=fh, stderr=subprocess.STDOUT)
            running[key] = {"start": time.time(), "pid": proc.pid, "log": log}
            rc = proc.wait()
        state = running.pop(key)
        produced = Path(work) / f"histoOut-{cfg['adl_path'].stem}.root"
        if EMPTY_INPUT in _read(log):
            # e.g. W+jets in the 4lep stream: the ntuple has no events, CutLang writes no output
            empty_marker.write_text("input ntuple has no events\n")
            return key, "empty (0 events)", None
        if rc != 0 or not produced.exists():
            return key, f"FAILED (rc={rc}, see {log})", None
        shutil.move(produced, target)
    detail = f"{hms(time.time() - state['start'])}"
    events = events_processed(target)
    if events is None:
        # CutLang stopped before writing any cutflow (seen with interrupted HTTP streams);
        # keep the file for inspection but under a name that is re-run next time
        target.rename(target.with_name(target.name + ".incomplete"))
        return key, f"FAILED (output has no cutflow, CutLang stopped early; see {log})", None
    return key, "ok", detail + f", {events:,} events"


def events_processed(path):
    """Raw event count: the 'all Events' bin of any cutflow in a CutLang output."""
    try:
        import uproot
        with uproot.open(path) as f:
            name = next(k for k, c in f.classnames().items() if k.split(";")[0].endswith("/cutflow"))
            return int(round(f[name].values()[0]))
    except Exception:
        return None


def _read(path):
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return ""


def _done_total(text):
    """(events done, events in this process's range) from one CutLang output."""
    n, s, e = N_ENTRIES.findall(text), START.findall(text), EVENT.findall(text)
    if not n:
        return None
    start = int(s[-1]) if s else 0
    done = int(e[-1]) - start if e else 0
    return max(done, 0), int(n[-1])


def progress(state, cutlang_dir):
    """(done, total) for a running sample, or None before CutLang has started.

    With CLA.sh -j the sub-processes write to <CutLang>/temp_adl_<pid>/out_*.txt.
    'done' advances in steps of 5000 events (CutLang's print interval).
    """
    text = _read(state["log"])
    subs = sorted(Path(cutlang_dir).glob(f"temp_adl_{state['pid']}/out_*.txt"))
    if subs or TOTAL.search(text):
        parts = [p for p in (_done_total(_read(f)) for f in subs) if p]
        total = TOTAL.findall(text)
        total = int(total[-1]) if total else sum(t for _, t in parts)
        if not total:
            return None
        return sum(d for d, _ in parts), total
    return _done_total(text)


def hms(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def status_lines(t0, n_done, n_total, cutlang_dir):
    n_run = len(running)
    lines = [f"[{hms(time.time() - t0)}] {n_done}/{n_total} done, {n_run} running, "
             f"{n_total - n_done - n_run} waiting"]
    for key, state in sorted(running.items()):
        p = progress(state, cutlang_dir)
        if not p:
            lines.append(f"  {key:30s} starting ({hms(time.time() - state['start'])})")
            continue
        done, total = p
        now = time.time()
        first_t, first_done = state.setdefault("first", (now, done))  # excludes file-opening time
        rate = (done - first_done) / (now - first_t) if now > first_t else 0.0
        if rate > 0:
            speed, eta = f"{rate / 1000:6.1f}k ev/s", hms((total - done) / rate)
        else:
            speed, eta = "   --  ev/s", "--:--:--"
        lines.append(f"  {key:30s} {done:>12,} / {total:<12,} ({100 * done / total:5.1f}%)  "
                     f"{speed}  ETA {eta}")
    return lines


class StatusBlock:
    """Status lines kept at the bottom of a terminal and redrawn in place;
    when stdout is not a terminal (log file, nohup), blocks are appended."""

    def __init__(self):
        self.live = sys.stdout.isatty()
        self.shown = 0  # lines currently drawn

    def clear(self):
        if self.live and self.shown:
            sys.stdout.write("\033[1A\r\033[K" * self.shown)  # cursor up + erase, per line
            self.shown = 0

    def draw(self, lines):
        self.clear()
        if self.live:  # a wrapped line would break the line count, so truncate
            width = shutil.get_terminal_size().columns - 1
            lines = [line[:width] for line in lines]
            self.shown = len(lines)
        print("\n".join(lines), flush=True)

    def message(self, text):
        """Print a permanent line (sample result) above the status block."""
        self.clear()
        print(text, flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("analysis")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--samples", help="comma-separated sample keys (default: all)")
    ap.add_argument("--jobs", type=int, default=1, help="samples run at the same time")
    ap.add_argument("--cutlang-parallel", type=int, default=1, metavar="M",
                    help="split each sample into M CutLang processes over event ranges (CLA.sh -j)")
    ap.add_argument("--events", type=int, help="process only the first N events per sample")
    ap.add_argument("--input-dir", help="local mirror of the ntuple tree (default: stream from CERN)")
    ap.add_argument("--cutlang", default=os.environ.get("CUTLANG_DIR", "CutLang"),
                    help="CutLang checkout (default: $CUTLANG_DIR)")
    ap.add_argument("--force", action="store_true", help="re-run samples whose output exists")
    ap.add_argument("--progress-interval", type=float, default=5, metavar="SEC",
                    help="seconds between status updates; redrawn in place in a terminal, "
                         "appended in a log file (0: no status, only per-sample results)")
    args = ap.parse_args()

    args.cutlang = str(Path(args.cutlang).resolve())  # samples run in scratch dirs
    if args.input_dir:
        args.input_dir = str(Path(args.input_dir).resolve())
    cfg = load_config(args.analysis)
    keys = args.samples.split(",") if args.samples else list(cfg["samples"])
    unknown = [k for k in keys if k not in cfg["samples"]]
    if unknown:
        sys.exit(f"unknown samples: {', '.join(unknown)}")
    if args.cutlang_parallel < 1:
        sys.exit("--cutlang-parallel must be >= 1")
    ncpu = os.cpu_count() or 1
    if args.cutlang_parallel > 1 and args.jobs * args.cutlang_parallel > ncpu:
        print(f"warning: {args.jobs} jobs x {args.cutlang_parallel} CutLang processes "
              f"= {args.jobs * args.cutlang_parallel} > {ncpu} CPUs", file=sys.stderr)
    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    failed, t0, n_done = [], time.time(), 0
    last_status, block = t0, StatusBlock()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        pending = {pool.submit(run_one, cfg, k, args) for k in keys}
        while pending:
            finished, pending = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
            for fut in finished:
                key, status, detail = fut.result()
                n_done += 1
                block.message(f"{key:40s} {status}" + (f"   ({detail})" if detail else ""))
                if status.startswith("FAILED"):
                    failed.append(key)
            now = time.time()
            redraw = block.live and block.shown == 0 and finished  # restore block after a result line
            if args.progress_interval > 0 and pending and (redraw or now - last_status >= args.progress_interval):
                block.draw(status_lines(t0, n_done, len(keys), args.cutlang))
                last_status = now
    block.clear()
    print(f"finished {len(keys)} samples in {hms(time.time() - t0)}", flush=True)
    if failed:
        sys.exit(f"{len(failed)} samples failed")


if __name__ == "__main__":
    main()
