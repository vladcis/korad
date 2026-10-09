"""Library for charging batteries with a KORAD lab power supply (CC/CV, −ΔV, float, lead-acid recovery).

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
    v = _rest_voltage(psu, 0, 3)      # rest voltage (no current) – under current a high-resistance battery reads high
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
            if below >= term_count and el < 120 and ah < max(0.005, 0.01 * (ah_max or 0)):
                # at the end voltage at once with almost no charge: not "full" but a battery that takes no current
                rest = _rest_voltage(psu, i_term, 5)
                raise ChargeAbort(f"The battery took almost no current ({ah:.3f} Ah) and was at {v_max:.2f} V at once "
                                  f"(rest voltage {rest:.2f} V). If it is not already full, its internal resistance is "
                                  "too high – lead-acid: sulfated / deeply discharged, use the Recovery mode; "
                                  "other types: a damaged cell.")
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


def _rest_voltage(psu, i_back, rest_s):
    """Current to 0 for rest_s seconds and returns the battery rest voltage (the PSU cannot sink current)."""
    psu.set_i(0)
    psu.wait(rest_s)
    v = psu.vout
    psu.set_i(i_back)
    return v


def _takes_current(psu, v, i, secs=30.0):
    """Charging test: v / i for secs seconds, returns the current the battery takes at the end."""
    psu.set_v(v)
    psu.set_i(i)
    psu.wait(secs)
    return psu.iout


def lead_recover(psu, cells, i_rec, *, v_charge, i_charge, v_limit_cell=2.50, v_ok_cell=1.80, v_full_cell=2.12,
                 check_min=10.0, rest_s=60.0, timeout_h=24.0, no_accept_h=3.0, interval=5.0, report_every=300,
                 log_name=None):
    """Recovery of a deeply discharged / sulfated lead-acid battery before normal charging.

    First decides from the rest voltage and a 30 s charging test at v_charge / i_charge:
      - rest ≥ v_ok_cell and the battery takes ≥ 50 % of i_charge  -> "ok" (normal charging, no recovery)
      - rest ≥ v_full_cell and it takes almost nothing             -> "full" (skip charging)
      - otherwise recovery: small constant current i_rec with a raised voltage limit (v_limit_cell); a
        sulfated battery takes almost no current at first, then more as the sulfate dissolves. Every
        check_min minutes the rest voltage is measured and the charging test repeated; when the battery
        passes both it is "recovered". Aborts when it takes no current for no_accept_h hours, or after timeout_h.
    Returns "ok", "full" or "recovered".
    """
    v_limit, v_ok, v_full = cells * v_limit_cell, cells * v_ok_cell, cells * v_full_cell
    _check_limits(v_limit, max(i_rec, i_charge))
    accept = 0.5 * i_charge
    psu.off()
    psu.set_v(v_limit)
    psu.set_i(0)
    psu.on()
    psu.wait(5)
    v0 = psu.vout
    if v0 < 1.0:
        psu.off()
        raise ChargeAbort(f"No battery on the output (or an open cell): {v0:.2f} V")
    i0 = _takes_current(psu, v_charge, i_charge)
    if v0 >= v_ok and i0 >= accept:
        say(psu, f"Battery OK – rest {v0:.2f} V, takes {i0:.3f} A at {v_charge:.2f} V – normal charging, no recovery")
        psu.off()
        return "ok"
    if v0 >= v_full and i0 < accept:
        say(psu, f"Battery is full – rest {v0:.2f} V, takes only {i0:.3f} A at {v_charge:.2f} V – charging skipped")
        psu.off()
        return "full"
    why = "deeply discharged" if v0 < v_ok else f"takes only {i0:.3f} A at {v_charge:.2f} V (high resistance / sulfated)"
    say(psu, f"=== Recovery: {v0:.2f} V, {why}; {i_rec:.3f} A up to {v_limit:.2f} V ===")
    psu.set_v(v_limit)
    psu.set_i(i_rec)
    if log_name:
        psu.log_start(log_name, interval)
    t0 = last = last_accept = last_check = time.time()
    ah, last_report = 0.0, 0.0
    try:
        while True:
            psu.wait(interval)
            now = time.time()
            v, i, st = psu.vout, psu.iout, psu.status()
            ah += i * (now - last) / 3600
            last = now
            el = now - t0
            if not st["output"]:
                raise ChargeAbort("PSU output switched off (OCP/OVP or manually)")
            if i >= 0.5 * i_rec:
                last_accept = now
            elif now - last_accept > no_accept_h * 3600:
                raise ChargeAbort(f"The battery has taken no current for {no_accept_h:g} h at {v:.2f} V – "
                                  "it is probably beyond recovery (heavy sulfation or a dead cell)")
            if now - last_check >= check_min * 60:
                rest = _rest_voltage(psu, i_rec, rest_s)
                takes = _takes_current(psu, v_charge, i_charge)
                psu.set_v(v_limit)
                psu.set_i(i_rec)
                last_check = last = time.time()
                say(psu, f"[{fmt_dur(el)}] recovery  rest {rest:.2f} V, takes {takes:.3f} A at {v_charge:.2f} V  ({ah:.3f} Ah)")
                if rest >= v_ok and takes >= accept:
                    say(psu, f"[{fmt_dur(el)}] RECOVERED – rest {rest:.2f} V, takes {takes:.3f} A – normal charging follows")
                    return "recovered"
            if el > timeout_h * 3600:
                raise ChargeAbort(f"Recovery time limit {timeout_h:g} h – the battery did not recover")
            if el - last_report >= report_every:
                say(psu, f"[{fmt_dur(el)}] recovery  U={v:.2f} V  I={i:.3f} A  ({ah:.3f} Ah)")
                last_report = el
    finally:
        psu.off()
        if log_name:
            psu.log_stop()


def lead_equalize(psu, v_eq, i_eq, hours, *, interval=5.0, report_every=300, log_name=None):
    """Reconditioning / equalisation after a full charge: constant current i_eq (≈ C/30) limited to v_eq
    for the given time. Mixes the electrolyte and converts remaining sulfate. Flooded batteries;
    AGM only occasionally and at a lower voltage; NEVER gel. The battery gasses – ventilate, and stop if
    it gets warm. Returns the charged Ah."""
    _check_limits(v_eq, i_eq)
    say(psu, f"=== Reconditioning {i_eq:.3f} A up to {v_eq:.2f} V for {hours:g} h ===")
    psu.off()
    psu.set_v(v_eq)
    psu.set_i(i_eq)
    psu.on()
    if log_name:
        psu.log_start(log_name, interval)
    t0 = last = time.time()
    ah, last_report = 0.0, 0.0
    try:
        while True:
            psu.wait(interval)
            now = time.time()
            v, i, st = psu.vout, psu.iout, psu.status()
            ah += i * (now - last) / 3600
            last = now
            el = now - t0
            if not st["output"]:
                raise ChargeAbort("PSU output switched off (OCP/OVP or manually)")
            if el >= hours * 3600:
                break
            if el - last_report >= report_every:
                say(psu, f"[{fmt_dur(el)}] recond  U={v:.2f} V  I={i:.3f} A  ({ah:.3f} Ah)")
                last_report = el
    finally:
        psu.off()
        if log_name:
            psu.log_stop()
    say(psu, f"Reconditioning finished, {ah:.3f} Ah")
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
