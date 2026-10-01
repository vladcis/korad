# Univerzálne CC/CV nabíjanie s ručne zadanými hodnotami (iné chémie, články, superkondenzátory…)
from lib_batt import cccv_charge

V_KONCOVE   = 8.40    # CV napätie [V]
I_NABIJACI  = 1.00    # CC prúd [A]
I_UKONCENIE = 0.10    # koniec, keď v CV fáze klesne prúd pod [A]
V_MINIMUM   = 5.0     # pod týmto napätím batérie nespúšťať [V] (0 = nekontrolovať)
LIMIT_H     = 5
AH_MAX      = None    # napr. 3.0 – poistka na nabitú kapacitu [Ah]
LOG         = "nabijanie"

cccv_charge(psu, V_KONCOVE, I_NABIJACI, I_UKONCENIE, LIMIT_H,
            v_min=V_MINIMUM, ah_max=AH_MAX, log_name=LOG, name="vlastné")
