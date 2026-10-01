# Nabíjanie olovenej batérie 12 V (6 článkov) – trojstupňové: bulk (CC) → absorpcia (CV) → float
# Typ:  AGM 14.4–14.7 V / float 13.6–13.8 V,  gél 14.1–14.4 V / float 13.5–13.8 V,
#       klasická (zaplavovaná) 14.4–14.8 V / float 13.5–13.8 V.  Pre 6 V batériu hodnoty vydeľ dvoma.
from lib_batt import cccv_charge, float_stage

KAPACITA_AH   = 7.2      # napr. 7.2 Ah AGM do UPS; 45 Ah autobatéria (max prúd zdroja je 5 A)
V_ABSORPCIA   = 14.4     # absorpčné (koncové) napätie [V]
V_FLOAT       = 13.6     # udržiavacie napätie [V]
FLOAT_H       = 2        # ako dlho držať float [h]; 0 = preskočiť
C_RATE        = 0.15     # bulk prúd (0.1–0.25 C; max 5 A)
UKONCENIE_C   = 0.02     # koniec absorpcie, keď prúd klesne pod 0.02 C
LIMIT_H       = 16
LOG           = "olovo"

i_bulk = min(5.0, KAPACITA_AH * C_RATE)
cccv_charge(
    psu,
    v_max=V_ABSORPCIA,
    i_charge=i_bulk,
    i_term=max(0.02, KAPACITA_AH * UKONCENIE_C),
    timeout_h=LIMIT_H,
    v_min=10.5,                    # pod 10.5 V (hlboko vybitá / sulfatovaná) nespúšťať
    ah_max=KAPACITA_AH * 1.3,
    log_name=LOG,
    name=f"Pb 12 V {KAPACITA_AH} Ah",
)
if FLOAT_H > 0:
    float_stage(psu, V_FLOAT, i_bulk, FLOAT_H, log_name=(LOG + "_float") if LOG else None)
