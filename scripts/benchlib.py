"""Shared helpers: sample configuration and CutLang output conventions."""
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]


def load_config(analysis_or_path):
    """Load config/samples/<analysis>.yaml (or an explicit path)."""
    p = Path(analysis_or_path)
    if not p.suffix:
        p = REPO / "config" / "samples" / f"{analysis_or_path}.yaml"
    cfg = yaml.safe_load(p.read_text())
    cfg["adl_path"] = REPO / cfg["adl"]
    return cfg


def output_name(sample):
    """Per-sample CutLang output file name, e.g. histoOut-mc_410000.ttbar_lep.1lep.root."""
    return f"histoOut-{Path(sample['file']).stem}.root"


def sample_url(cfg, sample):
    return f"{cfg['ntuple_base_url']}/{sample['file']}"


def scale_factor(sample):
    """Post-processing normalisation; Lumi and XSection are applied in the ADL."""
    if sample["type"] == "data":
        return 1.0
    return 1.0 / (sample["sumw"] * sample.get("eff", 1.0))


def weight_labels(adl_path):
    """Cutflow bin labels CutLang writes for `weight <name> <expr>` statements.

    Cutflow bins before the first such label count raw events and must not be
    rescaled; every bin from it on is weighted.
    """
    labels = set()
    for line in Path(adl_path).read_text().splitlines():
        m = re.match(r"^\s*weight\s+(\w+)\s+(\S+)", line)
        if m:
            labels.add(f"{m[1]} {m[2]}")
    return labels
