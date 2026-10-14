#!/usr/bin/env python3
"""Normalise per-sample CutLang outputs and merge them into plot groups.

Each MC sample is scaled by 1/(sumw*eff) from config/samples/<analysis>.yaml
(XSection and Lumi are already in the ADL event weight). Raw-count cutflow bins
(those before the first `weight` statement) are left untouched. Samples are
then summed into the groups listed in the config.

Usage:
  normalize_merge.py <analysis> --indir RUN/samples --outdir RUN/merged [--per-sample]
"""
import argparse
import sys
from pathlib import Path

import ROOT

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchlib import load_config, output_name, scale_factor, weight_labels  # noqa: E402

ROOT.TH1.AddDirectory(False)
ROOT.gROOT.SetBatch(True)


def first_weighted_bin(h, labels):
    """1-based index of the first weighted cutflow bin (nbins+1 if none)."""
    for i in range(1, h.GetNbinsX() + 1):
        if h.GetXaxis().GetBinLabel(i) in labels:
            return i
    return h.GetNbinsX() + 1


def scaled_copy(h, factor, labels):
    out = h.Clone()
    if factor == 1.0:
        return out
    if h.GetName() != "cutflow":
        out.Scale(factor)
        return out
    first = first_weighted_bin(h, labels)
    # A labelled cutflow axis can extend: writing the overflow bin would make
    # ROOT double the axis. Freeze it while rescaling.
    can_extend = out.CanExtendAllAxes()
    out.SetCanExtend(ROOT.TH1.kNoAxis)
    for i in range(first, h.GetNbinsX() + 2):
        out.SetBinContent(i, h.GetBinContent(i) * factor)
        out.SetBinError(i, h.GetBinError(i) * factor)
    if can_extend:
        out.SetCanExtend(ROOT.TH1.kAllAxes)
    return out


def read_objects(path, factor, labels):
    """{dir/name: object} for every histogram (scaled) and TText in a CutLang output."""
    f = ROOT.TFile.Open(str(path))
    if not f or f.IsZombie():
        raise OSError(f"cannot open {path}")
    objs = {}
    for dkey in f.GetListOfKeys():
        d = dkey.ReadObj()
        if not d.InheritsFrom("TDirectory"):
            continue
        for key in d.GetListOfKeys():
            obj = key.ReadObj()
            name = f"{d.GetName()}/{key.GetName()}"
            if obj.InheritsFrom("TH1"):
                objs[name] = scaled_copy(obj, factor, labels)
            elif obj.InheritsFrom("TText"):
                objs[name] = obj.Clone()
            # TNtuple "rntuple" bookkeeping trees are not carried over
    f.Close()
    return objs


def add_into(acc, objs):
    for name, obj in objs.items():
        if name not in acc:
            acc[name] = obj
        elif obj.InheritsFrom("TH1"):
            acc[name].Add(obj)


def write(path, objs):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = ROOT.TFile(str(path), "RECREATE")
    for name in objs:  # preserve directory order of the first input
        dname, oname = name.split("/", 1)
        d = f.GetDirectory(dname) or f.mkdir(dname)
        d.cd()
        objs[name].Write(oname)
    f.Close()


def normalise_sample(cfg, key, indir, labels):
    sample = cfg["samples"][key]
    path = Path(indir) / output_name(sample)
    return read_objects(path, scale_factor(sample), labels)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("analysis", help="analysis name or path to its samples YAML")
    ap.add_argument("--indir", required=True, help="directory with per-sample CutLang outputs")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--per-sample", action="store_true",
                    help="also write each normalised sample as <outdir>/samples/<key>.root")
    ap.add_argument("--allow-missing", action="store_true",
                    help="merge groups from the samples present (reduced runs)")
    args = ap.parse_args()

    cfg = load_config(args.analysis)
    labels = weight_labels(cfg["adl_path"])
    outdir = Path(args.outdir)
    missing = []
    for group, keys in cfg["groups"].items():
        acc = {}
        n_empty = 0
        for key in keys:
            out = Path(args.indir) / output_name(cfg["samples"][key])
            if not out.exists():
                if out.with_name(out.name + ".empty").exists():  # 0-event ntuple, contributes nothing
                    n_empty += 1
                else:
                    missing.append(key)
                continue
            objs = normalise_sample(cfg, key, args.indir, labels)
            if args.per_sample:
                write(outdir / "samples" / f"{key}.root", objs)
            add_into(acc, objs)
        if acc:
            write(outdir / f"{group}.root", acc)
            used = len(keys) - n_empty - sum(k in missing for k in keys)
            print(f"{group}.root <- {used}/{len(keys)} samples" + (f" ({n_empty} empty)" if n_empty else ""))
    if missing:
        print(f"missing outputs for {len(missing)} samples: {', '.join(missing)}", file=sys.stderr)
        if not args.allow_missing:
            sys.exit(1)


if __name__ == "__main__":
    main()
