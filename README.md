# ATLAS Open Data ADL Benchmark Suite

**ADL4ATLASOpenData** contains nine physics analyses of the ATLAS Open Data
13 TeV release (2020, 10 fb⁻¹), written in the Analysis Description Language
(ADL), together with what is needed to run them with the
[CutLang](https://github.com/unelg/CutLang) interpreter and reproduce the
results of the accompanying article:

- one ADL file per analysis, used for all data and simulated samples;
- per-analysis sample configurations: input files, cross-sections, sums of weights, merge groups;
- scripts to run CutLang over the samples, normalise the simulated samples and merge them into plot groups;
- tools to compare outputs bin by bin.

The analyses reproduce the educational analyses of the
[ATLAS Open Data 13 TeV C++ framework](https://github.com/atlas-outreach-data-tools/atlas-outreach-cpp-framework-13tev)
at tag **`10fb-legacy`** (commit `688d73f`). That tag corresponds to the 2020
10 fb⁻¹ release; the main branch of the framework repository now targets newer
ATLAS Open Data releases and is **not** the reference for this suite.

> Status: pre-release. Planned for v1.0.0: container image, reference outputs
> and automated comparison tests, plotting scripts for the article figures.

## Analyses

| Analysis | ADL | Input stream | Files | Input size | Merge groups |
|---|---|---|---|---|---|
| Z boson → ℓℓ | `analyses/ZBosonAnalysis/` | 2lep | 29 | 16.7 GB | data, Zjets, Wjets, stop, ttbar, diboson |
| W boson → ℓν | `analyses/WBosonAnalysis/` | 1lep | 65 | 69.9 GB | data, Wjets, Zjets, stop, ttbar, diboson |
| Single top (t-channel) | `analyses/SingleTopAnalysis/` | 1lep | 65 | 69.9 GB | data, stop_tchan, stop_tWtb, ZVV, Wjets |
| tt̄ (lepton + jets) | `analyses/TTbarAnalysis/` | 1lep | 29 | 50.5 GB | data, ttbar, stop, V, diboson |
| WZ → ℓνℓℓ | `analyses/WZDiBosonAnalysis/` | 3lep | 29 | 0.9 GB | data, WZ, VV, V, top |
| ZZ → 4ℓ | `analyses/ZZDiBosonAnalysis/` | 4lep, 2lep | 29 | 0.6 GB | data, ZZ, WWZ, topV |
| H → ZZ* → 4ℓ | `analyses/HZZAnalysis/` | 4lep | 33 | 0.3 GB | data, Higgs, ZZ, V |
| Slepton search (2ℓ + E_T^miss) | `analyses/SUSYAnalysis/` | 2lep | 105 | 19.6 GB | data, signal, ttbar, stop, diboson, Wjets, Zjets |
| Z′ → tt̄ (boosted) | `analyses/ZPrimeBoostedAnalysis/` | 1largeRjet1lep | 64 | 4.5 GB | data, signal, ttbar, stop, V, diboson |

In total, the nine analyses read 311 files (112.5 GB). The files do not have to
be downloaded: CutLang streams them over HTTP from `opendata.cern.ch`. With a
slow connection, download them once and run from disk with `--input-dir`; see
[`docs/download.md`](docs/download.md) for per-analysis download lists and
commands. The complete list of files, cross-sections and sums of weights is in
[`docs/samples.md`](docs/samples.md).

## Requirements

| Software | Version used for the article | Notes |
|---|---|---|
| CutLang | v2.15.2 (`ad940e8`) | needs ROOT, flex and bison to build |
| ROOT | 6.36.12 | with PyROOT, Davix/xrootd (for running using urls) |
| Python | 3.9 or newer | packages: `pyyaml`, `numpy`, `uproot` |
| OS | Linux or macOS | tested on macOS 26 (arm64) |

Streaming the samples over `http://` needs ROOT built with Davix (`root-config --has-davix`
should print `yes`); ROOT's built-in web reader cannot open the `opendata.cern.ch` links.
Alternatively, set `ntuple_base_url` in `.yaml` configs to the XRootD address
`root://eospublic.cern.ch//eos/opendata/atlas/OutreachDatasets/2020-01-22` (needs ROOT with
XRootD, `root-config --has-xrootd`), or download the files (`docs/download.md`).

## Installation

```bash
# 1. CutLang at the release used for the article
git clone https://github.com/unelg/CutLang.git
cd CutLang && git checkout v2.15.2
cd CLA && make -j4 && cd ../..        # requires ROOT (root-config in PATH), flex, bison
export CUTLANG_DIR=$PWD/CutLang

# 2. This repository and its Python dependencies
git clone https://github.com/ahmetcansansar/ADL4ATLASOpenData.git
cd ADL4ATLASOpenData
python3 -m pip install pyyaml numpy uproot
python3 -c "import ROOT"              # check that PyROOT is available
```

## Quick start (a few minutes)

Run the Z boson analysis on three small samples and the first 20 000 events of
one data period, then normalise and merge:

```bash
python3 scripts/run_analysis.py ZBosonAnalysis --outdir run/Zboson/samples \
    --samples data_A,Wminustaunu,single_top_schan --events 20000 --jobs 3

python3 scripts/normalize_merge.py ZBosonAnalysis \
    --indir run/Zboson/samples --outdir run/Zboson/merged --allow-missing
```

`--allow-missing` lets the merge proceed with only part of the samples.

## Running a full analysis

```bash
python3 scripts/run_analysis.py TTbarAnalysis --outdir run/TTbar/samples --jobs 4
python3 scripts/normalize_merge.py TTbarAnalysis --indir run/TTbar/samples --outdir run/TTbar/merged
```

The analysis name is the directory name under `analyses/`. The run is
resumable: samples whose output already exists are skipped, unless `--force`
is given. While samples run, a status block shows events processed, rate and
estimated time per sample. In a terminal the block is redrawn in place;
when the output goes to a file it is appended every `--progress-interval`
seconds. To run only the data, for example:

```bash
python3 scripts/run_analysis.py WZDiBosonAnalysis --outdir run/WZ/samples \
    --samples data_A,data_B,data_C,data_D --jobs 4
```

### `run_analysis.py` options

| Option | Meaning |
|---|---|
| `--outdir DIR` | where per-sample outputs (`histoOut-<file>.root`) and logs (`logs/<sample>.log`) go |
| `--samples a,b,...` | sample keys from `config/samples/<analysis>.yaml` (default: all) |
| `--jobs N` | number of samples processed at the same time |
| `--cutlang-parallel M` | split each sample into M CutLang processes over event ranges (`CLA.sh -j M`; multi-process, merged with `hadd`). `--jobs N` with `--cutlang-parallel M` starts N×M processes |
| `--events N` | process only the first N events of each sample (for tests) |
| `--input-dir DIR` | read ntuples from a local copy with the same directory layout instead of streaming |
| `--cutlang DIR` | CutLang checkout (default: `$CUTLANG_DIR`) |
| `--progress-interval SEC` | status update interval (default 5; 0 disables it) |
| `--force` | re-run samples whose output exists |

### `normalize_merge.py` options

| Option | Meaning |
|---|---|
| `--indir DIR` | per-sample outputs from `run_analysis.py` |
| `--outdir DIR` | where the merged `<group>.root` files go |
| `--per-sample` | also write each normalised sample to `<outdir>/samples/<sample>.root` |
| `--allow-missing` | merge groups from the samples that are present |

## Outputs

```
run/<analysis>/samples/histoOut-<ntuple>.root   one CutLang output per sample (unnormalised MC)
run/<analysis>/samples/logs/<sample>.log        CutLang log per sample
run/<analysis>/merged/<group>.root              normalised and merged, one file per group
```

Each output file has one directory per ADL `region`, containing the region's
histograms and its `cutflow` histogram (one bin per selection, labelled with
the ADL statement).

## Event weights and normalisation

- **Data:** weight 1.
- **Simulation:** each event is weighted by `XSection × Lumi × scale factors × mcWeight`
  in the ADL (`Lumi` = 10064 pb⁻¹). After the run, each sample is scaled by
  `1/(sumw × eff)`, using the sums of weights and efficiencies of the reference
  framework (`Plotting/inputfiles/Files_*.txt` at tag `10fb-legacy`). These values
  are recorded per sample in `config/samples/<analysis>.yaml`. This is the
  same normalisation the reference framework applies.
- **Single-top samples** (DSID 410011–410026) use `sign(mcWeight)`, and their sum
  of weights is the number of generated events, as in the reference framework.
  The `mcWeight` and `SumWeights` branches of these ntuples are mis-scaled, so no
  sample is normalised with the ntuple `SumWeights` branch.
- **Data vs simulation** is decided in the ADL by `channelNumber`, which holds
  the run number for data (< 310000). The Z′ signal (DSID 301325) is excluded
  from this test explicitly.
- **Raw-count cutflow bins** (those before the first `weight` statement) are not rescaled.

## Validation

`scripts/compare_outputs.py A.root B.root` compares two CutLang outputs
histogram by histogram, and cutflows bin by bin by label.

- The single-ADL workflow with post-run normalisation was checked against the
  per-sample-ADL workflow used for the article: data, simulated and single-top
  samples of the Z′ and Z boson analyses, and the Z′ signal. All histograms and
  cutflow bins agree within a relative difference of 10⁻⁶.
- Splitting a sample into several CutLang processes (`--cutlang-parallel`) gives
  identical outputs to a single process.

## Configuration files

`config/samples/<analysis>.yaml`:

```yaml
analysis: TTbarAnalysis
adl: analyses/TTbarAnalysis/TTbarAnalysis.adl
ntuple_base_url: http://opendata.cern.ch/eos/opendata/atlas/OutreachDatasets/2020-01-22
samples:
  ttbar_lep:
    type: mc
    dsid: 410000
    file: 1lep/MC/mc_410000.ttbar_lep.1lep.root   # relative to ntuple_base_url
    xsec: 452.693559                               # pb
    sumw: 49386600.0
    eff: 1.0
groups:                                            # merged output files <group>.root
  ttbar: [ttbar_lep]
```

`docs/samples.md` lists all samples in readable form (`python3 scripts/list_samples.py` regenerates it).

## Repository layout

```
analyses/<A>/<A>.adl        one ADL per analysis, used for every sample
config/samples/<A>.yaml     input files, cross-sections, sums of weights, merge groups
scripts/run_analysis.py     run CutLang over the samples of an analysis
scripts/normalize_merge.py  normalise MC by 1/(sumw*eff) and merge into groups
scripts/compare_outputs.py  bin-by-bin comparison of two CutLang output files
scripts/list_samples.py     regenerate docs/samples.md
scripts/list_download_links.py  regenerate docs/download.md and docs/download/*.txt
scripts/plot_all.py         plots of the merged outputs, as in the article
docs/                       samples.md, download.md (+ download/<A>.txt URL lists)
```

## Citing

If you use this suite, please cite the article [TBD: reference] and the
release used ([TBD: Zenodo DOI]). The ADL files build on the
[ADL4LHCOpenData](https://github.com/ADL4HEP/ADL4LHCOpenData) collection.

## Licence

[TBD]
