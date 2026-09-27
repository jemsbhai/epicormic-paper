# Analysis

`src/epicormic_lab/analysis.py` turns run outputs into the summaries under
`generated/`; `scripts/make_figures.py` turns those summaries into
`figures/`. Both are deterministic given the run directories they read, and
both are the only writers of their output directories.
