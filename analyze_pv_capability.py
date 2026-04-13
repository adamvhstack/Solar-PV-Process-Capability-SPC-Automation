"""
===============================================================================
Script 2: Process Capability (Cp/Cpk & Pp/Ppk) + X-bar Control Chart
===============================================================================
PURPOSE:
    Read the 10,000-row CSV produced by Script 1 and answer two questions:

    1. CAPABILITY  — Is the process spread narrow enough to reliably hit the
                     engineering spec limits?  (Cp/Cpk and Pp/Ppk indices)

    2. STABILITY   — Is the process mean staying in one place over time, or
                     is it drifting / jumping?  (X-bar control chart)

OUTPUT:
    pv_capability_report.png   — a three-panel chart:
        Top    : Cp/Cpk bar chart (within-subgroup sigma) for all 10 parameters
        Bottom : X-bar control charts for Pmax and Efficiency

DEPENDENCIES:
    numpy      — array maths
    pandas     — CSV loading and data manipulation
    matplotlib — plotting engine

KEY CONCEPTS (read before the code):

    Cp vs Pp — TWO capabilies
    -------------------------------------------
    Both measure "does the process fit inside the spec window?", but they
    estimate process spread (sigma) differently:

    Cp  uses sigma_WITHIN  = R-bar / d2
        This is the SHORT-TERM, within-subgroup estimate.  It captures only
        the inherent common-cause variation happening inside each small group
        of consecutive parts.  It deliberately ignores shifts between groups.
        Think of it as "what the process CAN do when nothing changes."

    Pp  uses sigma_OVERALL = sample std dev of ALL individual readings
        This is the LONG-TERM estimate.  It includes both within-subgroup
        variation AND any between-subgroup shifts (tool wear, batch changes,
        operator differences, etc.).
        Think of it as "what the process IS ACTUALLY doing over the full run."

    If Cp ≈ Pp  - the process is stable; no significant between-group shifts.
    If Cp > Pp  - special-cause variation is inflating overall spread.
                  The X-bar chart will usually show out-of-control signals.

    Cpk and Ppk apply the same logic but penalise an off-centre mean:
        Cpk = min( (USL-mean)/(3*sigma_within), (mean-LSL)/(3*sigma_within) )
        Ppk = min( (USL-mean)/(3*sigma_overall), (mean-LSL)/(3*sigma_overall) )

    The d2 constant
    -------------------------------------------
    d2 converts the average subgroup range (R-bar) into an unbiased estimate
    of the population standard deviation.  Its value depends on subgroup size n.
    For n=5, d2 = 2.326 (from standard SPC tables).

    sigma_within = R-bar / d2

    X-bar chart:
          Split all individual readings into consecutive subgroups of size n.
          Calculate the mean (X-bar) of each subgroup.
          Plot those means over time.
          Add control limits (UCL/LCL) derived from the average subgroup range.
          Points outside UCL/LCL are "out-of-control" — something changed.
===============================================================================
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Patch   # used to build the custom legend


# ── Engineering Spec Limits ────────────────────────────────────────────────────
# These MUST match the lsl/usl values in Script 1, because they define what
# "acceptable" means for each parameter.  Changing them here without changing
# the generator would give misleading capability results.
SPECS = {
    "Pmax_W":          {"lsl": 380.0, "usl": 420.0},
    "Voc_V":           {"lsl": 48.5,  "usl": 50.5},
    "Isc_A":           {"lsl": 9.80,  "usl": 10.60},
    "Vmp_V":           {"lsl": 39.5,  "usl": 42.5},
    "Imp_A":           {"lsl": 9.40,  "usl": 10.10},
    "Fill_Factor_pct": {"lsl": 77.0,  "usl": 82.0},
    "Efficiency_pct":  {"lsl": 19.5,  "usl": 21.5},
    "Temp_Coeff_Pmax": {"lsl": -0.370,"usl": -0.330},
    "Series_R_ohm":    {"lsl": 0.250, "usl": 0.350},
    "Shunt_R_ohm":     {"lsl": 300.0, "usl": 400.0},
}

# Must match the value used when generating the data (Script 1)
SUBGROUP_SIZE = 5

# d2 constants (from ISO 8258 / ASTM SPC tables) for subgroup sizes n = 2 … 10.
# d2 converts R-bar into an unbiased estimate of sigma:  sigma_within = R-bar / d2
D2_TABLE = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326,
            6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078}

# A2 constants (from ISO / ASTM SPC tables) for subgroup sizes n = 2 … 10.
# A2 converts R-bar into 3-sigma control limits for X-bar:  UCL/LCL = X-bar-bar ± A2*R-bar
# Note: A2 = 3 / (d2 * sqrt(n)), so they are mathematically related to d2.
A2_TABLE = {2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577,
            6: 0.483, 7: 0.419, 8: 0.373, 9: 0.337, 10: 0.308}


def subgroup_stats(series, subgroup_size):
    """
    Split an ordered series into consecutive subgroups and compute per-subgroup
    means and ranges.

    Parameters
    ----------
    series         : pandas Series  — the raw individual measurements in order
    subgroup_size  : int            — how many consecutive readings form one group

    Returns
    -------
    xbar     : numpy array  — mean of each subgroup
    ranges   : numpy array  — range (max-min) of each subgroup
    xbar_bar : float        — grand mean (mean of all subgroup means)
    r_bar    : float        — average range across all subgroups
    """
    n    = subgroup_size
    vals = series.values

    # Only complete subgroups; drop any trailing partial group.
    complete = (len(vals) // n) * n
    reshaped = vals[:complete].reshape(-1, n)

    xbar   = reshaped.mean(axis=1)
    ranges = reshaped.max(axis=1) - reshaped.min(axis=1)

    xbar_bar = xbar.mean()
    r_bar    = ranges.mean()

    return xbar, ranges, xbar_bar, r_bar


# ==============================================================================
# FUNCTION: capability  (Cp/Cpk — within-subgroup sigma)
# ==============================================================================
def capability(series, lsl, usl, subgroup_size):
    """
    Calculate Cp and Cpk using the WITHIN-SUBGROUP sigma estimate (R-bar / d2).

    This is the textbook short-term capability.  It measures what the process
    CAN do when only common-cause variation is present.

    Parameters
    ----------
    series         : pandas Series  — raw individual measurements
    lsl            : float          — Lower Spec Limit
    usl            : float          — Upper Spec Limit
    subgroup_size  : int            — rational subgroup size (must be 2–10)

    Returns
    -------
    cp, cpk, mu, sigma_within  (all floats)
    """
    _, _, xbar_bar, r_bar = subgroup_stats(series, subgroup_size)
    mu = xbar_bar                   # best estimate of process location

    d2 = D2_TABLE.get(subgroup_size, 2.326)
    sigma_w = r_bar / d2            # within-subgroup sigma

    cp  = (usl - lsl) / (6 * sigma_w)
    cpu = (usl - mu)  / (3 * sigma_w)
    cpl = (mu  - lsl) / (3 * sigma_w)
    cpk = min(cpu, cpl)

    return cp, cpk, mu, sigma_w


# ==============================================================================
# FUNCTION: performance  (Pp/Ppk — overall sigma)
# ==============================================================================
def performance(series, lsl, usl):
    """
    Calculate Pp and Ppk using the OVERALL (long-term) sigma.

    This measures what the process IS ACTUALLY doing, including any between-
    subgroup shifts (tool wear, batch changes, environmental drift, etc.).

    Parameters
    ----------
    series : pandas Series  — raw individual measurements
    lsl    : float          — Lower Spec Limit
    usl    : float          — Upper Spec Limit

    Returns
    -------
    pp, ppk, mu, sigma_overall  (all floats)
    """
    mu      = series.mean()
    sigma_o = series.std(ddof=1)    # sample std dev of ALL readings

    pp  = (usl - lsl) / (6 * sigma_o)
    ppu = (usl - mu)  / (3 * sigma_o)
    ppl = (mu  - lsl) / (3 * sigma_o)
    ppk = min(ppu, ppl)

    return pp, ppk, mu, sigma_o


# ==============================================================================
# FUNCTION: xbar_chart_data
# ==============================================================================
def xbar_chart_data(series, subgroup_size):
    """
    Compute the subgroup means (X-bars) and the X-bar chart control limits
    using the classical R-bar method.

    Returns
    -------
    xbar      : numpy array  — the mean of each subgroup
    xbar_bar  : float        — the grand mean
    ucl       : float        — Upper Control Limit
    lcl       : float        — Lower Control Limit
    """
    xbar, _, xbar_bar, r_bar = subgroup_stats(series, subgroup_size)

    A2  = A2_TABLE.get(subgroup_size, 0.577)
    ucl = xbar_bar + A2 * r_bar
    lcl = xbar_bar - A2 * r_bar

    return xbar, xbar_bar, ucl, lcl


# ── Load the Data ──────────────────────────────────────────────────────────────
df = pd.read_csv("pv_test_results.csv")
param_cols = list(SPECS.keys())


# ── Compute Capability & Performance for Every Parameter ───────────────────────
rows = []
for col in param_cols:
    lsl = SPECS[col]["lsl"]
    usl = SPECS[col]["usl"]

    cp,  cpk,  mu_w, sigma_w = capability(df[col], lsl, usl, SUBGROUP_SIZE)
    pp,  ppk,  mu_o, sigma_o = performance(df[col], lsl, usl)

    rows.append({
        "Parameter":     col,
        "Mean":          mu_w,
        "Sigma_Within":  sigma_w,
        "Sigma_Overall": sigma_o,
        "LSL":           lsl,
        "USL":           usl,
        "Cp":            cp,
        "Cpk":           cpk,
        "Pp":            pp,
        "Ppk":           ppk,
    })

cap_df = pd.DataFrame(rows)

# Print the summary table to the console
print("\n=== Process Capability & Performance Summary ===")
print("    Cp / Cpk  = within-subgroup (short-term) capability")
print("    Pp / Ppk  = overall (long-term) performance\n")
print(cap_df.to_string(index=False, float_format="{:.4f}".format))


# ==============================================================================
# PLOTTING
# ==============================================================================
fig = plt.figure(figsize=(18, 14), facecolor="#F7F9FC")

gs = gridspec.GridSpec(
    2, 2, figure=fig,
    hspace=0.45, wspace=0.35,
    left=0.06, right=0.97, top=0.93, bottom=0.06
)


# ── Panel A: Capability Bar Chart (Cp / Cpk — within-subgroup) ───────────────
ax_cap = fig.add_subplot(gs[0, :])

x     = np.arange(len(cap_df))
width = 0.35

colors_cp = ["#4A90D9"] * len(cap_df)

colors_cpk = []
for cpk_val in cap_df["Cpk"]:
    if cpk_val >= 1.33:
        colors_cpk.append("#2ECC71")   # green — capable
    elif cpk_val >= 1.00:
        colors_cpk.append("#F39C12")   # amber — marginal
    else:
        colors_cpk.append("#E74C3C")   # red   — incapable

bars1 = ax_cap.bar(x - width/2, cap_df["Cp"],  width,
                   color=colors_cp,  alpha=0.85, edgecolor="white", label="Cp")
bars2 = ax_cap.bar(x + width/2, cap_df["Cpk"], width,
                   color=colors_cpk, alpha=0.92, edgecolor="white", label="Cpk")

ax_cap.axhline(1.33, color="#E74C3C", lw=1.5, ls="--", label="Target 1.33")
ax_cap.axhline(1.00, color="#F39C12", lw=1.0, ls=":",  label="Minimum 1.00")

ax_cap.set_xticks(x)
ax_cap.set_xticklabels(cap_df["Parameter"], rotation=20, ha="right", fontsize=9)
ax_cap.set_ylabel("Index Value", fontsize=10)
ax_cap.set_title(
    "Process Capability Indices (Cp / Cpk) — Within-Subgroup σ  —  All PV Parameters",
    fontsize=13, fontweight="bold", pad=10
)

ax_cap.set_ylim(0, max(cap_df["Cp"].max(), cap_df["Cpk"].max()) * 1.25)
ax_cap.yaxis.grid(True, alpha=0.35, ls="--")
ax_cap.set_axisbelow(True)

ax_cap.legend(handles=[
    Patch(color="#4A90D9", label="Cp  (within-subgroup)"),
    Patch(color="#2ECC71", label="Cpk ≥ 1.33 (capable)"),
    Patch(color="#F39C12", label="1.00 ≤ Cpk < 1.33 (marginal)"),
    Patch(color="#E74C3C", label="Cpk < 1.00 (incapable)"),
    plt.Line2D([0], [0], color="#E74C3C", ls="--", label="Target 1.33"),
    plt.Line2D([0], [0], color="#F39C12", ls=":",  label="Minimum 1.00"),
], loc="upper right", fontsize=8, ncol=3)

for bar in list(bars1) + list(bars2):
    h = bar.get_height()
    ax_cap.text(
        bar.get_x() + bar.get_width() / 2,
        h + 0.02,
        f"{h:.2f}",
        ha="center", va="bottom",
        fontsize=7.5, color="#333"
    )


# ── Panels B & C: X-bar Control Charts ────────────────────────────────────────
chart_params = ["Pmax_W", "Efficiency_pct"]
axes = [fig.add_subplot(gs[1, 0]),
        fig.add_subplot(gs[1, 1])]

for ax, col in zip(axes, chart_params):

    # --- Compute chart data ---------------------------------------------------
    xbar, xbar_bar, ucl, lcl = xbar_chart_data(df[col], SUBGROUP_SIZE)

    n_sg = len(xbar)
    x_sg = np.arange(1, n_sg + 1)

    out_mask = (xbar > ucl) | (xbar < lcl)

    # --- Draw the chart -------------------------------------------------------
    ax.plot(x_sg, xbar, color="#4A90D9", lw=0.7, zorder=2, label="Subgroup mean")
    ax.scatter(x_sg[~out_mask], xbar[~out_mask],
               s=6, color="#4A90D9", zorder=3)
    ax.scatter(x_sg[out_mask], xbar[out_mask],
               s=18, color="#E74C3C", zorder=4, label="Out-of-control")

    ax.axhline(xbar_bar, color="#2ECC71", lw=1.5, ls="-",
               label=f"Grand mean = {xbar_bar:.3f}")
    ax.axhline(ucl, color="#E74C3C", lw=1.2, ls="--",
               label=f"UCL = {ucl:.3f}")
    ax.axhline(lcl, color="#E74C3C", lw=1.2, ls=":",
               label=f"LCL = {lcl:.3f}")

    ax.fill_between(x_sg, lcl, ucl, alpha=0.06, color="#4A90D9")

    # --- Annotate with both Cp/Cpk AND Pp/Ppk for context --------------------
    lsl = SPECS[col]["lsl"]
    usl = SPECS[col]["usl"]
    cp,  cpk,  _, sigma_w = capability(df[col], lsl, usl, SUBGROUP_SIZE)
    pp,  ppk,  _, sigma_o = performance(df[col], lsl, usl)

    ax.set_title(
        f"X-bar Chart — {col}\n"
        f"Cp={cp:.3f}  Cpk={cpk:.3f} (within)    "
        f"Pp={pp:.3f}  Ppk={ppk:.3f} (overall)    "
        f"n={SUBGROUP_SIZE}   {n_sg} subgroups",
        fontsize=9, fontweight="bold"
    )
    ax.set_xlabel("Subgroup Number", fontsize=9)
    ax.set_ylabel(col, fontsize=9)
    ax.legend(fontsize=8, loc="upper right")
    ax.yaxis.grid(True, alpha=0.3, ls="--")
    ax.set_axisbelow(True)

    # --- OOC percentage annotation -------------------------------------------
    ooc_pct = out_mask.mean() * 100
    ax.annotate(
        f"OOC: {ooc_pct:.1f}%",
        xy=(0.02, 0.04),
        xycoords="axes fraction",
        fontsize=9,
        color="#E74C3C" if ooc_pct > 0 else "#2ECC71",
        fontweight="bold"
    )


# ── Figure Title and Export ────────────────────────────────────────────────────
fig.suptitle("Solar PV Module Manufacturing — Process Capability & SPC Report",
             fontsize=15, fontweight="bold", y=0.97)

out_png = "pv_capability_report.png"
plt.savefig(out_png, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"\nChart saved -> {out_png}")
plt.close()
