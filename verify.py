"""
verify.py — physical self-test of the OP26 pipeline outputs.

Run AFTER the pipeline (preprocess → eda → demand → pricing → monitoring → robustness):

    python verify.py

It re-loads the generated files and checks shapes, value ranges, the energy
reconciliation, and the headline metrics, printing PASS/FAIL for each. Exit code is
0 if everything passes, 1 otherwise — so you can use it in CI or a quick gate.

It does NOT recompute models; it audits what the pipeline wrote. Needs the raw data
on hand (via OP26_DATA or ./data_raw) only for the energy-reconciliation check.
"""
from __future__ import annotations
import sys
import numpy as np
import pandas as pd
import config as C

OUT = C.OUTPUT_DIR
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def near(x, target, tol):
    return abs(float(x) - target) <= tol


print("=" * 70, "\nOP26 — output self-test\n", "=" * 70, sep="")

# ---- files exist ----------------------------------------------------------
need = ["clean_acn_sessions.csv", "urbanev_panel_hourly.csv.gz", "zone_features.csv",
        "peak_windows.csv", "eda_findings.md", "demand_predictions.csv", "demand_metrics.csv",
        "elasticity_estimates.csv", "pricing_policy.csv", "revenue_gain.csv",
        "episode_metrics.csv", "learned_policy.csv", "implications.md"]
missing = [f for f in need if not (OUT / f).exists()]
check("all expected output files present", not missing,
      "missing: " + ", ".join(missing) if missing else f"{len(need)} files")
if missing:
    print("\nRun the pipeline first (preprocess → … → robustness). Aborting.")
    sys.exit(1)

# ---- Phase 1: panel + ACN -------------------------------------------------
panel = pd.read_csv(OUT / "urbanev_panel_hourly.csv.gz")
check("panel shape == 177,840 × 42", panel.shape == (177840, 42), str(panel.shape))
check("utilization within [0, 1]", panel.utilization.between(0, 1).all(),
      f"min {panel.utilization.min():.3f}, max {panel.utilization.max():.3f}")
acn = pd.read_csv(OUT / "clean_acn_sessions.csv")
check("ACN clean sessions ≈ 14,947", near(len(acn), 14947, 50), f"{len(acn):,} rows")

# ---- energy reconciliation (needs raw volume.csv) -------------------------
vol_path = C.DATA_DIR / C.F_VOLUME
if vol_path.exists():
    raw = pd.read_csv(vol_path).iloc[:, 1:].to_numpy(float).sum()
    check("hourly panel energy reconciles to raw 5-min sum",
          near(raw, panel.energy_kwh.sum(), 1.0),
          f"raw {raw:,.0f} vs panel {panel.energy_kwh.sum():,.0f}")
else:
    print(f"  [SKIP] energy reconciliation — raw data not found at {vol_path}")

# ---- Phase 3: demand metrics ----------------------------------------------
dm = pd.read_csv(OUT / "demand_metrics.csv")
def metric(target, model, m):
    r = dm[(dm.target == target) & (dm.model == model) & (dm.metric == m)]
    return float(r.value.iloc[0]) if len(r) else np.nan
util_r2 = metric("utilization", "GBM", "R2")
util_rmse = metric("utilization", "GBM", "RMSE")
auc = metric("congestion", "GBM", "ROC_AUC")
check("utilization GBM R² > 0.90", util_r2 > 0.90, f"R² = {util_r2:.3f}")
check("utilization GBM RMSE < 0.05", util_rmse < 0.05, f"RMSE = {util_rmse:.4f}")
check("GBM beats persistence (RMSE)", util_rmse < metric("utilization", "persistence_1h", "RMSE"),
      f"{util_rmse:.4f} < {metric('utilization','persistence_1h','RMSE'):.4f}")
check("congestion AUC > 0.95", auc > 0.95, f"AUC = {auc:.3f}")

# ---- Phase 4: elasticity + pricing ---------------------------------------
est = pd.read_csv(OUT / "elasticity_estimates.csv")
eps = est.query("target=='energy_kwh' and scope=='overall'").elasticity.iloc[0]
check("energy elasticity is negative & inelastic (−0.5 < ε < −0.2)", -0.5 < eps < -0.2,
      f"ε = {eps:+.3f}")
sw = pd.read_csv(OUT / "revenue_gain.csv")
check("revenue_gain has exactly one recommended policy", int(sw.is_recommended.sum()) == 1,
      f"{int(sw.is_recommended.sum())} flagged")
rec = sw[sw.is_recommended].iloc[0]
check("recommended policy is ~revenue-neutral (|gain| < 1.5%)", abs(rec.rev_gain_pct) < 1.5,
      f"{rec.rev_gain_pct:+.2f}% (discount {rec.m_min}× / surge {rec.m_max}×)")

# ---- Phase 5: learning improved ------------------------------------------
em = pd.read_csv(OUT / "episode_metrics.csv")
better = em.avg_wait_reduction_pct.iloc[-1] > em.avg_wait_reduction_pct.iloc[0]
check("monitoring loop improved over episodes (wait-reduction up)", better,
      f"{em.avg_wait_reduction_pct.iloc[0]:.1f}% → {em.avg_wait_reduction_pct.iloc[-1]:.1f}%")
conv = near(em.customer_response_rate.iloc[-1], abs(eps), 0.05)
check("online elasticity estimate converged near true value", conv,
      f"|ε̂| {em.customer_response_rate.iloc[-1]:.3f} vs true {abs(eps):.3f}")

# ---- summary --------------------------------------------------------------
n_pass, n = sum(results), len(results)
print("-" * 70)
print(f"{n_pass}/{n} checks passed.", "ALL GOOD ✓" if n_pass == n else "SOME CHECKS FAILED ✗")
sys.exit(0 if n_pass == n else 1)
