# Li-ion / LiPo charging (CC/CV)  –  18650, LiPo packs 1S–7S
# !!! Check the cell count and polarity. Charge under supervision on a non-flammable surface. !!!
from lib_batt import cccv_charge

CELLS        = 1        # cells in series (1S, 2S, 3S …), max 7S on a 30 V supply
CAPACITY_MAH = 2500     # battery capacity [mAh]
C_RATE       = 0.5      # charge current as a multiple of capacity (0.5 C = gentle, 1 C = fast)
V_CELL       = 4.20     # end-of-charge voltage per cell [V]; 4.10 = longer life, 4.35 only for LiHV!
CUTOFF_C     = 0.05     # cut-off current as a multiple of capacity (0.05 C = C/20; chargers typically use C/10–C/20)
LIMIT_H      = 6        # safety time limit [h]
LOG          = "liion"  # CSV log name or None

cap = CAPACITY_MAH / 1000
cccv_charge(
    psu,
    v_max=CELLS * V_CELL,
    i_charge=min(5.0, cap * C_RATE),
    i_term=max(0.01, cap * CUTOFF_C),
    timeout_h=LIMIT_H,
    v_min=CELLS * 2.5,            # below 2.5 V/cell the cell is damaged – do not start
    precharge_v=CELLS * 3.0,      # below 3.0 V/cell precharge with a small current first
    precharge_i=max(0.02, cap * 0.1),
    ah_max=cap * 1.2,              # safety: more than 120 % of capacity = something is wrong
    log_name=LOG,
    name=f"Li-ion {CELLS}S {CAPACITY_MAH} mAh",
)
