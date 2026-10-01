# Panasonic CGR18650CG (18650 Li-ion, UL mark MH12210) – charging per the datasheet
#   capacity 2250 mAh typ. / 2150 mAh min., nominal 3.6 V, high-power cell (10 A discharge)
#   charge: CC/CV 4.20 V, 0.7 It = 1500 mA, cut-off 110 mA at 20 °C
#   do not charge below 0 °C or above 45 °C; a cell under 2.5 V is damaged – do not charge it
# !!! Check polarity, charge under supervision on a non-flammable surface. !!!
from lib_batt import cccv_charge

CELLS      = 1        # cells in series (1S = single 18650)
GENTLE     = False    # True = 0.5 C (1.1 A), longer cell life; False = datasheet 0.7 C (1.5 A)
V_CELL     = 4.20     # datasheet end-of-charge voltage; 4.10 V ≈ 90 % capacity, more cycles
LIMIT_H    = 4        # safety time limit [h] (datasheet charge time is ~2.5 h)
LOG        = "cgr18650cg"

I_CHARGE   = 1.1 if GENTLE else 1.5     # A
I_TERM     = 0.11                       # A – datasheet cut-off (≈ C/20)

cccv_charge(
    psu,
    v_max=CELLS * V_CELL,
    i_charge=I_CHARGE,
    i_term=I_TERM,
    timeout_h=LIMIT_H,
    v_min=CELLS * 2.5,          # below 2.5 V/cell: damaged cell, refuse to start
    precharge_v=CELLS * 3.0,    # below 3.0 V/cell (= discharge cut-off) precharge gently
    precharge_i=0.2,
    ah_max=CELLS * 2.7,         # safety: >120 % of 2250 mAh means something is wrong
    log_name=LOG,
    name=f"Panasonic CGR18650CG {CELLS}S",
)
