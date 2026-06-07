/* OP26 deck — Agentic Dynamic Tariff Optimization for EV Charging Networks */
const pptxgen = require("pptxgenjs");
const dims = require("./fig_dims.json");

const INK="0B2B2E", INK2="12393C", TEAL="0F766E", TEALD="0B5A53", AMBER="EA7317",
      GREY="64748B", WHITE="FFFFFF", ICE="CFE9E6", TINT="F0FDFA", TINT2="FFF7ED",
      BODYC="1F2937", BORDER="D9E6E4";
const HEAD="Trebuchet MS", BODY="Calibri";

const p = new pptxgen();
p.layout = "LAYOUT_WIDE";              // 13.33 x 7.5
p.author = "OP26"; p.title = "Agentic Dynamic Tariff Optimization for EV Charging Networks";
const W = 13.33;
const sh = () => ({ type:"outer", color:"0B2B2E", blur:7, offset:3, angle:135, opacity:0.12 });

function header(s, kick, title){
  s.addText(kick, {x:0.55, y:0.34, w:12, h:0.3, fontSize:12, bold:true, color:AMBER,
    fontFace:HEAD, charSpacing:2, margin:0});
  s.addText(title, {x:0.5, y:0.62, w:12.3, h:0.72, fontSize:29, bold:true, color:TEALD,
    fontFace:HEAD, margin:0});
}
function footer(s, n){
  s.addText("OP26 · Agentic Dynamic Tariff Optimization for EV Charging Networks",
    {x:0.5, y:7.06, w:10, h:0.3, fontSize:9, color:GREY, fontFace:BODY, margin:0});
  s.addText(String(n), {x:12.4, y:7.06, w:0.5, h:0.3, fontSize:9, color:GREY, align:"right",
    fontFace:BODY, margin:0});
}
function fit(file, maxW, maxH){
  const [pw,ph]=dims[file]; const r=pw/ph; let w=maxW, h=w/r;
  if(h>maxH){ h=maxH; w=h*r; } return {w,h};
}
function fig(s, file, bx, by, bw, bh, frame=true){
  const {w,h}=fit(file, bw, bh); const x=bx+(bw-w)/2, y=by+(bh-h)/2;
  if(frame) s.addShape(p.shapes.RECTANGLE, {x, y, w, h, fill:{color:WHITE},
    line:{color:BORDER, width:1}, shadow:sh()});
  s.addImage({path:`figures/${file}`, x, y, w, h});
}
function stat(s, x, y, w, h, num, label, col){
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {x, y, w, h, fill:{color:TINT},
    line:{color:BORDER, width:1}, rectRadius:0.07, shadow:sh()});
  s.addText(num, {x, y:y+0.10, w, h:h*0.52, align:"center", valign:"middle",
    fontSize:27, bold:true, color:col, fontFace:HEAD, margin:0});
  s.addText(label, {x:x+0.08, y:y+h*0.56, w:w-0.16, h:h*0.4, align:"center", valign:"top",
    fontSize:10.5, color:GREY, fontFace:BODY, margin:0});
}
function card(s, x, y, w, h, head, body, accent){
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {x, y, w, h, fill:{color:TINT},
    line:{color:BORDER, width:1}, rectRadius:0.06, shadow:sh()});
  s.addShape(p.shapes.OVAL, {x:x+0.22, y:y+0.26, w:0.16, h:0.16, fill:{color:accent}});
  s.addText(head, {x:x+0.5, y:y+0.16, w:w-0.7, h:0.34, fontSize:14.5, bold:true,
    color:TEALD, fontFace:HEAD, margin:0, valign:"middle"});
  s.addText(body, {x:x+0.5, y:y+0.52, w:w-0.7, h:h-0.66, fontSize:12, color:BODYC,
    fontFace:BODY, margin:0, valign:"top"});
}
const bullets = (arr) => arr.map((t,i)=>({text:t, options:{bullet:{indent:14}, breakLine:true,
  paraSpaceAfter:7, color:BODYC, fontSize:13, fontFace:BODY}}));

/* ---------------- 1. COVER (dark) ---------------- */
let s = p.addSlide(); s.background = {color:INK};
s.addText("OPEN PROJECT 2026  ·  SOCIETY OF BUSINESS",
  {x:0.7, y:1.05, w:12, h:0.4, fontSize:14, bold:true, color:AMBER, fontFace:HEAD, charSpacing:3, margin:0});
s.addText("Agentic Dynamic Tariff Optimization\nfor EV Charging Networks",
  {x:0.66, y:1.7, w:12, h:2.0, fontSize:44, bold:true, color:WHITE, fontFace:HEAD, lineSpacingMultiple:1.02, margin:0});
s.addText("A self-improving pricing engine on large-scale charging data: forecast demand → set dynamic tariffs → learn from outcomes.",
  {x:0.7, y:3.75, w:11.4, h:0.7, fontSize:16, italic:true, color:ICE, fontFace:BODY, margin:0});
const chips=[["247 zones × 30 days","5-min UrbanEV panel + 15k ACN sessions"],
  ["3 agents","Demand · Tariff · Monitoring & Learning"],
  ["R² 0.96 · AUC 0.99","forecast accuracy on held-out test"]];
chips.forEach((c,i)=>{ const x=0.7+i*4.0;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {x, y:5.05, w:3.7, h:1.25, fill:{color:INK2},
    line:{color:TEAL, width:1}, rectRadius:0.08});
  s.addText(c[0], {x:x+0.05, y:5.2, w:3.6, h:0.55, align:"center", fontSize:21, bold:true,
    color:WHITE, fontFace:HEAD, margin:0});
  s.addText(c[1], {x:x+0.15, y:5.75, w:3.4, h:0.45, align:"center", fontSize:10.5,
    color:ICE, fontFace:BODY, margin:0}); });
s.addText("Datasets: UrbanEV / ST-EVCDP (Shenzhen)  ·  ACN-Data (Caltech)",
  {x:0.7, y:6.7, w:12, h:0.3, fontSize:10.5, color:GREY, fontFace:BODY, margin:0});

/* ---------------- 2. EXECUTIVE SUMMARY ---------------- */
s = p.addSlide(); s.background={color:WHITE};
header(s, "EXECUTIVE SUMMARY", "What we built — and what the data says");
s.addText("We turn two real charging datasets into a unified panel and an agentic pricing stack:",
  {x:0.55, y:1.55, w:6.0, h:0.5, fontSize:13.5, color:BODYC, fontFace:BODY, margin:0});
s.addText(bullets([
  "Demand agent — forecasts utilization, load & congestion one hour ahead.",
  "Tariff agent — turns forecasts into bounded surge/discount tariffs.",
  "Monitoring & learning agent — measures each decision and adapts online."]),
  {x:0.6, y:2.05, w:5.9, h:1.8});
// 2x2 stat grid (right)
stat(s, 6.95, 1.6, 2.95, 1.45, "R² 0.96", "1-h utilization forecast (R² 0.971 load)", TEAL);
stat(s, 10.1, 1.6, 2.95, 1.45, "AUC 0.99", "congestion P(util≥0.8), 0.97% base rate", TEAL);
stat(s, 6.95, 3.2, 2.95, 1.45, "ε = −0.32", "demand is inelastic (controlled estimate)", AMBER);
stat(s, 10.1, 3.2, 2.95, 1.45, "+5.85 pp", "peak relief from the learned policy", AMBER);
// bottom line band
s.addShape(p.shapes.ROUNDED_RECTANGLE, {x:0.55, y:5.45, w:12.25, h:1.25, fill:{color:TINT2},
  line:{color:"F4C28A", width:1}, rectRadius:0.07, shadow:sh()});
s.addText("BOTTOM LINE", {x:0.8, y:5.62, w:3, h:0.3, fontSize:12, bold:true, color:AMBER,
  fontFace:HEAD, charSpacing:2, margin:0});
s.addText("Because demand is inelastic, dynamic pricing here is a load-balancing tool, not a revenue lever — it cuts the peak wait proxy ~57% and improves pricing efficiency while holding revenue flat. Off-peak discounting is a strategic lever, not a short-run win.",
  {x:0.8, y:5.92, w:11.8, h:0.7, fontSize:13.5, color:BODYC, fontFace:BODY, margin:0});
footer(s,2);

/* ---------------- 3. DATA LANDSCAPE ---------------- */
s = p.addSlide(); s.background={color:WHITE};
header(s, "DATA LANDSCAPE & PREPROCESSING", "Two datasets, two jobs — kept deliberately separate");
card(s, 0.55, 1.6, 6.05, 1.5, "UrbanEV / ST-EVCDP — Shenzhen  (the engine)",
  "247 zones × 8,640 five-minute steps (30 days). Occupancy, energy, duration & price (CNY/kWh), zero missing; spatial graph + zone metadata. Drives forecasting, pricing & monitoring.", TEAL);
card(s, 0.55, 3.25, 6.05, 1.5, "ACN-Data — Caltech  (behaviour)",
  "14,947 cleaned sessions, 54 stations, 204 users. Dwell, charging, idle/overstay, laxity. No price field → used for behaviour & sanity checks, not revenue.", AMBER);
fig(s, "fig05_spatial_map.png", 6.85, 1.55, 6.0, 3.3);
s.addText(bullets([
  "Utilization = clip(occupancy / installed piles, 0–1); revenue computed at 5-min then summed (exact).",
  "Queue/wait is a saturation proxy — queues are never directly observed.",
  "UrbanEV complete (no imputation); ACN flags carried, not imputed; datasets never fused (geography/units differ)."]),
  {x:0.6, y:5.0, w:12.2, h:1.7});
footer(s,3);

/* ---------------- 4. EDA ---------------- */
s = p.addSlide(); s.background={color:WHITE};
header(s, "EXPLORATORY DATA ANALYSIS", "Time-of-day demand — chronically under-used");
fig(s, "fig01_intraday_utilization.png", 6.5, 1.7, 6.4, 4.9);
card(s, 0.55, 1.6, 5.6, 1.55, "Chronically under-used",
  "Only 0.9% of zone-hours exceed the 80% surge line; 61% sit below 30% → a discount-led network.", TEAL);
card(s, 0.55, 3.3, 5.6, 1.55, "Time-of-day, not day-of-week",
  "Occupancy peaks overnight, troughs midday; weekday ≈ weekend (0.279 vs 0.283). Discount window is daytime.", AMBER);
card(s, 0.55, 5.0, 5.6, 1.55, "Congestion is concentrated — not the CBD",
  "Top ~10% of zones ≈ all surge incidence; CBD zones are actually less utilized → surge by observed load, not label.", TEAL);
footer(s,4);

/* ---------------- 5. DEMAND AGENT ---------------- */
s = p.addSlide(); s.background={color:WHITE};
header(s, "AGENT 1 · DEMAND PREDICTION", "Forecasting utilization, load & congestion");
fig(s, "fig09_demand_pred.png", 6.45, 1.95, 6.45, 3.4);
stat(s, 0.55, 1.6, 1.95, 1.4, "R² 0.96", "utilization", TEAL);
stat(s, 2.62, 1.6, 1.95, 1.4, "R² 0.97", "energy load", TEAL);
stat(s, 4.69, 1.6, 1.95, 1.4, "AUC 0.99", "congestion", AMBER);
s.addText(bullets([
  "Gradient boosting (sklearn HistGBM) vs strong baselines; strict time-based split, no leakage.",
  "Beats 1-hour persistence by 32% on RMSE (0.036 vs 0.052); per-zone median R² 0.89.",
  "Top features: recent lags + the weekly lag + zone identity — the seasonality EDA predicted.",
  "Outputs forecast utilization + congestion probability per zone-hour → feeds the tariff agent."]),
  {x:0.6, y:3.25, w:5.7, h:3.4});
footer(s,5);

/* ---------------- 6. TARIFF AGENT ---------------- */
s = p.addSlide(); s.background={color:WHITE};
header(s, "AGENT 2 · TARIFF PRICING", "Dynamic tariffs — and an honest revenue finding");
fig(s, "fig13_policy_frontier.png", 6.7, 1.95, 6.2, 3.5);
// finding callout
s.addShape(p.shapes.ROUNDED_RECTANGLE, {x:0.55, y:1.6, w:6.0, h:1.45, fill:{color:TINT2},
  line:{color:"F4C28A", width:1}, rectRadius:0.07, shadow:sh()});
s.addText("KEY FINDING", {x:0.78, y:1.74, w:3, h:0.3, fontSize:11.5, bold:true, color:AMBER,
  fontFace:HEAD, charSpacing:2, margin:0});
s.addText("Demand is inelastic (ε = −0.32). Off-peak holds ~22% of energy vs ~3% in surge slots, so dynamic pricing cannot grow revenue here — best case is revenue-neutral.",
  {x:0.78, y:2.04, w:5.6, h:0.95, fontSize:12.5, color:BODYC, fontFace:BODY, margin:0});
s.addText(bullets([
  "Policy: surge ramp when forecast util ≥ 80%, discount ramp < 30%, neutral between — bounded & transparent.",
  "Value is operational load-shifting, not revenue; we map the full revenue↔uplift↔congestion frontier."]),
  {x:0.6, y:3.2, w:5.95, h:1.4});
stat(s, 0.55, 4.75, 1.95, 1.35, "−0.26%", "revenue (≈ neutral)", TEAL);
stat(s, 2.62, 4.75, 1.95, 1.35, "+0.81%", "off-peak uplift", AMBER);
stat(s, 4.69, 4.75, 1.95, 1.35, "+2.52 pp", "peak relief", TEAL);
footer(s,6);

/* ---------------- 7. MONITORING & LEARNING ---------------- */
s = p.addSlide(); s.background={color:WHITE};
header(s, "AGENT 3 · MONITORING & LEARNING", "A feedback loop that improves itself");
fig(s, "fig15_learning_curve.png", 6.6, 1.6, 6.3, 5.0);
s.addText(bullets([
  "Loop: agent prices → environment returns realized demand → monitor logs outcomes → agent updates.",
  "An ε-greedy bandit learns the multiplier per utilization bucket; exploration decays over episodes.",
  "Tracks the three required metrics: wait-time reduction, customer response rate, pricing efficiency."]),
  {x:0.6, y:1.6, w:5.8, h:1.85});
card(s, 0.55, 3.5, 5.85, 1.45, "It improves over episodes",
  "Peak wait-reduction proxy 29% → 58%; pricing efficiency 0.848 → 0.868 CNY/kWh; the online elasticity estimate converges to the true −0.32.", TEAL);
card(s, 0.55, 5.05, 5.85, 1.6, "What it learns (honest)",
  "Surge congested buckets, stay neutral elsewhere → +0.58% revenue & +5.85 pp peak relief vs flat, beating the fixed policy. It declines to discount — myopically unprofitable.", AMBER);
footer(s,7);

/* ---------------- 8. IMPLICATIONS (dark) ---------------- */
s = p.addSlide(); s.background={color:INK};
s.addText("BUSINESS, OPERATIONAL & POLICY IMPLICATIONS",
  {x:0.55, y:0.45, w:12, h:0.3, fontSize:12, bold:true, color:AMBER, fontFace:HEAD, charSpacing:2, margin:0});
s.addText("From analysis to decisions",
  {x:0.5, y:0.74, w:12.3, h:0.7, fontSize:29, bold:true, color:WHITE, fontFace:HEAD, margin:0});
const cols=[
  ["BUSINESS", TEAL, ["Don't sell dynamic pricing as a revenue lever — pitch congestion relief & load balancing, revenue held flat.",
    "Concentrate surge on the ~10% genuinely hot (mostly non-CBD) zones.",
    "Fund equity / off-peak discounts from surge revenue — keep it revenue-neutral."]],
  ["OPERATIONAL", AMBER, ["Forecast-driven surge cuts the peak wait proxy ~57% — service quality, no new hardware.",
    "Idle/occupancy fees free capacity: ~46% of ACN sessions sit idle >1h after charging.",
    "Most chargers are under-used (61% of hours <30%) → expand hot zones, not uniformly."]],
  ["POLICY", ICE, ["Bounded, transparent, published multipliers keep pricing fair & predictable.",
    "Price scarcity, not demographics — surge follows measured load, falls on non-CBD hot zones.",
    "Treat off-peak discounts as a strategic adoption / grid-balancing instrument."]]];
cols.forEach((c,i)=>{ const x=0.55+i*4.12;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {x, y:1.7, w:3.9, h:4.95, fill:{color:INK2},
    line:{color:c[1], width:1}, rectRadius:0.06});
  s.addText(c[0], {x:x+0.3, y:1.95, w:3.4, h:0.4, fontSize:16, bold:true, color:c[1],
    fontFace:HEAD, charSpacing:1, margin:0});
  s.addText(c[2].map(t=>({text:t, options:{bullet:{indent:14}, breakLine:true, paraSpaceAfter:11,
    color:"E6F1EF", fontSize:12.5, fontFace:BODY}})), {x:x+0.3, y:2.45, w:3.35, h:4.0, valign:"top"});
});
footer(s,8);

/* ---------------- 9. APPENDIX A — robustness ---------------- */
s = p.addSlide(); s.background={color:WHITE};
header(s, "APPENDIX · ROBUSTNESS", "Every headline conclusion stress-tested");
fig(s, "fig17_robustness_elasticity.png", 0.55, 1.55, 6.1, 3.5);
fig(s, "fig19_robustness_cbd.png", 6.85, 1.55, 6.0, 3.5);
s.addText(bullets([
  "Elasticity: revenue stays ~neutral (−0.34% to −0.08%) across ε ∈ [−0.1, −0.8] — not an artefact of the point estimate.",
  "Triggers: across 25 (discount, surge) combos outcomes move smoothly (revenue −0.80% to +0.77%) — not a knife-edge.",
  "Peak definition: tertile / quartile / above-mean all identify the overnight block (Jaccard 0.73–1.0).",
  "Fairness: surge falls on congested non-CBD zones; forecast accuracy comparable across segments.",
  "Features: dropping all lags collapses the demand model (R² 0.96 → 0.78) — temporal structure drives it."]),
  {x:0.6, y:5.2, w:12.2, h:1.5});
footer(s,9);

/* ---------------- 10. APPENDIX B — assumptions / repro ---------------- */
s = p.addSlide(); s.background={color:WHITE};
header(s, "APPENDIX · ASSUMPTIONS, LIMITATIONS & REPRODUCIBILITY", "How to read — and rerun — this work");
s.addText("Assumptions & limitations", {x:0.55, y:1.55, w:6, h:0.35, fontSize:15, bold:true, color:TEALD, fontFace:HEAD, margin:0});
s.addText(bullets([
  "Elasticity is associational (FE controls), not causal — all 'after' figures are simulated under it.",
  "The learning environment is a calibrated constant-elasticity simulation, not a live A/B test.",
  "No cross-time substitution modelled — real peak→off-peak shifting would improve the uplift case.",
  "Single city, 30 days (Shenzhen); ACN is Caltech-only (~15k, no price) — not the 30k+/JPL headline.",
  "Wait time is an M/M/1-style proxy; ₹15/kWh is an illustrative anchor (metrics are unit-invariant)."]),
  {x:0.6, y:1.95, w:6.0, h:3.0});
s.addText("Reproducibility & deliverables", {x:6.95, y:1.55, w:6, h:0.35, fontSize:15, bold:true, color:TEALD, fontFace:HEAD, margin:0});
s.addText(bullets([
  "7 scripts + 6 runnable notebooks; single config; fixed seed; strict time-based split.",
  "Gradient boosting via sklearn HistGradientBoosting (LightGBM unavailable offline; same family).",
  "Outputs: 30+ CSV/MD tables, 19 figures, saved models — every score in a CSV.",
  "Run: preprocess → eda → demand → pricing → monitoring → robustness."]),
  {x:7.0, y:1.95, w:5.85, h:2.6});
// pipeline flow
const steps=["Preprocess","EDA","Demand","Tariff","Monitor","Robust"];
steps.forEach((t,i)=>{ const x=0.7+i*2.04;
  s.addShape(p.shapes.OVAL, {x, y:5.35, w:0.5, h:0.5, fill:{color:(i%2?AMBER:TEAL)}});
  s.addText(String(i+1), {x, y:5.35, w:0.5, h:0.5, align:"center", valign:"middle", fontSize:16,
    bold:true, color:WHITE, fontFace:HEAD, margin:0});
  s.addText(t, {x:x-0.35, y:5.92, w:1.2, h:0.35, align:"center", fontSize:11.5, bold:true,
    color:BODYC, fontFace:BODY, margin:0});
  if(i<steps.length-1) s.addShape(p.shapes.LINE, {x:x+0.55, y:5.6, w:1.45, h:0,
    line:{color:GREY, width:1.5}}); });
footer(s,10);

p.writeFile({ fileName: "deck/OP26_deck.pptx" }).then(f=>console.log("wrote", f));
