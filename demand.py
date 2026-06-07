"""
demand.py — Phase 3: Demand Prediction Agent.

Forecasts, one hour ahead, per zone:
  * utilization rate        (primary regression target)
  * expected charging load  (energy_kwh, regression)
  * congestion probability  P(utilization >= 0.80) (classification)

Design (leakage-safe): the target is the value at hour t; every feature is either
strictly pre-t (lags / rolling) or deterministic for t (calendar / static zone
attributes). Contemporaneous outcomes (occupancy, energy, revenue, price, saturation at t)
are NEVER used as features. Validation is a strict TIME-BASED split (no shuffling); the
test window is the final 4 days, untouched during training.

Gradient boosting = sklearn HistGradientBoosting (same histogram-based GBM family as
LightGBM; chosen because it is available offline and supports native categoricals).

Outputs:
  outputs/demand_predictions.csv       test-set actual vs predicted (+ baselines, congestion prob)
  outputs/demand_metrics.csv           RMSE/MAE/R2 (utilization, energy) + AUC/AP/Brier (congestion), model vs baselines
  outputs/demand_metrics_by_zone.csv   per-zone utilization metrics for the GBM
  outputs/feature_importance.csv       permutation importance (utilization model)
  outputs/demand_model_*.joblib        fitted models
  figures/fig09_demand_pred.png, fig10_feature_importance.png, fig11_congestion_roc.png
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.metrics import (mean_squared_error, mean_absolute_error, r2_score,
                             roc_auc_score, average_precision_score, brier_score_loss,
                             roc_curve)
from sklearn.inspection import permutation_importance

import config as C

TEAL, ORANGE, GREY, RED = "#0F766E", "#EA7317", "#64748B", "#b91c1c"
TEST_START = 624          # final 96 hours (4 days) -> test; warm-up (<168) dropped
WARMUP_END = 168

LAG = ["util_lag1", "util_lag2", "util_lag3", "util_lag24", "util_lag168",
       "energy_lag1", "energy_lag2", "energy_lag3", "energy_lag24", "energy_lag168"]
ROLL = ["util_roll3_mean", "util_roll3_std", "util_roll24_mean"]
CAL = ["hour", "dayofweek", "is_weekend", "hour_sin", "hour_cos", "dow_sin", "dow_cos"]
ZONE_STATIC = ["capacity", "area", "CBD", "dynamic_pricing", "fast_count", "slow_count"]
FEATURES = LAG + ROLL + CAL + ZONE_STATIC + ["zone"]


def _prep(frame):
    X = frame[FEATURES].copy()
    X["is_weekend"] = X["is_weekend"].astype(int)
    X["zone"] = X["zone"].astype("category")
    return X


def _reg():
    return HistGradientBoostingRegressor(
        loss="squared_error", max_iter=400, learning_rate=0.05, max_leaf_nodes=63,
        min_samples_leaf=50, l2_regularization=1.0, categorical_features=["zone"],
        random_state=C.RANDOM_SEED)


def _metrics_reg(y, p):
    return {"RMSE": float(mean_squared_error(y, p) ** 0.5),
            "MAE": float(mean_absolute_error(y, p)),
            "R2": float(r2_score(y, p))}


def load_split():
    panel = pd.read_csv(C.OUTPUT_DIR / "urbanev_panel_hourly.csv.gz")
    df = panel[panel.has_full_lags].copy()                      # hour_index >= 168
    df = df.dropna(subset=[c for c in FEATURES if c != "zone"])
    train = df[df.hour_index < TEST_START].copy()
    test = df[df.hour_index >= TEST_START].copy()
    return train, test


def run():
    train, test = load_split()
    Xtr, Xte = _prep(train), _prep(test)
    rows = []   # tidy metrics

    # ---- 1) utilization regression ---------------------------------------
    reg = _reg().fit(Xtr, train.utilization)
    util_pred = np.clip(reg.predict(Xte), 0, 1)
    for m, v in _metrics_reg(test.utilization, util_pred).items():
        rows.append(("utilization", "GBM", m, v))

    # baselines on the same test rows
    clim = train.groupby(["zone", "hour"])["utilization"].mean()
    gm = train.utilization.mean()
    clim_pred = (test[["zone", "hour"]].merge(clim.rename("c"), left_on=["zone", "hour"],
                 right_index=True, how="left")["c"].fillna(gm).values)
    baselines = {"persistence_1h": test.util_lag1.values,
                 "seasonal_daily": test.util_lag24.values,
                 "seasonal_weekly": test.util_lag168.values,
                 "climatology": clim_pred}
    for name, pred in baselines.items():
        for m, v in _metrics_reg(test.utilization, np.clip(pred, 0, 1)).items():
            rows.append(("utilization", name, m, v))

    # per-zone metrics for the GBM
    tz = test.assign(pred=util_pred)
    by_zone = (tz.groupby("zone").apply(
        lambda d: pd.Series({"RMSE": mean_squared_error(d.utilization, d.pred) ** 0.5,
                             "MAE": mean_absolute_error(d.utilization, d.pred),
                             "R2": r2_score(d.utilization, d.pred) if d.utilization.nunique() > 1 else np.nan,
                             "n": len(d), "util_mean": d.utilization.mean()}),
        include_groups=False).reset_index())
    by_zone.round(4).to_csv(C.OUTPUT_DIR / "demand_metrics_by_zone.csv", index=False)

    # ---- 2) expected load (energy) regression, log target ----------------
    ereg = _reg().fit(Xtr, np.log1p(train.energy_kwh))
    energy_pred = np.clip(np.expm1(ereg.predict(Xte)), 0, None)
    for m, v in _metrics_reg(test.energy_kwh, energy_pred).items():
        rows.append(("energy_kwh", "GBM", m, v))
    e_persist = test.energy_lag1.values
    for m, v in _metrics_reg(test.energy_kwh, np.clip(e_persist, 0, None)).items():
        rows.append(("energy_kwh", "persistence_1h", m, v))

    # ---- 3) congestion probability classification ------------------------
    ytr_c = (train.utilization >= C.UTIL_SURGE).astype(int)
    yte_c = (test.utilization >= C.UTIL_SURGE).astype(int)
    clf = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=50,
        l2_regularization=1.0, categorical_features=["zone"],
        class_weight="balanced", random_state=C.RANDOM_SEED).fit(Xtr, ytr_c)
    cong_prob = clf.predict_proba(Xte)[:, 1]
    rows.append(("congestion", "GBM", "ROC_AUC", float(roc_auc_score(yte_c, cong_prob))))
    rows.append(("congestion", "GBM", "avg_precision", float(average_precision_score(yte_c, cong_prob))))
    rows.append(("congestion", "GBM", "Brier", float(brier_score_loss(yte_c, cong_prob))))
    rows.append(("congestion", "GBM", "base_rate", float(yte_c.mean())))
    # baseline: historical congestion rate per zone-hour
    crate = ytr_c.groupby([train.zone, train.hour]).mean()
    cbase = (test[["zone", "hour"]].merge(crate.rename("c"), left_on=["zone", "hour"],
             right_index=True, how="left")["c"].fillna(ytr_c.mean()).values)
    rows.append(("congestion", "climatology", "ROC_AUC", float(roc_auc_score(yte_c, cbase))))
    rows.append(("congestion", "climatology", "avg_precision", float(average_precision_score(yte_c, cbase))))

    metrics = pd.DataFrame(rows, columns=["target", "model", "metric", "value"]).round(5)
    metrics.to_csv(C.OUTPUT_DIR / "demand_metrics.csv", index=False)

    # ---- predictions deliverable -----------------------------------------
    preds = pd.DataFrame({
        "zone": test.zone.values, "hour_index": test.hour_index.values,
        "timestamp": test.timestamp.values,
        "util_actual": test.utilization.values, "util_pred": util_pred,
        "pred_persistence": baselines["persistence_1h"],
        "pred_seasonal_weekly": baselines["seasonal_weekly"],
        "pred_climatology": clim_pred,
        "energy_actual": test.energy_kwh.values, "energy_pred": energy_pred,
        "congestion_actual": yte_c.values, "congestion_prob": cong_prob,
    }).round(5)
    preds.to_csv(C.OUTPUT_DIR / "demand_predictions.csv", index=False)

    # ---- feature importance (permutation on utilization model) -----------
    sub = test.sample(min(8000, len(test)), random_state=C.RANDOM_SEED)
    pim = permutation_importance(reg, _prep(sub), sub.utilization, n_repeats=5,
                                 random_state=C.RANDOM_SEED,
                                 scoring="neg_root_mean_squared_error")
    fi = (pd.DataFrame({"feature": FEATURES, "importance": pim.importances_mean,
                        "std": pim.importances_std})
          .sort_values("importance", ascending=False).round(5))
    fi.to_csv(C.OUTPUT_DIR / "feature_importance.csv", index=False)

    # ---- persist models ---------------------------------------------------
    joblib.dump(reg, C.OUTPUT_DIR / "demand_model_utilization.joblib")
    joblib.dump(ereg, C.OUTPUT_DIR / "demand_model_energy.joblib")
    joblib.dump(clf, C.OUTPUT_DIR / "demand_model_congestion.joblib")

    figures(metrics, preds, fi, yte_c, cong_prob, by_zone)
    return metrics, preds, fi, by_zone


# ===========================================================================
def figures(metrics, preds, fi, yte_c, cong_prob, by_zone):
    # fig09: model vs baselines RMSE + sample-zone forecast overlay
    ru = metrics[(metrics.target == "utilization") & (metrics.metric == "RMSE")] \
        .set_index("model")["value"].sort_values()
    fig, ax = plt.subplots(1, 2, figsize=(14, 5.2))
    colors = [TEAL if m == "GBM" else GREY for m in ru.index]
    ax[0].bar(ru.index, ru.values, color=colors)
    for i, v in enumerate(ru.values):
        ax[0].text(i, v + .001, f"{v:.3f}", ha="center", fontsize=9)
    ax[0].set(ylabel="Test RMSE (utilization)", title="GBM vs baselines (lower = better)")
    ax[0].tick_params(axis="x", rotation=25)

    # busiest test zone forecast overlay
    z = by_zone.sort_values("util_mean", ascending=False).iloc[0]["zone"]
    d = preds[preds.zone == z].sort_values("hour_index")
    ax[1].plot(range(len(d)), d.util_actual, "-o", color=GREY, ms=3, label="Actual")
    ax[1].plot(range(len(d)), d.util_pred, "-", color=TEAL, lw=2, label="GBM forecast")
    ax[1].axhline(C.UTIL_SURGE, ls="--", color=RED, lw=1)
    ax[1].set(xlabel="Test hour", ylabel="Utilization",
              title=f"1-hour-ahead forecast — busiest test zone ({int(z)})")
    ax[1].legend(fontsize=9)
    fig.text(0.5, -0.02, "→ The demand agent tracks the daily cycle and anticipates the surge "
             "line — the input the tariff agent needs.", ha="center", style="italic",
             color=GREY, fontsize=10)
    fig.savefig(C.FIG_DIR / "fig09_demand_pred.png")
    plt.close(fig)

    # fig10: feature importance
    top = fi.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.barh(top.feature, top.importance, xerr=top["std"], color=TEAL)
    ax.set(xlabel="Permutation importance (Δ RMSE)", title="Top 15 features — utilization model")
    fig.text(0.5, -0.02, "→ Recent lags + daily/weekly seasonality dominate; demand is highly "
             "predictable, validating a forecast-driven tariff.", ha="center", style="italic",
             color=GREY, fontsize=10)
    fig.savefig(C.FIG_DIR / "fig10_feature_importance.png")
    plt.close(fig)

    # fig11: congestion ROC
    fpr, tpr, _ = roc_curve(yte_c, cong_prob)
    auc = roc_auc_score(yte_c, cong_prob)
    fig, ax = plt.subplots(figsize=(6.5, 6))
    ax.plot(fpr, tpr, color=ORANGE, lw=2.5, label=f"GBM (AUC = {auc:.2f})")
    ax.plot([0, 1], [0, 1], ls="--", color=GREY, label="Chance")
    ax.set(xlabel="False positive rate", ylabel="True positive rate",
           title=f"Congestion detection ROC  (base rate {yte_c.mean():.1%})")
    ax.legend(loc="lower right")
    fig.text(0.5, -0.02, "→ Reliable early warning of the rare >80% events that should trigger surge.",
             ha="center", style="italic", color=GREY, fontsize=10)
    fig.savefig(C.FIG_DIR / "fig11_congestion_roc.png")
    plt.close(fig)


def main():
    print("=" * 64, "\nPHASE 3  — Demand Prediction Agent\n", "=" * 64, sep="")
    metrics, preds, fi, by_zone = run()

    def show(target, metric):
        s = metrics[(metrics.target == target) & (metrics.metric == metric)] \
            .set_index("model")["value"]
        return s

    ru = show("utilization", "RMSE").sort_values()
    print(f"\nTrain/test split: warm-up<{WARMUP_END}h dropped; test = hour_index >= {TEST_START} "
          f"(final {720-TEST_START}h / 4 days). Test rows: {len(preds):,}")
    print("\nUtilization — test RMSE (lower better):")
    for m, v in ru.items():
        tag = "  <-- GBM" if m == "GBM" else ""
        print(f"   {m:18} {v:.4f}{tag}")
    gbm = ru["GBM"]; best_base = ru.drop("GBM").min(); base_name = ru.drop("GBM").idxmin()
    print(f"   GBM improves on best baseline ({base_name}) by {(best_base-gbm)/best_base*100:.1f}%")
    print("Utilization R2 (GBM):", round(show("utilization", "R2")["GBM"], 3),
          "| MAE:", round(show("utilization", "MAE")["GBM"], 4))
    print("Energy load  R2 (GBM):", round(show("energy_kwh", "R2")["GBM"], 3),
          "| RMSE:", round(show("energy_kwh", "RMSE")["GBM"], 1), "kWh")
    print("Congestion   AUC (GBM):", round(show("congestion", "ROC_AUC")["GBM"], 3),
          "| avg-precision:", round(show("congestion", "avg_precision")["GBM"], 3),
          "| base rate:", round(show("congestion", "base_rate")["GBM"], 4))
    print("\nTop 5 features:", ", ".join(fi.head(5).feature))
    print("[outputs] demand_predictions.csv, demand_metrics.csv, demand_metrics_by_zone.csv, "
          "feature_importance.csv, demand_model_*.joblib")
    print("[figures] fig09_demand_pred.png, fig10_feature_importance.png, fig11_congestion_roc.png")


if __name__ == "__main__":
    main()
