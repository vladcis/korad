# Nabíjanie LiFePO4 (CC/CV)  –  3.2 V články, 12 V packy = 4S, 24 V = 8S
from lib_batt import cccv_charge

CLANKY        = 4        # počet článkov v sérii (4S = „12 V“ batéria, 8S = „24 V“)
KAPACITA_AH   = 10       # kapacita [Ah]
C_RATE        = 0.3      # nabíjací prúd (max 5 A zdroja!)
V_CLANOK      = 3.60     # koncové napätie na článok [V]; 3.55–3.65 V; 3.50 V = šetrné (≈ 95 %)
UKONCENIE_C   = 0.05     # ukončovací prúd (C/20)
LIMIT_H       = 10
LOG           = "lifepo4"

cccv_charge(
    psu,
    v_max=CLANKY * V_CLANOK,
    i_charge=min(5.0, KAPACITA_AH * C_RATE),
    i_term=max(0.01, KAPACITA_AH * UKONCENIE_C),
    timeout_h=LIMIT_H,
    v_min=CLANKY * 2.0,            # pod 2.0 V/čl. nespúšťať
    precharge_v=CLANKY * 2.5,
    precharge_i=max(0.05, KAPACITA_AH * 0.05),
    ah_max=KAPACITA_AH * 1.2,
    log_name=LOG,
    name=f"LiFePO4 {CLANKY}S {KAPACITA_AH} Ah",
)
