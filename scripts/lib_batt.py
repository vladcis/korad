"""Library for charging batteries with a KORAD lab power supply (CC/CV, −ΔV, float charging).

Usage in a script:  from lib_batt import *

SAFETY – a lab power supply is not a charger:
 - check polarity and the correct cell count BEFORE starting
 - never leave charging unattended; charge Li-ion/LiPo on a non-flammable surface
 - the PSU does not measure battery temperature; if the battery gets warm, stop charging (Stop button)
 - with the output off, current can flow back from the battery into the PSU; for long connections add a series Schottky diode
 - if a cell drops below its minimum voltage (e.g. Li-ion < 2.5 V), it is probably damaged – do not charge it
"""
import time

PSU_V_MAX = 30.0
PSU_I_MAX = 5.0


class ChargeAbort(Exception):
    """Charging safely aborted (the output is off)."""


def say(psu, *args):
    """Prints to the script output in the UI (print from the library would only go to the server console)."""
    getattr(psu, "log", print)(*args)


def fmt_dur(sec):
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _check_limits(v_max, i_charge):
    if not 0 < v_max <= PSU_V_MAX:
        raise ChargeAbort(f"Voltage {v_max} V is outside the PSU range (0–{PSU_V_MAX} V)")
    if not 0 < i_charge <= PSU_I_MAX:
        raise ChargeAbort(f"Current {i_charge} A is outside the PSU range (0–{PSU_I_MAX} A)")


def probe_battery(psu, v_max, i_probe=0.05, settle=2.0):
    """Switches the output on with a small current and returns (battery voltage, current, status). Detects a missing battery."""
    psu.off()
    psu.set_i(min(i_probe, PSU_I_MAX))
    psu.set_v(v_max)
    psu.on()
    psu.wait(settle)
    v, i, st = psu.vout, psu.iout, psu.status()
    return v, i, st


def cccv_charge(psu, v_max, i_charge, i_term, timeout_h=8.0, *, v_min=0.0, precharge_v=None, precharge_i=None,
                ah_max=None, interval=2.0, report_every=30, log_name=None, name="battery", term_count=3):
    """CC/CV charging. Returns the charged capacity [Ah].

    v_max       end-of-charge voltage (CV phase) [V]
    i_charge    charge current (CC phase) [A]
    i_term      cut-off current – done when the current in the CV phase drops below this value [A]
    timeout_h   safety time limit [h]
    v_min       charging does not start if the battery is below this voltage (deeply discharged / wrong polarity / wrong cell count)
    precharge_v, precharge_i   below precharge_v charge with the small current precharge_i (Li-ion below 3.0 V/cell)
    ah_max      safety limit on charged capacity [Ah] (e.g. 1.2 × capacity)
    log_name    CSV log name (None = no logging)
    """
    _check_limits(v_max, i_charge)
    say(psu, f"=== Charging: {name} ===")
    say(psu, f"CV {v_max:.2f} V, CC {i_charge:.3f} A, cut-off at {i_term:.3f} A, limit {timeout_h:g} h"
          + (f", max {ah_max:g} Ah" if ah_max else ""))

    v, i, st = probe_battery(psu, v_max)
    if st["cv"] and i < 0.01:
        psu.off()
        raise ChargeAbort(f"No battery on the output, or it is already full (U={v:.2f} V, I={i:.3f} A)")
    if v < v_min:
        psu.off()
        raise ChargeAbort(f"Battery voltage {v:.2f} V is below the minimum {v_min:.2f} V – check polarity, cell count or battery condition")
    say(psu, f"Battery: {v:.2f} V")

    if log_name:
        psu.log_start(log_name, interval)
    t0 = time.time()
    last = t0
    ah = 0.0
    try:
        if precharge_v and precharge_i and v < precharge_v:
            say(psu, f"Precharging at {precharge_i:.3f} A up to {precharge_v:.2f} V …")
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
                    raise ChargeAbort("Precharge is taking more than 1 h – the battery is probably damaged")
            say(psu, f"[{fmt_dur(now - t0)}] precharged to {v:.2f} V")

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
                raise ChargeAbort("PSU output switched off (OCP/OVP or manually)")
            new_phase = "CV" if st["cv"] else "CC"
            if new_phase != phase:
                say(psu, f"[{fmt_dur(el)}] {phase} → {new_phase} at {v:.2f} V, {i:.3f} A, charged {ah:.3f} Ah")
                phase = new_phase
            below = below + 1 if (phase == "CV" and i <= i_term) else 0
            if below >= term_count:
                say(psu, f"[{fmt_dur(el)}] DONE – current dropped below {i_term:.3f} A")
                break
            if el > timeout_h * 3600:
                raise ChargeAbort(f"Time limit {timeout_h:g} h – charging aborted (charged {ah:.3f} Ah)")
            if ah_max and ah > ah_max:
                raise ChargeAbort(f"Capacity limit {ah_max:g} Ah exceeded – charging aborted")
            if el - last_report >= report_every:
                say(psu, f"[{fmt_dur(el)}] {phase}  U={v:.2f} V  I={i:.3f} A  charged {ah:.3f} Ah")
                last_report = el
    finally:
        psu.off()
        if log_name:
            psu.log_stop()
    say(psu, f"Total charged {ah:.3f} Ah in {fmt_dur(time.time() - t0)}")
    return ah


def float_stage(psu, v_float, i_max, hours, *, interval=5.0, report_every=300, log_name=None):
    """Float charging at constant voltage for the given time [h]. Returns the charged Ah."""
    _check_limits(v_float, i_max)
    say(psu, f"=== Float {v_float:.2f} V, max {i_max:.3f} A, {hours:g} h ===")
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
                say(psu, f"[{fmt_dur(el)}] float  U={psu.vout:.2f} V  I={i:.3f} A  ({ah:.3f} Ah)")
                last_report = el
    finally:
        psu.off()
        if log_name:
            psu.log_stop()
    say(psu, f"Float finished, delivered {ah:.3f} Ah")
    return ah


def nimh_charge(psu, cells, i_charge, *, v_cell_max=1.60, dv_per_cell=0.005, blank_min=5.0, timeout_h=3.0,
                ah_max=None, v_min_cell=0.9, interval=2.0, report_every=30, log_name=None, name="NiMH",
                i_trickle=None, trickle_min=0):
    """NiMH/NiCd constant-current charging with −ΔV termination (voltage drop after the peak).

    cells        cells in series
    i_charge     charge current [A] (fast charge 0.5–1 C; better end a slow 0.1 C charge by time – timeout_h)
    v_cell_max   PSU voltage ceiling per cell [V]; charging ends when it is reached (CV)
    dv_per_cell  voltage drop per cell that ends charging [V]; the PSU measures in 10 mV steps,
                 so with < 4 cells use dv_per_cell=0.01 or more
    blank_min    minutes at the start during which −ΔV is ignored (the voltage rises first)
    i_trickle, trickle_min   optional small-current top-off after finishing (e.g. 0.05 C, 30 min)
    """
    v_max = cells * v_cell_max
    _check_limits(v_max, i_charge)
    dv = cells * dv_per_cell
    say(psu, f"=== Charging: {name}, {cells} cells, CC {i_charge:.3f} A, −ΔV {dv * 1000:.0f} mV, ceiling {v_max:.2f} V ===")
    v, i, st = probe_battery(psu, v_max)
    if st["cv"] and i < 0.01:
        psu.off()
        raise ChargeAbort(f"No battery on the output (U={v:.2f} V, I={i:.3f} A)")
    if v < cells * v_min_cell:
        psu.off()
        raise ChargeAbort(f"Voltage {v:.2f} V is below {cells * v_min_cell:.2f} V – wrong cell count or damaged battery")
    say(psu, f"Battery: {v:.2f} V ({v / cells:.3f} V/cell)")
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
                raise ChargeAbort("PSU output switched off")
            window.append(v)
            window = window[-5:]
            avg = sum(window) / len(window)
            if el > blank_min * 60:
                if avg > peak:
                    peak = avg
                elif peak - avg >= dv:
                    reason = f"−ΔV: peak {peak:.3f} V, now {avg:.3f} V"
                    break
            if st["cv"]:
                reason = f"voltage ceiling {v_max:.2f} V reached"
                break
            if el > timeout_h * 3600:
                reason = f"time limit {timeout_h:g} h"
                break
            if ah_max and ah > ah_max:
                reason = f"capacity limit {ah_max:g} Ah"
                break
            if el - last_report >= report_every:
                say(psu, f"[{fmt_dur(el)}] U={v:.2f} V ({v / cells:.3f}/cell)  I={i:.3f} A  peak {peak:.3f} V  {ah:.3f} Ah")
                last_report = el
        say(psu, f"[{fmt_dur(el)}] END – {reason}; charged {ah:.3f} Ah")
        if i_trickle and trickle_min:
            say(psu, f"Top-off {i_trickle:.3f} A for {trickle_min:g} min …")
            psu.set_i(i_trickle)
            t1 = time.time()
            while time.time() - t1 < trickle_min * 60:
                psu.wait(interval)
                ah += psu.iout * interval / 3600
    finally:
        psu.off()
        if log_name:
            psu.log_stop()
    say(psu, f"Total charged {ah:.3f} Ah in {fmt_dur(time.time() - t0)}")
    return ah
