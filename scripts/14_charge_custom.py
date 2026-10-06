# Generic CC/CV charging with manually entered values (other chemistries, cells, supercapacitors…)
from lib_batt import cccv_charge

V_END     = 8.40    # CV voltage [V]
I_CHARGE  = 1.00    # CC current [A]
I_CUTOFF  = 0.10    # finish when the current in the CV phase drops below [A]
V_MINIMUM = 5.0     # do not start if the battery is below this voltage [V] (0 = no check)
LIMIT_H   = 5
AH_MAX    = None    # e.g. 3.0 – safety limit on charged capacity [Ah]
LOG       = "charge"

cccv_charge(psu, V_END, I_CHARGE, I_CUTOFF, LIMIT_H,
            v_min=V_MINIMUM, ah_max=AH_MAX, log_name=LOG, name="custom")
