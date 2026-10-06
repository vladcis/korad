# LiFePO4 charging (CC/CV)  –  3.2 V cells, 12 V packs = 4S, 24 V = 8S
from lib_batt import cccv_charge

CELLS       = 4        # cells in series (4S = "12 V" battery, 8S = "24 V")
CAPACITY_AH = 10       # capacity [Ah]
C_RATE      = 0.3      # charge current (supply max is 5 A!)
V_CELL      = 3.60     # end-of-charge voltage per cell [V]; 3.55–3.65 V; 3.50 V = gentle (≈ 95 %)
CUTOFF_C    = 0.05     # cut-off current (C/20)
LIMIT_H     = 10
LOG         = "lifepo4"

cccv_charge(
    psu,
    v_max=CELLS * V_CELL,
    i_charge=min(5.0, CAPACITY_AH * C_RATE),
    i_term=max(0.01, CAPACITY_AH * CUTOFF_C),
    timeout_h=LIMIT_H,
    v_min=CELLS * 2.0,            # below 2.0 V/cell do not start
    precharge_v=CELLS * 2.5,
    precharge_i=max(0.05, CAPACITY_AH * 0.05),
    ah_max=CAPACITY_AH * 1.2,
    log_name=LOG,
    name=f"LiFePO4 {CELLS}S {CAPACITY_AH} Ah",
)
