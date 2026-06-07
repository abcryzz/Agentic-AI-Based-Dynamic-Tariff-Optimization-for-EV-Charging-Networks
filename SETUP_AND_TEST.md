# OP26 — Setup & Physical Test Guide

A step-by-step way to install this project, run it, and **see for yourself that it works** —
both with an automated self-test and with numbers you can eyeball. No prior knowledge of the
code is assumed.

---

## 0. What you need first

| Requirement | Why | How to check |
|---|---|---|
| **Python 3.10–3.12** | runs the whole pipeline | `python3 --version` |
| **pip** | installs the libraries | `pip --version` |
| **The OpenProject raw data files** (10 files, listed below) | the code reads these | you downloaded them from the OpenProject Drive |
| Node.js 18+ *(optional)* | only to **rebuild** the deck; the finished `.pptx` is already included | `node --version` |

The 10 raw files the code expects (exact names):

```
acndata_sessions_json.xlsx   occupancy.csv   volume.csv   duration.csv   price.csv
information.csv              stations.csv    adj.csv       distance.csv   time.csv
```

---

## 1. Unzip and open a terminal in the folder

```bash
unzip OP26_submission_FINAL.zip
cd op26_submission
```

You should see `preprocess.py`, `demand.py`, …, `verify.py`, `requirements.txt`, `figures/`,
`outputs/`, `notebooks/`, `deck/`.

## 2. Create an isolated environment and install the libraries

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

This pulls pandas, numpy, scikit-learn, matplotlib, seaborn, scipy, openpyxl, jupyter. Takes a
couple of minutes. (`lightgbm`/`pyarrow` are **not** required — the code uses scikit-learn's
HistGradientBoosting and gzipped CSV.)

## 3. Tell the code where the raw data is

Pick **one** option:

- **A — drop the files in `data_raw/`**: copy the 10 raw files into the `data_raw/` folder that
  ships in this package (it has a placeholder note inside).
- **B — point an environment variable at them** (leave the files wherever they are):
  ```bash
  export OP26_DATA=/full/path/to/the/raw/files       # macOS/Linux
  setx OP26_DATA "C:\full\path\to\the\raw\files"      # Windows (reopen terminal after)
  ```

## 4. Run the pipeline (in this order)

Each script prints a short summary and writes its results into `outputs/` and `figures/`.

```bash
python preprocess.py      # builds the unified panel + cleaned ACN sessions
python eda.py             # exploratory analysis + figures + peak windows
python demand.py          # Agent 1 — demand/congestion forecasting
python pricing.py         # Agent 2 — elasticity + dynamic tariff
python monitoring.py      # Agent 3 — feedback loop / online learning
python robustness.py      # stress tests + implications.md
```

**Expected total runtime: a few minutes** on a normal laptop. If a script errors with
`FileNotFoundError`, your raw-data path in Step 3 is wrong — fix it and re-run.

---

## 5. PHYSICAL TEST #1 — the automated self-test (the main gate)

```bash
python verify.py
```

This re-opens the files the pipeline wrote and checks shapes, value ranges, the energy
reconciliation, and the headline metrics. **You want to see this:**

```
14/14 checks passed. ALL GOOD ✓
```

(The command also exits with code 0 on success, 1 on failure — handy for a CI gate.)
What it actually verifies, in plain terms:

- all expected output files exist;
- the hourly panel is exactly **177,840 rows × 42 columns** and utilization is within **[0, 1]**;
- the cleaned ACN data is **≈ 14,947 sessions**;
- the **energy in the hourly panel reconciles exactly to the raw 5-minute totals** (a strong sign preprocessing is correct);
- demand model **R² > 0.90**, **RMSE < 0.05**, and it **beats the persistence baseline**; congestion **AUC > 0.95**;
- the estimated elasticity is **negative and inelastic** (−0.5 < ε < −0.2);
- exactly **one** recommended pricing policy is flagged and it is **~revenue-neutral** (|gain| < 1.5%);
- the learning loop **improved over episodes** and its **online elasticity estimate converged** to the true value.

If any line says `FAIL`, the detail text tells you which number was off and by how much.

## 6. PHYSICAL TEST #2 — eyeball the "golden numbers"

Open these files and confirm the values match. (They are deterministic — a fixed random seed
means you should get **these exact numbers**, not just close ones.)

| What to check | Expected value | Where to look |
|---|---|---|
| Panel size | 177,840 rows | `verify.py` output, or row count of `outputs/urbanev_panel_hourly.csv.gz` |
| Utilization forecast quality | **R² 0.959**, RMSE 0.0356 | `outputs/demand_metrics.csv` (target=utilization, model=GBM) |
| Congestion detection | **AUC 0.992** | `outputs/demand_metrics.csv` (target=congestion) |
| Demand elasticity | **ε ≈ −0.32** | `outputs/elasticity_estimates.csv` (energy_kwh / overall) |
| Recommended tariff | discount **0.90×** / surge **1.60×**, revenue **−0.26%** | `outputs/revenue_gain.csv` (row where `is_recommended` = True) |
| Learning improved | wait-reduction **~29% → ~58%** | `outputs/episode_metrics.csv` (first vs last row) |

## 7. Look at the results the way a reviewer would

- **Figures** — open the 19 PNGs in `figures/` (e.g. `fig01_intraday_utilization.png`,
  `fig09_demand_pred.png`, `fig13_policy_frontier.png`, `fig15_learning_curve.png`).
- **The deck** — open `deck/OP26_deck.pptx` (10 slides: cover, exec summary, 6 content, appendix).
- **Written findings** — read `outputs/eda_findings.md`, `outputs/pricing_findings.md`,
  `outputs/implications.md`, and the assumptions in `ASSUMPTIONS.md`.
- **Every score** is in a CSV under `outputs/` — open any of them in Excel / a viewer.

---

## Alternative: run it as notebooks

If you prefer notebooks to scripts:

```bash
jupyter notebook
```

Open `notebooks/01_preprocessing.ipynb` → `06_robustness.ipynb` and **Run All** in each, in
order. They produce the same `outputs/` and `figures/`. (Run Step 3 first so the data path is set.)

## Optional: rebuild the deck from code

The finished `deck/OP26_deck.pptx` is already in the package, so this is optional.

```bash
npm install -g pptxgenjs      # one-time
node deck/build_deck.js       # writes deck/OP26_deck.pptx
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `FileNotFoundError` on a raw file | Step 3 path is wrong — files must be in `data_raw/` or `OP26_DATA` must point at them. Names must match exactly (see Step 0). |
| `ModuleNotFoundError` | Activate the venv (Step 2) and re-run `pip install -r requirements.txt`. |
| A number is slightly different | Re-check you ran the scripts **in order** and didn't edit `config.py`; the seed is fixed, so values should match. |
| Can't read the `.xlsx` | `openpyxl` must be installed (it's in `requirements.txt`). |
| Deck won't rebuild | Needs Node + `pptxgenjs` — but the `.pptx` is already included, so you can skip this. |

## "Working" in one sentence

`python verify.py` prints **14/14 checks passed. ALL GOOD ✓**, and the figures and the deck open
with the numbers in the table above. That's the whole project, reproduced and verified on your machine.
