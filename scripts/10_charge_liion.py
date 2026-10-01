# Nabíjanie Li-ion / LiPo (CC/CV)  –  18650, LiPo packy 1S–7S
# !!! Skontroluj počet článkov a polaritu. Nabíjaj pod dozorom na nehorľavom podklade. !!!
from lib_batt import cccv_charge

CLANKY        = 1        # počet článkov v sérii (1S, 2S, 3S …), max 7S na 30 V zdroji
KAPACITA_MAH  = 2500     # kapacita batérie [mAh]
C_RATE        = 0.5      # nabíjací prúd ako násobok kapacity (0.5 C = šetrné, 1 C = rýchle)
V_CLANOK      = 4.20     # koncové napätie na článok [V]; 4.10 = dlhšia životnosť, 4.35 iba pre LiHV!
UKONCENIE_C   = 0.05     # ukončovací prúd ako násobok kapacity (0.05 C = C/20; nabíjačky bežne C/10–C/20)
LIMIT_H       = 6        # bezpečnostný časový limit [h]
LOG           = "liion"  # názov CSV logu alebo None

kap = KAPACITA_MAH / 1000
cccv_charge(
    psu,
    v_max=CLANKY * V_CLANOK,
    i_charge=min(5.0, kap * C_RATE),
    i_term=max(0.01, kap * UKONCENIE_C),
    timeout_h=LIMIT_H,
    v_min=CLANKY * 2.5,            # pod 2.5 V/čl. je článok poškodený – nespúšťať
    precharge_v=CLANKY * 3.0,      # pod 3.0 V/čl. najprv prednabíjať malým prúdom
    precharge_i=max(0.02, kap * 0.1),
    ah_max=kap * 1.2,              # poistka: viac ako 120 % kapacity = niečo je zle
    log_name=LOG,
    name=f"Li-ion {CLANKY}S {KAPACITA_MAH} mAh",
)
