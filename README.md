# Solar PV Module Manufacturing — Process Capability & SPC Automation

**An automated Statistical Process Control (SPC) toolkit that monitors critical-to-quality parameters for crystalline-silicon photovoltaic module production, computes short-term capability (Cp/Cpk) and long-term performance (Pp/Ppk) indices, renders X-bar control charts, and serves everything through an interactive browser-based dashboard.**

Built by **Adam Van Hove** · Oregon State University · Mechanical Engineering (B.S. 2027)

[**→ Launch Interactive Dashboard**](https://adamvhstack.github.io/Solar-PV-Process-Capability-SPC-Automation/pv_capability_dashboard.html)

---

## What This Project Does

In high-volume PV manufacturing, the difference between a profitable line and a scrap-heavy one comes down to how quickly you detect process drift. Manual SPC, pulling samples, hand-calculating X-bar/R values, taping control charts to a whiteboard, doesn't scale when you're testing 10,000+ modules across 10 parameters.

This project automates that entire workflow and answers the question every manufacturing engineer asks: **"Is my process capable, and where exactly is it drifting?"**

The system generates realistic end-of-line flash test data (with both common-cause noise and directional special-cause bursts), computes Cp/Cpk and Pp/Ppk for every critical parameter, renders X-bar control charts with out-of-control flagging, and presents everything through an interactive dashboard, the same deliverable that would appear on a quality engineering team's monitor on a real production floor.

---

## Dashboard Screenshots

### Process Capability Report (Matplotlib)
![Process Capability & SPC Report](assets/pv_capability_report.png)

---

## How It Works

### 1. Data Generation (`generate_pv_data.py`)

Simulates 10,000 end-of-line flash test records for a ~400W mono-PERC solar module measured at Standard Test Conditions (STC: 1000 W/m², 25°C, AM1.5 spectrum). Each record contains 10 CTQ parameters:

| Parameter | Description | Units | Nominal |
|-----------|------------|-------|---------|
| Pmax | Maximum power output | W | 400.0 |
| Voc | Open-circuit voltage | V | 49.5 |
| Isc | Short-circuit current | A | 10.20 |
| Vmp | Max-power-point voltage | V | 41.0 |
| Imp | Max-power-point current | A | 9.75 |
| Fill Factor | I-V curve squareness | % | 79.5 |
| Efficiency | Electrical conversion efficiency | % | 20.5 |
| Temp Coeff Pmax | Power temperature coefficient | %/°C | -0.350 |
| Series R | Internal series resistance | Ω | 0.300 |
| Shunt R | Shunt (leakage) resistance | Ω | 350.0 |

The noise model includes:

- **Common-cause variation**: Gaussian scatter representing normal process variation (tool wear, temperature drift, paste viscosity changes).
- **Directional special-cause bursts**: ~2% of readings receive an additional shift biased in the physically realistic direction. For example, contamination and micro-cracks push Pmax *downward*, while solder joint degradation pushes Series R *upward*. 80% of bursts follow the expected direction; 20% go the opposite way to reflect real-world unpredictability.

### 2. Capability & SPC Analysis (`analyze_pv_capability.py`)

Reads the generated CSV and computes:

- **Cp / Cpk** — Short-term (within-subgroup) capability using `σ_within = R̄ / d₂`. This is the textbook approach per ISO 8258, estimating process spread from the average subgroup range. It captures only inherent common-cause variation.
- **Pp / Ppk** — Long-term (overall) performance using `σ_overall = s` (sample standard deviation of all individual readings). This includes both within-subgroup and between-subgroup variation.
- **X-bar control charts** — Subgroup means plotted over time with UCL/LCL derived from `X̄̄ ± A₂R̄`. Out-of-control points are flagged.

Outputs a three-panel matplotlib report (`pv_capability_report.png`).

### 3. Interactive Dashboard (`pv_capability_dashboard.html`)

A self-contained HTML/JS dashboard (Chart.js) that lets you:

- Click any of the 10 parameter cards to drill into its data
- View Cp/Cpk vs Pp/Ppk side-by-side with 1.33 and 1.00 threshold lines
- Explore the histogram with LSL/USL/mean overlays
- Scroll through the X-bar control chart with highlighted OOC points
- Compare all parameters in a single overview bar chart

No build tools or server required, just open the `.html` file in any browser.

---

## Results Summary

| Parameter | Cpk | Status |
|-----------|-----|--------|
| Pmax (W) | 1.61 | ✅ Capable |
| Voc (V) | 1.10 | ⚠️ Marginal |
| Isc (A) | 1.29 | ⚠️ Marginal |
| Vmp (V) | 1.22 | ⚠️ Marginal |
| Imp (A) | 1.24 | ⚠️ Marginal |
| Fill Factor (%) | 1.01 | ⚠️ Marginal |
| Efficiency (%) | 1.29 | ⚠️ Marginal |
| Temp Coeff Pmax | 1.32 | ⚠️ Marginal |
| Series R (Ω) | 1.08 | ⚠️ Marginal |
| Shunt R (Ω) | 0.82 | ❌ Incapable |

Only Pmax exceeds the 1.33 industry benchmark. Shunt resistance is the highest-risk parameter (Cpk < 1.0), indicating the tolerance band is too narrow for the current process spread, a candidate for either tightening process controls or widening the spec.

---

## Key Technical Decisions

**Why Cp/Cpk instead of Pp/Ppk for the primary metric?**

The original version of this project computed capability using `series.std(ddof=1)`, the overall sample standard deviation. This is technically Pp/Ppk (long-term performance), not Cp/Cpk (short-term capability). The distinction matters because:

- Cp/Cpk uses σ estimated from *within-subgroup* variation (R̄/d₂), isolating only common-cause spread.
- Pp/Ppk uses the *overall* σ, which includes between-subgroup shifts (batch changes, tool wear, operator differences).
- If Cp ≈ Pp, the process is stable. If Cp >> Pp, special-cause variation is present and the X-bar chart will show it.

The updated version computes and displays both, giving a complete picture.

**Why directional burst noise?**

Real manufacturing special causes are rarely symmetric. A contaminated paste batch doesn't randomly increase *and* decrease fill factor, it degrades it. Modeling directional bursts produces data that better mimics real failure modes and makes for a more defensible simulation in technical discussions.

**Why R̄ / d₂ instead of pooled standard deviation?**

The R-bar method is the classical SPC approach, historically preferred because range is easy to compute by hand on the shop floor and robust to single outliers within small subgroups. For n=5, d₂=2.326 and A₂=0.577 (from standard SPC/ISO tables). The S-bar/c₄ method is equally valid and gives similar results for small subgroup sizes.

---

## Technical Skills Demonstrated

| Skill | Where It Appears |
|-------|-----------------|
| **Statistical Process Control (SPC)** | X-bar/R charts, UCL/LCL derivation, OOC flagging |
| **Process Capability Analysis** | Cp/Cpk (within-subgroup) and Pp/Ppk (overall) computation |
| **Lean Six Sigma Concepts** | DMAIC-aligned analysis, rational subgrouping, spec limit evaluation |
| **Monte Carlo / Stochastic Modeling** | Gaussian noise + directional special-cause burst injection |
| **Python (NumPy, Pandas, Matplotlib)** | Data generation, statistical computation, publication-quality charting |
| **Data Visualization** | Multi-panel matplotlib report + interactive Chart.js dashboard |
| **ISO 8258 / ASTM SPC Standards** | d₂, A₂ constants, R̄-based sigma estimation |
| **Manufacturing Domain Knowledge** | Mono-PERC PV module parameters, STC test conditions, realistic failure modes |
| **Interactive UI Design** | Self-contained HTML/CSS/JS dashboard, no backend required |

---

## Concepts & Methodology

This project applies several core Statistical Process Control and Lean Six Sigma concepts:

- **Cp / Cpk (Process Capability)**: Measures whether the short-term process spread fits within engineering spec limits. Uses within-subgroup σ estimated via R̄/d₂.
- **Pp / Ppk (Process Performance)**: Same metric but using overall σ, capturing long-term variation including between-subgroup shifts.
- **X-bar / R Charts**: Classical SPC control charts that plot subgroup means over time. Points beyond UCL/LCL signal special-cause variation.
- **Rational Subgrouping**: Consecutive modules (n=5) are grouped so that within-group variation represents only common-cause noise.
- **A₂ and d₂ Constants**: Tabled values from ISO 8258 / ASTM SPC standards that convert subgroup range statistics into σ estimates and control limits.

---

## How to Run

### Prerequisites
- Python 3.8+
- Required packages: `numpy`, `pandas`, `matplotlib`

### Quick Start
```bash
# Clone the repository
git clone https://github.com/adamvhstack/Solar-PV-Process-Capability-SPC-Automation.git
cd Solar-PV-Process-Capability-SPC-Automation

# Install dependencies
pip install numpy pandas matplotlib

# Step 1: Generate the synthetic dataset
python generate_pv_data.py

# Step 2: Run the capability analysis and generate the static report
python analyze_pv_capability.py

# Step 3: Open the interactive dashboard (no server needed)
open pv_capability_dashboard.html        # macOS
xdg-open pv_capability_dashboard.html    # Linux
start pv_capability_dashboard.html       # Windows
```

### Interactive Dashboard
Open `pv_capability_dashboard.html` in any modern browser, no server, no Python environment required.

---

## Technologies

- **Python 3** — NumPy, Pandas, Matplotlib
- **Chart.js 4** — Browser-based interactive charting
- **HTML/CSS/JS** — Self-contained dashboard (no framework, no build step)

---

## Related Projects

- [Supply Chain Digital Twin & AI Disruption Analyzer](https://github.com/adamvhstack/Adam-Van-Hove---Supply-Chain-Digital-Twin), A discrete-event simulation modeling a 3-tier supply network with Monte Carlo stress testing, Claude API-powered root cause analysis, and executive dashboards.

---

## License

This project is open source for educational and portfolio purposes.

---

## Author

**Adam Van Hove**
B.S. Mechanical Engineering — Oregon State University (2027)
Focused on Lean Manufacturing, NPI, and the intersection of engineering and operations strategy.

---

*Built as a portfolio project targeting Manufacturing Engineering, Quality Engineering, and TPM internship roles. Every component — from the noise model to the dashboard — is designed to be explainable in a 60-second interview answer.*
