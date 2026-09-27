# Notebooks

Two kinds, both thin front-ends over `epicormic_lab`:

1. Run notebooks (`run_exp_a.ipynb`, ...) call the same functions as the
   scripts, on the same frozen protocol, and write the same run directory
   and registry entry, with `front_end: notebook`. Their first cell installs
   this repository at a pinned commit
   (`pip install "git+https://github.com/jemsbhai/epicormic-paper@<sha>"`),
   so they are Colab-compatible for the mock-only experiments (EXP-A to
   EXP-C). The local control, EXP-D, and EXP-E need a local kernel: the
   control talks to a llama-server on this machine, EXP-D needs the provider
   keys, EXP-E needs NVML on the local GPU.
2. Exploratory notebooks read `analysis/generated/` and draft figures. They
   never produce a paper number.

Outputs are cleared before commit. Notebooks are scanned by
`tools/scan_vocabulary.py` like any other file.
