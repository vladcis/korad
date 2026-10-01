# Nabíjanie NiMH / NiCd – konštantný prúd s ukončením −ΔV (pokles napätia po vrchole)
# Zdroj meria s krokom 10 mV, preto −ΔV spoľahlivo funguje od ~4 článkov. Pri 1–3 článkoch
# nastav DV_CLANOK = 0.01 alebo použi POMALY = True (0.1 C, ukončenie časom).
from lib_batt import nimh_charge

CLANKY        = 4        # počet článkov v sérii (AA 4× = 4.8 V, 8× = 9.6 V)
KAPACITA_MAH  = 2000
POMALY        = False    # True = pomalé 0.1 C nabíjanie 14 h (bezpečné aj bez −ΔV)
C_RATE        = 0.5      # rýchle nabíjanie 0.3–1 C (iba s −ΔV)
DV_CLANOK     = 0.005    # −ΔV na článok [V]: NiMH 3–8 mV, NiCd 10–15 mV
V_CLANOK_MAX  = 1.60     # napäťový strop na článok (NiMH pri nabíjaní dosahuje 1.45–1.55 V)
LOG           = "nimh"

kap = KAPACITA_MAH / 1000
if POMALY:
    nimh_charge(psu, CLANKY, i_charge=kap * 0.1, dv_per_cell=1.0,  # −ΔV prakticky vypnuté
                v_cell_max=V_CLANOK_MAX, timeout_h=14, ah_max=kap * 1.5, log_name=LOG,
                name=f"NiMH {CLANKY} čl. pomaly 0.1 C")
else:
    nimh_charge(psu, CLANKY, i_charge=min(5.0, kap * C_RATE), dv_per_cell=DV_CLANOK,
                v_cell_max=V_CLANOK_MAX, blank_min=5, timeout_h=1.5 / C_RATE + 0.5,
                ah_max=kap * 1.3, log_name=LOG, name=f"NiMH {CLANKY} čl. {C_RATE} C",
                i_trickle=kap * 0.05, trickle_min=30)   # dobitie 0.05 C na 30 min po −ΔV
