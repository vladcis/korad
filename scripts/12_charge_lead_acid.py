# 12 V lead-acid battery charging (6 cells) – three-stage: bulk (CC) → absorption (CV) → float
# Type: AGM 14.4–14.7 V / float 13.6–13.8 V,  gel 14.1–14.4 V / float 13.5–13.8 V,
#       flooded 14.4–14.8 V / float 13.5–13.8 V.  For a 6 V battery divide the values by two.
from lib_batt import cccv_charge, float_stage

CAPACITY_AH  = 7.2      # e.g. 7.2 Ah UPS AGM; 45 Ah car battery (supply max current is 5 A)
V_ABSORPTION = 14.4     # absorption (end-of-charge) voltage [V]
V_FLOAT      = 13.6     # float voltage [V]
FLOAT_H      = 2        # how long to hold float [h]; 0 = skip
C_RATE       = 0.15     # bulk current (0.1–0.25 C; max 5 A)
CUTOFF_C     = 0.02     # end absorption when current drops below 0.02 C
LIMIT_H      = 16
LOG          = "lead_acid"

i_bulk = min(5.0, CAPACITY_AH * C_RATE)
cccv_charge(
    psu,
    v_max=V_ABSORPTION,
    i_charge=i_bulk,
    i_term=max(0.02, CAPACITY_AH * CUTOFF_C),
    timeout_h=LIMIT_H,
    v_min=10.5,                    # below 10.5 V (deeply discharged / sulfated) do not start
    ah_max=CAPACITY_AH * 1.3,
    log_name=LOG,
    name=f"Pb 12 V {CAPACITY_AH} Ah",
)
if FLOAT_H > 0:
    float_stage(psu, V_FLOAT, i_bulk, FLOAT_H, log_name=(LOG + "_float") if LOG else None)
