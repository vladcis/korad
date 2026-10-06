# LiPo / LiHV charging (CC/CV) for RC packs 1S–7S, plus storage charge
# !!! The PSU cannot balance cells: a 2S+ pack needs a balancer / BMS on the balance lead. !!!
# !!! Never charge a puffed or damaged pack. Charge under supervision in a LiPo bag / on a non-flammable surface. !!!
from lib_batt import ChargeAbort, cccv_charge

CELLS        = 1        # cells in series (1S … 7S; LiHV max 6S on a 30 V supply)
CAPACITY_MAH = 1000     # pack capacity [mAh]
C_RATE       = 1.0      # charge current as a multiple of capacity (1 C = standard for LiPo, 0.5 C = gentle)
MODE         = "full"   # "full" = 4.20 V/cell, "lihv" = 4.35 V/cell (only packs marked LiHV!), "storage" = 3.80 V/cell
CUTOFF_C     = 0.1      # cut-off current as a multiple of capacity (RC chargers end at C/10)
BALANCER     = False    # True = a balancer / BMS watches the cells (required for CELLS > 1)
LOG          = "lipo"   # CSV log name or None

V_CELL = {"full": 4.20, "lihv": 4.35, "storage": 3.80}[MODE]
if CELLS > 1 and not BALANCER:
    raise ChargeAbort(f"{CELLS}S pack without a balancer: the PSU only sees the pack voltage and one cell could be "
                      "overcharged. Connect a balancer / BMS and set BALANCER = True.")

cap = CAPACITY_MAH / 1000
try:
    cccv_charge(
        psu,
        v_max=CELLS * V_CELL,
        i_charge=min(5.0, cap * C_RATE),
        i_term=max(0.01, cap * CUTOFF_C),
        timeout_h=1.5 / C_RATE + 0.5,  # safety time limit [h]
        v_min=CELLS * 3.0,             # below 3.0 V/cell a LiPo is over-discharged – do not charge it
        precharge_v=CELLS * 3.3,       # 3.0–3.3 V/cell: start gently with 0.1 C
        precharge_i=max(0.02, cap * 0.1),
        ah_max=cap * 1.1,              # safety: more than 110 % of capacity = something is wrong
        log_name=LOG,
        name=f"LiPo {CELLS}S {CAPACITY_MAH} mAh ({MODE} {V_CELL:.2f} V/cell)",
    )
except ChargeAbort as e:
    if MODE != "storage" or "already full" not in str(e):
        raise
    # the PSU cannot discharge: a pack above storage voltage has to go to a discharger / RC charger
    print(f"Pack is already at or above storage voltage ({V_CELL:.2f} V/cell) – the PSU cannot discharge it.")
