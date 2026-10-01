"""Knižnica pre nabíjanie batérií laboratórnym zdrojom KORAD (CC/CV, −ΔV, udržiavacie nabíjanie).

Použitie v skripte:  from lib_batt import *

BEZPEČNOSŤ – laboratórny zdroj nie je nabíjačka:
 - skontroluj polaritu a správny počet článkov PRED spustením
 - nikdy nenechávaj nabíjanie bez dozoru, Li-ion/LiPo nabíjaj na nehorľavom podklade
 - zdroj nemeria teplotu batérie; pri zahriatí nabíjanie zastav (tlačidlo Stop)
 - pri vypnutom výstupe môže batéria tiecť späť do zdroja; na dlhé pripojenie daj do série Schottky diódu
 - ak článok klesne pod minimálne napätie (napr. Li-ion < 2.5 V), je pravdepodobne poškodený – nenabíjaj ho
"""
import time

PSU_V_MAX = 30.0
PSU_I_MAX = 5.0


class ChargeAbort(Exception):
    """Nabíjanie bezpečne prerušené (výstup je vypnutý)."""


def fmt_dur(sec):
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _check_limits(v_max, i_charge):
    if not 0 < v_max <= PSU_V_MAX:
        raise ChargeAbort(f"Napätie {v_max} V je mimo rozsahu zdroja (0–{PSU_V_MAX} V)")
    if not 0 < i_charge <= PSU_I_MAX:
        raise ChargeAbort(f"Prúd {i_charge} A je mimo rozsahu zdroja (0–{PSU_I_MAX} A)")


def probe_battery(psu, v_max, i_probe=0.05, settle=2.0):
    """Zapne výstup malým prúdom a vráti (napätie batérie, prúd, status). Odhalí chýbajúcu batériu."""
    psu.off()
    psu.set_i(min(i_probe, PSU_I_MAX))
    psu.set_v(v_max)
    psu.on()
    psu.wait(settle)
    v, i, st = psu.vout, psu.iout, psu.status()
    return v, i, st


def cccv_charge(psu, v_max, i_charge, i_term, timeout_h=8.0, *, v_min=0.0, precharge_v=None, precharge_i=None,
                ah_max=None, interval=2.0, report_every=30, log_name=None, name="batéria", term_count=3):
    """Nabíjanie CC/CV. Vráti nabitú kapacitu [Ah].

    v_max       koncové napätie (CV fáza) [V]
    i_charge    nabíjací prúd (CC fáza) [A]
    i_term      ukončovací prúd – keď v CV fáze klesne prúd pod túto hodnotu, hotovo [A]
    timeout_h   bezpečnostný časový limit [h]
    v_min       pod týmto napätím batérie sa nabíjanie nespustí (hlboko vybitá / zlá polarita / zlý počet článkov)
    precharge_v, precharge_i   pod precharge_v nabíjaj malým prúdom precharge_i (Li-ion pod 3.0 V/čl.)
    ah_max      bezpečnostný limit nabitej kapacity [Ah] (napr. 1.2 × kapacita)
    log_name    názov CSV logu (None = nelogovať)
    """
    _check_limits(v_max, i_charge)
    print(f"=== Nabíjanie: {name} ===")
    print(f"CV {v_max:.2f} V, CC {i_charge:.3f} A, ukončenie pri {i_term:.3f} A, limit {timeout_h:g} h"
          + (f", max {ah_max:g} Ah" if ah_max else ""))

    v, i, st = probe_battery(psu, v_max)
    if st["cv"] and i < 0.01:
        psu.off()
        raise ChargeAbort(f"Na výstupe nie je batéria alebo je už plná (U={v:.2f} V, I={i:.3f} A)")
    if v < v_min:
        psu.off()
        raise ChargeAbort(f"Napätie batérie {v:.2f} V je pod minimom {v_min:.2f} V – skontroluj polaritu, počet článkov alebo stav batérie")
    print(f"Batéria: {v:.2f} V")

    if log_name:
        psu.log_start(log_name, interval)
    t0 = time.time()
    last = t0
    ah = 0.0
    try:
        if precharge_v and precharge_i and v < precharge_v:
            print(f"Prednabíjanie prúdom {precharge_i:.3f} A do {precharge_v:.2f} V …")
            psu.set_i(precharge_i)
            while True:
                psu.wait(interval)
                now = time.time()
                v, i = psu.vout, psu.iout
                ah += i * (now - last) / 3600
                last = now
                if v >= precharge_v:
                    break
                if now - t0 > 3600:
                    raise ChargeAbort("Prednabíjanie trvá viac ako 1 h – batéria je pravdepodobne poškodená")
            print(f"[{fmt_dur(now - t0)}] prednabité na {v:.2f} V")

        psu.set_i(i_charge)
        phase = "CC"
        below = 0
        last_report = 0.0
        while True:
            psu.wait(interval)
            now = time.time()
            v, i, st = psu.vout, psu.iout, psu.status()
            ah += i * (now - last) / 3600
            last = now
            el = now - t0
            if not st["output"]:
                raise ChargeAbort("Výstup zdroja sa vypol (OCP/OVP alebo ručne)")
            new_phase = "CV" if st["cv"] else "CC"
            if new_phase != phase:
                print(f"[{fmt_dur(el)}] {phase} → {new_phase} pri {v:.2f} V, {i:.3f} A, nabité {ah:.3f} Ah")
                phase = new_phase
            below = below + 1 if (phase == "CV" and i <= i_term) else 0
            if below >= term_count:
                print(f"[{fmt_dur(el)}] HOTOVO – prúd klesol pod {i_term:.3f} A")
                break
            if el > timeout_h * 3600:
                raise ChargeAbort(f"Časový limit {timeout_h:g} h – nabíjanie prerušené (nabité {ah:.3f} Ah)")
            if ah_max and ah > ah_max:
                raise ChargeAbort(f"Prekročený limit kapacity {ah_max:g} Ah – nabíjanie prerušené")
            if el - last_report >= report_every:
                print(f"[{fmt_dur(el)}] {phase}  U={v:.2f} V  I={i:.3f} A  nabité {ah:.3f} Ah")
                last_report = el
    finally:
        psu.off()
        if log_name:
            psu.log_stop()
    print(f"Celkom nabité {ah:.3f} Ah za {fmt_dur(time.time() - t0)}")
    return ah


def float_stage(psu, v_float, i_max, hours, *, interval=5.0, report_every=300, log_name=None):
    """Udržiavacie (float) nabíjanie konštantným napätím po zadaný čas [h]. Vráti nabité Ah."""
    _check_limits(v_float, i_max)
    print(f"=== Float {v_float:.2f} V, max {i_max:.3f} A, {hours:g} h ===")
    psu.off()
    psu.set_i(i_max)
    psu.set_v(v_float)
    psu.on()
    if log_name:
        psu.log_start(log_name, interval)
    t0 = time.time()
    last = t0
    ah = 0.0
    last_report = 0.0
    try:
        while True:
            psu.wait(interval)
            now = time.time()
            i = psu.iout
            ah += i * (now - last) / 3600
            last = now
            el = now - t0
            if el >= hours * 3600:
                break
            if el - last_report >= report_every:
                print(f"[{fmt_dur(el)}] float  U={psu.vout:.2f} V  I={i:.3f} A  ({ah:.3f} Ah)")
                last_report = el
    finally:
        psu.off()
        if log_name:
            psu.log_stop()
    print(f"Float ukončený, dodané {ah:.3f} Ah")
    return ah


def nimh_charge(psu, cells, i_charge, *, v_cell_max=1.60, dv_per_cell=0.005, blank_min=5.0, timeout_h=3.0,
                ah_max=None, v_min_cell=0.9, interval=2.0, report_every=30, log_name=None, name="NiMH",
                i_trickle=None, trickle_min=0):
    """Nabíjanie NiMH/NiCd konštantným prúdom s ukončením −ΔV (pokles napätia po vrchole).

    cells        počet článkov v sérii
    i_charge     nabíjací prúd [A] (rýchle nabíjanie 0.5–1 C; pomalé 0.1 C ukonči radšej časom – timeout_h)
    v_cell_max   napäťový strop zdroja na článok [V]; ak sa dosiahne (CV), nabíjanie skončí
    dv_per_cell  pokles napätia na článok, ktorý ukončí nabíjanie [V]; zdroj meria s krokom 10 mV,
                 preto pri < 4 článkoch použi dv_per_cell=0.01 alebo viac
    blank_min    minúty na začiatku, počas ktorých sa −ΔV ignoruje (napätie najprv stúpa)
    i_trickle, trickle_min   voliteľné dobíjanie malým prúdom po skončení (napr. 0.05 C, 30 min)
    """
    v_max = cells * v_cell_max
    _check_limits(v_max, i_charge)
    dv = cells * dv_per_cell
    print(f"=== Nabíjanie: {name}, {cells} čl., CC {i_charge:.3f} A, −ΔV {dv * 1000:.0f} mV, strop {v_max:.2f} V ===")
    v, i, st = probe_battery(psu, v_max)
    if st["cv"] and i < 0.01:
        psu.off()
        raise ChargeAbort(f"Na výstupe nie je batéria (U={v:.2f} V, I={i:.3f} A)")
    if v < cells * v_min_cell:
        psu.off()
        raise ChargeAbort(f"Napätie {v:.2f} V je pod {cells * v_min_cell:.2f} V – zlý počet článkov alebo poškodená batéria")
    print(f"Batéria: {v:.2f} V ({v / cells:.3f} V/čl.)")
    if log_name:
        psu.log_start(log_name, interval)
    psu.set_i(i_charge)
    t0 = time.time()
    last = t0
    ah = 0.0
    peak = 0.0
    window = []
    last_report = 0.0
    reason = None
    try:
        while True:
            psu.wait(interval)
            now = time.time()
            v, i, st = psu.vout, psu.iout, psu.status()
            ah += i * (now - last) / 3600
            last = now
            el = now - t0
            if not st["output"]:
                raise ChargeAbort("Výstup zdroja sa vypol")
            window.append(v)
            window = window[-5:]
            avg = sum(window) / len(window)
            if el > blank_min * 60:
                if avg > peak:
                    peak = avg
                elif peak - avg >= dv:
                    reason = f"−ΔV: vrchol {peak:.3f} V, teraz {avg:.3f} V"
                    break
            if st["cv"]:
                reason = f"dosiahnutý napäťový strop {v_max:.2f} V"
                break
            if el > timeout_h * 3600:
                reason = f"časový limit {timeout_h:g} h"
                break
            if ah_max and ah > ah_max:
                reason = f"limit kapacity {ah_max:g} Ah"
                break
            if el - last_report >= report_every:
                print(f"[{fmt_dur(el)}] U={v:.2f} V ({v / cells:.3f}/čl.)  I={i:.3f} A  vrchol {peak:.3f} V  {ah:.3f} Ah")
                last_report = el
        print(f"[{fmt_dur(el)}] KONIEC – {reason}; nabité {ah:.3f} Ah")
        if i_trickle and trickle_min:
            print(f"Dobíjanie {i_trickle:.3f} A po {trickle_min:g} min …")
            psu.set_i(i_trickle)
            t1 = time.time()
            while time.time() - t1 < trickle_min * 60:
                psu.wait(interval)
                ah += psu.iout * interval / 3600
    finally:
        psu.off()
        if log_name:
            psu.log_stop()
    print(f"Celkom nabité {ah:.3f} Ah za {fmt_dur(time.time() - t0)}")
    return ah
