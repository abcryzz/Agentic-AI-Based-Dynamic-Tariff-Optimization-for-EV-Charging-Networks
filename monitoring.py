"""
monitoring.py — Phase 5: Monitoring & Learning Agent (the feedback loop).

Closes the loop: the agent prices -> a stochastic environment returns realized demand ->
the monitor logs outcomes -> the agent updates and improves over episodes.

WHAT IT LEARNS
--------------
An epsilon-greedy contextual bandit learns, per forecast-utilization *bucket*, the tariff
multiplier that maximizes a transparent operator reward:
      reward_slot = revenue_ratio  -  W_WAIT * wait_proxy(utilization_after)
where revenue_ratio = m^(1+eps_e) (revenue vs the flat baseline) and the wait proxy is an
M/M/1-style congestion term rho/(1-rho). Exploration decays over episodes. In parallel the
monitor maintains an online elasticity estimate from the (price, demand) pairs it observes
(the "Customer Response Rate"), which converges to the true value.

THREE REQUIRED METRICS, tracked per episode (brief):
  * Average Waiting-Time Reduction   reduction in the peak wait proxy vs the flat baseline
  * Customer Response Rate           the agent's online elasticity estimate |eps_hat|
  * Pricing Efficiency Score         revenue per kWh delivered

HONEST NOTE: because demand is inelastic, a myopic reward-maximizer learns to SURGE the rare
congested slots (raising both revenue and pricing efficiency while cutting waits) and to stay
NEUTRAL elsewhere — it does not discount, since discounting inelastic off-peak demand only
loses revenue. Off-peak discounting (Phase-4 uplift) is therefore a strategic lever justified
by longer-run goals, not by this short-run objective. Reported transparently.

Outputs: monitoring_log.csv, episode_metrics.csv, learned_policy.csv,
         figures/fig15_learning_curve.png, fig16_policy_comparison.png
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C

TEAL, ORANGE, GREY, RED, BLUE, PURP = "#0F766E", "#EA7317", "#64748B", "#b91c1c", "#1d4ed8", "#7c3aed"
LO, HI = C.UTIL_DISCOUNT, C.UTIL_SURGE

# bandit state space
BUCKET_EDGES = [0.15, 0.30, 0.80, 0.90]      # -> buckets 0..4
ACTIONS = {0: [0.70, 0.80, 0.90, 1.00],       # very-low util  (discount candidates)
           1: [0.70, 0.80, 0.90, 1.00],       # low util
           2: [1.00],                          # mid (neutral, not learned)
           3: [1.00, 1.20, 1.40, 1.60],        # high util      (surge candidates)
           4: [1.00, 1.20, 1.40, 1.60]}        # very-high util
W_WAIT = 0.10
N_EPISODES, BATCH = 60, 3000
SIG_U, SIG_Q = 0.05, 0.10                       # environment noise (lognormal sd)


def wait_proxy(util):
    rho = np.clip(util, 0, 0.98)
    return rho / (1 - rho)


def bucketize(u):
    return np.digitize(np.clip(u, 0, 1), BUCKET_EDGES).astype(int)


def greedy_multiplier(u, Q):
    best = {b: ACTIONS[b][int(np.argmax([Q[(b, a)] for a in ACTIONS[b]]))] for b in ACTIONS}
    barr = bucketize(u)
    return np.array([best[b] for b in barr]), best


def evaluate(m, uo, q, p0, eps_e, eps_u):
    """Deterministic (expected) evaluation of a multiplier vector on the given slots."""
    util_after = np.clip(uo * m ** eps_u, 0, 1)
    q_real = q * m ** eps_e
    rev_dyn, rev_flat = p0 * q * m ** (1 + eps_e), p0 * q
    pk = uo >= HI
    wb, wp = wait_proxy(uo[pk]), wait_proxy(util_after[pk])
    disc = m < 1.0
    return {
        "composite_reward": float(np.mean(m ** (1 + eps_e) - W_WAIT * wait_proxy(util_after))),
        "pricing_efficiency": float(rev_dyn.sum() / q_real.sum()),
        "avg_wait_reduction_pct": float((1 - wp.mean() / wb.mean()) * 100) if pk.any() else 0.0,
        "rev_gain_pct": float((rev_dyn.sum() / rev_flat.sum() - 1) * 100),
        "offpeak_uplift_pct": float((q_real[disc].sum() / q[disc].sum() - 1) * 100) if disc.any() else 0.0,
        "peak_reduction_pp": float((uo[pk].mean() - util_after[pk].mean()) * 100) if pk.any() else 0.0,
    }


def run():
    rng = np.random.default_rng(C.RANDOM_SEED)
    panel = pd.read_csv(C.OUTPUT_DIR / "urbanev_panel_hourly.csv.gz")
    test = pd.read_csv(C.OUTPUT_DIR / "demand_predictions.csv")
    est = pd.read_csv(C.OUTPUT_DIR / "elasticity_estimates.csv")
    eps_e = est.query("target=='energy_kwh' and scope=='overall'").elasticity.iloc[0]
    eps_u = est.query("target=='utilization' and scope=='overall'").elasticity.iloc[0]
    p0_map = panel.groupby("zone")["price_mean"].mean().to_dict()
    p0_full = test.zone.map(p0_map).values

    u_all = test.util_pred.values
    uo_all = test.util_actual.values
    q_all = test.energy_actual.values
    p0a = p0_full

    Q = {(b, a): 0.0 for b in ACTIONS for a in ACTIONS[b]}
    N = {(b, a): 0 for b in ACTIONS for a in ACTIONS[b]}
    sum_lm2 = sum_lmlr = 0.0          # for online elasticity (Customer Response Rate)

    ep_rows, log_rows = [], []
    n = len(test)
    for ep in range(1, N_EPISODES + 1):
        eps = max(0.05, 0.9 * (0.90 ** (ep - 1)))     # exploration schedule
        idx = rng.integers(0, n, BATCH)
        u, uo, q, p0 = u_all[idx], uo_all[idx], q_all[idx], p0a[idx]
        bk = bucketize(u)
        train_reward = 0.0
        m_exec = np.ones(BATCH)
        for i in range(BATCH):
            b = bk[i]; acts = ACTIONS[b]
            if rng.random() < eps:
                a = acts[rng.integers(len(acts))]
            else:
                a = acts[int(np.argmax([Q[(b, aa)] for aa in acts]))]
            m_exec[i] = a
            # environment (stochastic realized response)
            nu = np.exp(rng.normal(0, SIG_U)); nq = np.exp(rng.normal(0, SIG_Q))
            util_after = min(uo[i] * a ** eps_u * nu, 1.0)
            q_real = q[i] * a ** eps_e * nq
            rev_ratio = (a * p0[i]) * q_real / max(p0[i] * q[i], 1e-9)
            r = rev_ratio - W_WAIT * wait_proxy(util_after)
            N[(b, a)] += 1
            Q[(b, a)] += (r - Q[(b, a)]) / N[(b, a)]
            train_reward += r
            if a != 1.0:                                # accumulate elasticity evidence
                lm = np.log(a); lr = np.log(max(q_real, 1e-9) / max(q[i], 1e-9))
                sum_lm2 += lm * lm; sum_lmlr += lm * lr
        eps_hat = sum_lmlr / sum_lm2 if sum_lm2 > 0 else np.nan

        # ONLINE performance of the actions actually executed this episode (improves as ε decays)
        ev = evaluate(m_exec, uo, q, p0, eps_e, eps_u)
        _, best = greedy_multiplier(u_all, Q)
        ep_rows.append({"episode": ep, "epsilon": round(eps, 3),
                        "customer_response_rate": round(abs(eps_hat), 4),
                        "eps_hat": round(eps_hat, 4), **{k: round(v, 4) for k, v in ev.items()}})
        log_rows.append({"episode": ep, "epsilon": round(eps, 3),
                         "train_reward": round(train_reward / BATCH, 4),
                         "eps_hat": round(eps_hat, 4),
                         **{f"mult_bucket{b}": best[b] for b in ACTIONS}})

    episode_metrics = pd.DataFrame(ep_rows)
    episode_metrics.to_csv(C.OUTPUT_DIR / "episode_metrics.csv", index=False)
    pd.DataFrame(log_rows).to_csv(C.OUTPUT_DIR / "monitoring_log.csv", index=False)

    # learned policy table
    m_final, best = greedy_multiplier(u_all, Q)
    names = {0: "[0,0.15) very-low", 1: "[0.15,0.30) low", 2: "[0.30,0.80) mid",
             3: "[0.80,0.90) high", 4: "[0.90,1.0] very-high"}
    learned = pd.DataFrame([{"bucket": b, "utilization_range": names[b],
                             "learned_multiplier": best[b],
                             "Q_value": round(max(Q[(b, a)] for a in ACTIONS[b]), 4)}
                            for b in ACTIONS])
    learned.to_csv(C.OUTPUT_DIR / "learned_policy.csv", index=False)

    # comparison: flat vs Phase-4 fixed vs learned
    sw = pd.read_csv(C.OUTPUT_DIR / "revenue_gain.csv")
    rec = sw[sw.is_recommended].iloc[0]
    from pricing import multiplier as p4_mult     # reuse Phase-4 policy
    comparisons = {
        "flat_baseline": np.ones(n),
        f"phase4_fixed({rec.m_min:.2f}/{rec.m_max:.2f})": p4_mult(u_all, rec.m_min, rec.m_max),
        "learned_agent": m_final,
    }
    comp = pd.DataFrame({name: evaluate(m, uo_all, q_all, p0a, eps_e, eps_u)
                         for name, m in comparisons.items()}).T

    figures(episode_metrics, learned, comp, eps_e)
    return episode_metrics, learned, comp, eps_e, eps_u


# ===========================================================================
def figures(em, learned, comp, eps_e):
    # fig15 — learning curves (2x2)
    fig, ax = plt.subplots(2, 2, figsize=(13, 9))
    a = ax[0, 0]
    a.plot(em.episode, em.composite_reward, color=TEAL, lw=2)
    a2 = a.twinx(); a2.plot(em.episode, em.epsilon, color=GREY, ls="--", lw=1)
    a2.set_ylabel("exploration ε", color=GREY)
    a.set(xlabel="Episode", ylabel="Mean reward (greedy policy)", title="Learning curve — reward")
    ax[0, 1].plot(em.episode, em.pricing_efficiency, color=ORANGE, lw=2)
    ax[0, 1].set(xlabel="Episode", ylabel="Revenue per kWh (CNY)", title="Pricing efficiency score")
    ax[1, 0].plot(em.episode, em.avg_wait_reduction_pct, color=BLUE, lw=2)
    ax[1, 0].set(xlabel="Episode", ylabel="% reduction", title="Avg waiting-time reduction (peak, proxy)")
    ax[1, 1].plot(em.episode, em.customer_response_rate, color=PURP, lw=2, label="estimate |ε̂|")
    ax[1, 1].axhline(abs(eps_e), ls="--", color=GREY, label=f"true |ε| = {abs(eps_e):.2f}")
    ax[1, 1].set(xlabel="Episode", ylabel="|elasticity|", title="Customer response rate (online elasticity)")
    ax[1, 1].legend(fontsize=9)
    fig.suptitle("Monitoring & Learning Agent — feedback loop over episodes", fontweight="bold")
    fig.text(0.5, -0.01, "→ As exploration decays the agent converges: reward, pricing efficiency and "
             "peak wait-reduction rise and stabilise; the elasticity estimate locks onto the true value.",
             ha="center", style="italic", color=GREY, fontsize=10)
    fig.tight_layout(rect=[0, 0.02, 1, 0.97])
    fig.savefig(C.FIG_DIR / "fig15_learning_curve.png")
    plt.close(fig)

    # fig16 — policy comparison + learned multipliers
    fig, ax = plt.subplots(1, 2, figsize=(14, 5.4))
    met = ["rev_gain_pct", "avg_wait_reduction_pct", "peak_reduction_pp"]
    lab = ["Revenue gain %", "Wait reduction %\n(peak)", "Peak util\nreduction (pp)"]
    x = np.arange(len(met)); w = 0.26
    cols = {0: GREY, 1: ORANGE, 2: TEAL}
    for j, (name, row) in enumerate(comp.iterrows()):
        ax[0].bar(x + (j - 1) * w, [row[m] for m in met], w, label=name, color=list(cols.values())[j])
    ax[0].set_xticks(x); ax[0].set_xticklabels(lab, fontsize=9)
    ax[0].axhline(0, color="#111", lw=.8)
    ax[0].set(ylabel="value", title="Policy comparison (flat vs Phase-4 fixed vs learned)")
    ax[0].legend(fontsize=8)
    lc = learned[learned.bucket != 2]
    bcol = [TEAL if m < 1 else (ORANGE if m > 1 else GREY) for m in lc.learned_multiplier]
    ax[1].bar(lc.utilization_range, lc.learned_multiplier, color=bcol)
    ax[1].axhline(1, ls=":", color=GREY)
    ax[1].set(ylabel="learned multiplier ×", title="Learned multiplier by utilization bucket")
    ax[1].tick_params(axis="x", rotation=20, labelsize=8)
    fig.text(0.5, -0.02, "→ The agent learns to surge congested buckets and stay neutral elsewhere — "
             "revenue-improving and wait-reducing; it does not discount (myopically unprofitable).",
             ha="center", style="italic", color=GREY, fontsize=10)
    fig.savefig(C.FIG_DIR / "fig16_policy_comparison.png")
    plt.close(fig)


def main():
    print("=" * 64, "\nPHASE 5  — Monitoring & Learning Agent\n", "=" * 64, sep="")
    em, learned, comp, eps_e, eps_u = run()
    first, last = em.iloc[0], em.iloc[-1]
    print(f"Episodes: {len(em)} | environment noise σ_u={SIG_U}, σ_q={SIG_Q} | true ε_energy {eps_e:+.3f}")
    print("\nLearning (first → last episode):")
    print(f"  composite reward     : {first.composite_reward:+.3f} → {last.composite_reward:+.3f}")
    print(f"  pricing efficiency   : {first.pricing_efficiency:.3f} → {last.pricing_efficiency:.3f} CNY/kWh")
    print(f"  avg wait reduction % : {first.avg_wait_reduction_pct:+.2f} → {last.avg_wait_reduction_pct:+.2f}")
    print(f"  customer response |ε̂|: {first.customer_response_rate:.3f} → {last.customer_response_rate:.3f}  (true {abs(eps_e):.3f})")
    print("\nLearned policy by utilization bucket:")
    for _, r in learned.iterrows():
        print(f"  {r.utilization_range:24} → ×{r.learned_multiplier:.2f}")
    print("\nFinal policy comparison (full test set):")
    print(comp[["rev_gain_pct", "avg_wait_reduction_pct", "peak_reduction_pp",
                "pricing_efficiency", "offpeak_uplift_pct"]].round(3).to_string())
    print("\n[outputs] episode_metrics.csv, monitoring_log.csv, learned_policy.csv")
    print("[figures] fig15_learning_curve.png, fig16_policy_comparison.png")


if __name__ == "__main__":
    main()
