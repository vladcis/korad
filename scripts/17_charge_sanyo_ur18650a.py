# Sanyo UR18650A (18650 Li-ion, notebook cell; "U43A" on the wrapper is a lot marking) – per the datasheet
#   capacity 2250 mAh typ. / 2150 mAh min., nominal 3.6 V, max discharge 4.3 A
#   charge: CC/CV 4.20 V (+0.03 V, never above 4.35 V), standard 1.51 A (0.7 C), max 2.15 A, ~3 h
#   pre-charge below 3.0 V/cell with less than 0.215 A; charge only at 0–40 °C
#   datasheet gives no cut-off current – full-charge detection by current, C/20 = 110 mA is used here
#   never discharge below 2.0 V; a cell under 2.5 V has been over-discharged – do not charge it
# !!! Check polarity, charge under supervision on a non-flammable surface. !!!
from lib_batt import cccv_charge

CELLS      = 1        # cells in series
GENTLE     = False    # True = 0.5 C (1.1 A), longer cell life; False = datasheet standard 1.51 A
V_CELL     = 4.20     # datasheet end-of-charge voltage; 4.10 V ≈ 90 % capacity, more cycles
LIMIT_H    = 4.5      # safety time limit [h] (datasheet charge time is ~3 h)
LOG        = "ur18650a"

I_CHARGE   = 1.1 if GENTLE else 1.51    # A
I_TERM     = 0.11                       # A  (≈ C/20)

cccv_charge(
    psu,
    v_max=CELLS * V_CELL,
    i_charge=I_CHARGE,
    i_term=I_TERM,
    timeout_h=LIMIT_H,
    v_min=CELLS * 2.5,          # below 2.5 V/cell: over-discharged cell, refuse to start
    precharge_v=CELLS * 3.0,    # datasheet: pre-charge below 3.0 V/cell
    precharge_i=0.2,            # datasheet: below 0.215 A/cell
    ah_max=CELLS * 2.7,         # safety: >120 % of 2250 mAh means something is wrong
    log_name=LOG,
    name=f"Sanyo UR18650A {CELLS}S",
)
