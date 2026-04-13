"""
===============================================================================
Script 1: Generate 10,000 Solar PV Module End-of-Line Test Results
===============================================================================
PURPOSE:
    Simulate a realistic manufacturing test dataset for crystalline-silicon
    photovoltaic (PV) modules.  Each row represents one module measured on the
    production line under Standard Test Conditions (STC: 1000 W/m², 25 °C,
    AM1.5 spectrum).

    We inject two kinds of random variation so the data behaves like real
    factory measurements rather than a perfectly clean theoretical distribution:
      • Common-cause noise  — the ever-present Gaussian scatter from tool wear,
        temperature drift, paste-viscosity changes, etc.
      • Special-cause bursts — rare, directional shifts that mimic real events
        such as a new paste batch, a laminator drift, or a string-soldering
        temperature change.

OUTPUT:
    pv_test_results.csv   (read by Script 2 for SPC / capability analysis)

DEPENDENCIES:
    numpy  — fast numerical arrays and random-number generation
    pandas — DataFrame construction and CSV export
===============================================================================
"""

import numpy as np
import pandas as pd


# ── Reproducibility ────────────────────────────────────────────────────────────
# Setting a random seed means every run produces IDENTICAL numbers.
# Remove or change this value if you want a fresh random dataset each time.
np.random.seed(42)

# Total number of module test records to generate
N = 10_000   # Python allows underscores in numbers for readability (= 10000)


# ── Parameter Definitions ──────────────────────────────────────────────────────
# Each key is a measured parameter name (will become a CSV column).
# Each value is a dict with five fields:
#   mean       — the target (nominal) value the process aims for
#   std        — the standard deviation of natural common-cause scatter
#   lsl        — Lower Spec Limit: the minimum acceptable value per datasheet
#   usl        — Upper Spec Limit: the maximum acceptable value per datasheet
#   burst_dir  — preferred direction of special-cause shifts:
#                  +1 = bursts tend to push the value UP   (e.g. resistance drift)
#                  -1 = bursts tend to push the value DOWN (e.g. degradation)
#                   0 = bursts are equally likely in either direction
#
# These values are representative of a ~400 W mono-PERC module measured at STC.
# The gap between LSL and USL is the "tolerance band".  A well-centred, low-
# spread process should sit comfortably inside that band — which is exactly
# what Cp and Cpk measure in Script 2.

PARAMS = {
    # Maximum power output (Watts) — the headline performance figure.
    # Bursts tend downward: contamination or micro-cracks reduce power.
    "Pmax_W":          {"mean": 400.0,  "std": 4.0,   "lsl": 380.0, "usl": 420.0,
                        "burst_dir": -1},

    # Open-circuit voltage (Volts) — voltage with no load attached.
    # Relatively stable; bursts can go either way (wafer doping variation).
    "Voc_V":           {"mean": 49.5,   "std": 0.30,  "lsl": 48.5,  "usl": 50.5,
                        "burst_dir": 0},

    # Short-circuit current (Amps) — current when terminals are shorted.
    # Bursts tend downward: paste smearing or dirty glass reduce photocurrent.
    "Isc_A":           {"mean": 10.20,  "std": 0.10,  "lsl": 9.80,  "usl": 10.60,
                        "burst_dir": -1},

    # Maximum-power-point voltage (Volts) — voltage at the Pmax operating point.
    "Vmp_V":           {"mean": 41.0,   "std": 0.40,  "lsl": 39.5,  "usl": 42.5,
                        "burst_dir": 0},

    # Maximum-power-point current (Amps) — current at the Pmax operating point.
    "Imp_A":           {"mean": 9.75,   "std": 0.09,  "lsl": 9.40,  "usl": 10.10,
                        "burst_dir": -1},

    # Fill Factor (%) — ratio of actual Pmax to the theoretical maximum (Voc × Isc).
    # A higher fill factor means the I-V curve is more "square" / efficient.
    # Bursts tend downward: series resistance increases degrade the fill factor.
    "Fill_Factor_pct": {"mean": 79.5,   "std": 0.80,  "lsl": 77.0,  "usl": 82.0,
                        "burst_dir": -1},

    # Conversion efficiency (%) — electrical power out / incident light power in.
    # Follows Pmax direction since efficiency = Pmax / (area × irradiance).
    "Efficiency_pct":  {"mean": 20.5,   "std": 0.25,  "lsl": 19.5,  "usl": 21.5,
                        "burst_dir": -1},

    # Temperature coefficient of Pmax (%/°C) — how much power drops per degree C.
    # Negative because power falls as temperature rises.
    # Bursts push the coefficient more negative (worse) — material degradation.
    "Temp_Coeff_Pmax": {"mean": -0.350, "std": 0.005, "lsl": -0.370, "usl": -0.330,
                        "burst_dir": -1},

    # Series resistance (Ohms) — internal resistance that causes I²R power loss.
    # Lower is better; bursts tend upward (solder joint degradation, paste issues).
    "Series_R_ohm":    {"mean": 0.300,  "std": 0.015, "lsl": 0.250,  "usl": 0.350,
                        "burst_dir": +1},

    # Shunt resistance (Ohms) — resistance of unintended current leakage paths.
    # Higher is better; bursts tend downward (micro-cracks open leakage paths).
    "Shunt_R_ohm":     {"mean": 350.0,  "std": 20.0,  "lsl": 300.0,  "usl": 400.0,
                        "burst_dir": -1},
}


# ── Subgroup Size ──────────────────────────────────────────────────────────────
# In Statistical Process Control (SPC), measurements are grouped into small
# "rational subgroups" — typically consecutive items off the same machine in a
# short time window.  The X-bar chart in Script 2 plots the MEAN of each
# subgroup rather than individual readings.  This makes trends easier to spot.
# A subgroup size of 5 is a classic industry default.
SUBGROUP_SIZE = 5


# ── Build the Dataset ──────────────────────────────────────────────────────────
# Start with a dictionary; we'll add one key (column) per parameter.
# Module IDs run from 1 to N inclusive.
data = {"Module_ID": np.arange(1, N + 1)}

# Loop over every parameter and generate N random measurements for it.
for col, p in PARAMS.items():

    # --- Step 1: Base (normal) noise -------------------------------------------
    # np.random.normal(mean, std, N) draws N values from a Gaussian bell curve
    # centred on `mean` with spread `std`.  This models the natural, common-cause
    # variation every manufacturing process has (tool wear, temperature drift, etc.)
    values = np.random.normal(p["mean"], p["std"], N)

    # --- Step 2: Directional burst noise ---------------------------------------
    # Real processes have rare "special-cause" events: a brief calibration
    # drift, a new batch of raw material, a technician adjustment.  Unlike
    # pure-random noise, these shifts are usually directional — for example,
    # contamination degrades power (downward), while solder degradation
    # increases series resistance (upward).
    #
    # We model this by randomly selecting ~2 % of readings and nudging them
    # by 1.5 standard deviations in the parameter's preferred burst direction.
    # If burst_dir == 0, the direction is randomised (symmetric bursts).

    burst_mask = np.random.random(N) < 0.02       # ~2 % of readings flagged
    n_burst    = burst_mask.sum()

    if p["burst_dir"] == 0:
        # Symmetric: randomly choose +1 or -1 for each burst
        directions = np.random.choice([-1, 1], n_burst)
    else:
        # Directional: 80 % of bursts go in the preferred direction,
        # 20 % go the opposite way (not everything is perfectly predictable).
        directions = np.where(
            np.random.random(n_burst) < 0.80,
            p["burst_dir"],
            -p["burst_dir"]
        )

    values[burst_mask] += directions * 1.5 * p["std"]

    # --- Step 3: Store rounded values -----------------------------------------
    # Round to 4 decimal places so the CSV doesn't have 15-digit floats.
    data[col] = np.round(values, 4)


# ── Subgroup Labels ────────────────────────────────────────────────────────────
# Assign each row to a subgroup number.
# np.arange(N) gives [0, 1, 2, ..., 9999].
# Integer division by SUBGROUP_SIZE groups rows 0-4 -> 0, rows 5-9 -> 1, etc.
# Adding 1 makes the labels start at 1 (more human-friendly).
# With N=10,000 and SUBGROUP_SIZE=5 we get 2,000 subgroups labelled 1-2000.
data["Subgroup"] = (np.arange(N) // SUBGROUP_SIZE) + 1


# ── Timestamps ─────────────────────────────────────────────────────────────────
# Simulate a flash tester (I-V curve tracer) that measures one module every
# 30 seconds, starting at 08:00 on 2025-01-01.  At that rate, 10,000 modules
# takes about 3.5 days — realistic for a high-throughput production line.
# pd.date_range creates a sequence of N evenly-spaced datetime values.
timestamps = pd.date_range("2025-01-01 08:00:00", periods=N, freq="30s")
data["Timestamp"] = timestamps


# ── Assemble and Export ────────────────────────────────────────────────────────
# Convert the dictionary of arrays into a pandas DataFrame (a 2-D table).
df = pd.DataFrame(data)

# Reorder columns so the metadata columns come first, then all measurement cols.
cols = ["Module_ID", "Timestamp", "Subgroup"] + list(PARAMS.keys())
df = df[cols]

# Write to CSV.  index=False prevents pandas from adding an extra row-number column.
out_path = "pv_test_results.csv"
df.to_csv(out_path, index=False)


# ── Quick Sanity Check ─────────────────────────────────────────────────────────
# Print a summary so we can eyeball that means and spreads look sensible.
# .describe() computes count/mean/std/min/quartiles/max for every numeric column.
# .T transposes the result (parameters become rows, statistics become columns)
# so it fits neatly on screen even with many columns.
print(f"Generated {N:,} records -> {out_path}")
print(df.describe().T[["mean", "std", "min", "max"]].to_string())
