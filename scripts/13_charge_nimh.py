# NiMH / NiCd charging – constant current with −ΔV termination (voltage drop after the peak)
# The supply measures in 10 mV steps, so −ΔV works reliably from ~4 cells. With 1–3 cells
# set DV_CELL = 0.01 or use SLOW = True (0.1 C, timed termination).
from lib_batt import nimh_charge

CELLS        = 4        # cells in series (AA 4× = 4.8 V, 8× = 9.6 V)
CAPACITY_MAH = 2000
SLOW         = False    # True = slow 0.1 C charge for 14 h (safe even without −ΔV)
C_RATE       = 0.5      # fast charge 0.3–1 C (only with −ΔV)
DV_CELL      = 0.005    # −ΔV per cell [V]: NiMH 3–8 mV, NiCd 10–15 mV
V_CELL_MAX   = 1.60     # voltage ceiling per cell (NiMH reaches 1.45–1.55 V while charging)
LOG          = "nimh"

cap = CAPACITY_MAH / 1000
if SLOW:
    nimh_charge(psu, CELLS, i_charge=cap * 0.1, dv_per_cell=1.0,  # −ΔV effectively disabled
                v_cell_max=V_CELL_MAX, timeout_h=14, ah_max=cap * 1.5, log_name=LOG,
                name=f"NiMH {CELLS} cells slow 0.1 C")
else:
    nimh_charge(psu, CELLS, i_charge=min(5.0, cap * C_RATE), dv_per_cell=DV_CELL,
                v_cell_max=V_CELL_MAX, blank_min=5, timeout_h=1.5 / C_RATE + 0.5,
                ah_max=cap * 1.3, log_name=LOG, name=f"NiMH {CELLS} cells {C_RATE} C",
                i_trickle=cap * 0.05, trickle_min=30)   # top-off at 0.05 C for 30 min after −ΔV
