# Test skims

The first 5000 events (tree `mini`) of one ATLAS Open Data 13 TeV MC sample per analysis, for
regression tests of analysis tools (CutLang's CI runs every analysis of this suite on them). They are
too small for physics results: the normalisation in `config/samples/` refers to the full samples.

Source: https://opendata.cern.ch/eos/opendata/atlas/OutreachDatasets/2020-01-22/ (CC0 licence).

| File | Source sample | Used by |
|---|---|---|
| `mc_410000.ttbar_lep.1lep.5000evt.root` | `1lep/MC/mc_410000.ttbar_lep.1lep.root` | WBosonAnalysis, TTbarAnalysis |
| `mc_410011.single_top_tchan.1lep.5000evt.root` | `1lep/MC/mc_410011.single_top_tchan.1lep.root` | SingleTopAnalysis |
| `mc_363490.llll.2lep.5000evt.root` | `2lep/MC/mc_363490.llll.2lep.root` | ZBosonAnalysis |
| `mc_392985.SlepSlep_direct_600p0_300p0_2L8.2lep.5000evt.root` | `2lep/MC/mc_392985.SlepSlep_direct_600p0_300p0_2L8.2lep.root` | SUSYAnalysis |
| `mc_363491.lllv.3lep.5000evt.root` | `3lep/MC/mc_363491.lllv.3lep.root` | WZDiBosonAnalysis |
| `mc_345060.ggH125_ZZ4lep.4lep.5000evt.root` | `4lep/MC/mc_345060.ggH125_ZZ4lep.4lep.root` | HZZAnalysis |
| `mc_363490.llll.4lep.5000evt.root` | `4lep/MC/mc_363490.llll.4lep.root` | ZZDiBosonAnalysis |
| `mc_301325.ZPrime1000_tt.1largeRjet1lep.5000evt.root` | `1largeRjet1lep/MC/mc_301325.ZPrime1000_tt.1largeRjet1lep.root` | ZPrimeBoostedAnalysis |

The samples are chosen so that every region of every analysis keeps events at its last cut: ttbar
gives both lepton flavours for the W boson regions, and llll both Z flavours for the Z boson regions.

Made with `skim.C` (copies the first N entries), for example:
```
root -l -b -q 'skim.C("root://eospublic.cern.ch//eos/opendata/atlas/OutreachDatasets/2020-01-22/1lep/MC/mc_410000.ttbar_lep.1lep.root", "mc_410000.ttbar_lep.1lep.5000evt.root", 5000)'
```
`skims.sha256` holds the checksums (`shasum -a 256 -c skims.sha256`).
