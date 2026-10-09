"""Charge tab: battery profiles and validation; builds a lib_batt script for ScriptRunner.

The UI fills the form from PROFILES and sends the final values; build() checks them against the
chemistry and the PSU limits and returns a summary for the confirmation dialog plus the script code.
"""
import re

PSU_V_MAX = 30.0
PSU_I_MAX = 5.0

# per-cell values; c_* are multiples of the capacity
PROFILES = {
    "liion": {
        "label": "Li-ion (18650, 21700 …)", "method": "cccv",
        "cells": 1, "cells_max": 7, "capacity": 2500, "c_rate": 0.5, "c_max": 1.0, "cutoff_c": 0.05,
        "v_cell": 4.20, "v_range": [4.00, 4.20], "v_min": 2.5, "pre_v": 3.0, "pre_c": 0.1, "ah_pct": 120,
        "log": "liion",
        "hint": "4.20 V/cell = full; 4.10 V ≈ 90 % capacity but many more cycles. Cut-off C/20 like most chargers.",
        "models": {
            "cgr18650cg": {"label": "Panasonic CGR18650CG", "capacity": 2250, "c_rate": 0.667, "cutoff_c": 0.049,
                           "timeout_h": 4, "hint": "Datasheet: CC/CV 4.20 V, 0.7 It = 1.5 A, cut-off 110 mA, 0–45 °C."},
            "ur18650a": {"label": "Sanyo UR18650A", "capacity": 2250, "c_rate": 0.671, "cutoff_c": 0.049,
                         "timeout_h": 4.5, "hint": "Datasheet: CC/CV 4.20 V, 1.51 A (max 2.15 A), pre-charge below 3.0 V, 0–40 °C."},
        },
    },
    "lipo": {
        "label": "LiPo (RC packs)", "method": "cccv", "balancer": True,
        "cells": 1, "cells_max": 7, "capacity": 1000, "c_rate": 1.0, "c_max": 2.0, "cutoff_c": 0.1,
        "v_cell": 4.20, "v_range": [4.00, 4.20], "v_storage": 3.80, "v_min": 3.0, "pre_v": 3.3, "pre_c": 0.1,
        "ah_pct": 110, "log": "lipo",
        "hint": "1 C is the standard LiPo charge rate. Never charge a puffed pack; use a LiPo bag.",
    },
    "lihv": {
        "label": "LiHV (high-voltage LiPo)", "method": "cccv", "balancer": True,
        "cells": 1, "cells_max": 6, "capacity": 1000, "c_rate": 1.0, "c_max": 2.0, "cutoff_c": 0.1,
        "v_cell": 4.35, "v_range": [4.20, 4.35], "v_storage": 3.85, "v_min": 3.0, "pre_v": 3.3, "pre_c": 0.1,
        "ah_pct": 110, "log": "lihv",
        "hint": "Only for packs marked LiHV – 4.35 V/cell destroys a normal LiPo.",
    },
    "lifepo4": {
        "label": "LiFePO4", "method": "cccv",
        "cells": 4, "cells_max": 8, "capacity": 10000, "c_rate": 0.3, "c_max": 1.0, "cutoff_c": 0.05,
        "v_cell": 3.60, "v_range": [3.45, 3.65], "v_min": 2.0, "pre_v": 2.5, "pre_c": 0.05, "ah_pct": 120,
        "log": "lifepo4",
        "hint": "4S = \"12 V\" battery, 8S = \"24 V\". 3.50 V/cell is gentle (≈ 95 %).",
    },
    "lead": {
        "label": "Lead-acid (AGM, gel, flooded)", "method": "lead",
        "cells": 6, "cells_choices": [3, 6, 12], "capacity": 7200, "c_rate": 0.15, "c_max": 0.3, "cutoff_c": 0.02,
        "v_min": 1.75, "ah_pct": 130, "float_h": 2, "timeout_h": 16, "log": "lead_acid",
        "types": {
            # v_rec = recovery voltage limit, v_eq = reconditioning (equalisation) voltage, per cell
            "agm": {"label": "AGM", "v_cell": 2.40, "v_float": 2.267, "v_rec": 2.50, "v_rec_max": 2.55,
                    "v_eq": 2.55, "v_eq_max": 2.58},
            "gel": {"label": "Gel", "v_cell": 2.35, "v_float": 2.25, "v_rec": 2.42, "v_rec_max": 2.45,
                    "v_eq": None, "v_eq_max": None},
            "flooded": {"label": "Flooded (wet)", "v_cell": 2.43, "v_float": 2.25, "v_rec": 2.55, "v_rec_max": 2.65,
                        "v_eq": 2.62, "v_eq_max": 2.70},
            "caca": {"label": "Calcium Ca/Ca (car, maintenance-free)", "v_cell": 2.47, "v_float": 2.27, "v_rec": 2.55,
                     "v_rec_max": 2.65, "v_eq": 2.63, "v_eq_max": 2.70},
        },
        "v_range": [2.25, 2.50], "rec_c": 0.02, "eq_c": 0.03, "eq_h": 2,
        "hint": "Bulk (CC) → absorption (CV) → float. Car batteries are usually Ca/Ca (14.8 V). Below 1.75 V/cell (10.5 V for 12 V) the battery is deeply "
                "discharged – use Recovery. Reconditioning (equalisation) gasses: flooded batteries, AGM only "
                "occasionally, never gel.",
    },
    "nimh": {
        "label": "NiMH / NiCd", "method": "nimh",
        "cells": 4, "cells_max": 18, "capacity": 2000, "c_rate": 0.5, "c_max": 1.0, "v_cell_max": 1.60,
        "ah_pct": 130, "log": "nimh",
        "types": {"nimh": {"label": "NiMH", "dv": 0.005}, "nicd": {"label": "NiCd", "dv": 0.012}},
        "hint": "Fast = constant current with −ΔV end (reliable from ~4 cells). Slow = 0.1 C for 14 h, safe for any count.",
    },
}


# full charge from empty ≈ factor × capacity / current (CC part + slower CV / absorption tail)
EST_FACTOR = {"liion": 1.3, "lipo": 1.3, "lihv": 1.3, "lifepo4": 1.2, "lead": 1.5, "nimh": 1.2}
STORAGE_FACTOR = 0.55   # empty -> storage voltage


def _dur(h):
    m = round(h * 60)
    return f"{m} min" if m < 90 else f"{m // 60} h {m % 60:02d} min"


# Rough rest voltage [V/cell] -> state of charge [%] for the estimate in the UI (the PSU has no fuel gauge);
# eff = charge efficiency for counting Ah into %, cv_at = state of charge when CC turns into CV (at ~0.5 C)
SOC = {
    "liion": {"ocv": [[3.0, 0], [3.3, 5], [3.5, 10], [3.6, 20], [3.7, 35], [3.75, 45], [3.8, 55], [3.9, 68], [4.0, 80], [4.1, 90], [4.2, 100]],
              "eff": 0.98, "cv_at": 80},
    "lihv": {"ocv": [[3.0, 0], [3.3, 5], [3.5, 10], [3.6, 18], [3.7, 30], [3.8, 50], [3.9, 62], [4.0, 73], [4.1, 83], [4.2, 91], [4.35, 100]],
             "eff": 0.98, "cv_at": 80},
    "lifepo4": {"ocv": [[2.5, 0], [3.0, 5], [3.2, 15], [3.25, 30], [3.3, 60], [3.33, 80], [3.4, 95], [3.6, 100]],
                "eff": 0.98, "cv_at": 90},
    "lead": {"ocv": [[1.95, 0], [2.0, 20], [2.05, 40], [2.1, 65], [2.13, 85], [2.15, 100]], "eff": 0.85, "cv_at": 80},
    "nimh": {"ocv": [[1.0, 0], [1.2, 20], [1.25, 40], [1.3, 70], [1.4, 95], [1.45, 100]], "eff": 0.8, "cv_at": 100},
}
SOC["lipo"] = SOC["liion"]
for _k, _p in PROFILES.items():
    _p["soc"] = SOC[_k]


class ChargeError(ValueError):
    pass


def _num(p, key, default=None, lo=None, hi=None, label=None, integer=False):
    v = p.get(key, default)
    if v in (None, ""):
        v = default
    try:
        v = int(v) if integer else float(v)
    except (TypeError, ValueError):
        raise ChargeError(f"{label or key}: not a number")
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise ChargeError(f"{label or key} must be between {lo:g} and {hi:g}")
    return v


def _r(x, n=3):
    return round(x + 0.0, n)


def _cap(ah):
    return f"{ah:g} Ah" if ah >= 10 else f"{ah * 1000:g} mAh"


def build(p):
    """p = form values. Returns {name, code, summary: [[label, value]], warnings: [..]}; raises ChargeError."""
    chem = p.get("chem")
    if chem not in PROFILES:
        raise ChargeError("Choose the battery type")
    pr = PROFILES[chem]
    warn = []
    if pr.get("cells_choices"):
        cells = _num(p, "cells", pr["cells"], 1, 24, "Cells", integer=True)
        if cells not in pr["cells_choices"]:
            raise ChargeError("Cells: " + " / ".join(f"{c} ({c * 2} V)" for c in pr["cells_choices"]))
    else:
        cells = _num(p, "cells", pr["cells"], 1, pr["cells_max"], "Cells in series", integer=True)
    cap = _num(p, "capacity_mah", pr["capacity"], 10, 500000, "Capacity [mAh]") / 1000
    log = re.sub(r"[^A-Za-z0-9_-]", "_", str(p.get("log") or "").strip())[:40] or None
    ah_pct = _num(p, "ah_pct", pr["ah_pct"], 100, 200, "Capacity limit [%]")
    ah_max = _r(cap * ah_pct / 100, 3)
    timeout = p.get("timeout_h")
    timeout = None if timeout in (None, "", 0, "0") else _num(p, "timeout_h", None, 0.1, 48, "Time limit [h]")

    if pr["method"] == "nimh":
        typ = pr["types"].get(p.get("nimh_type") or "nimh")
        if not typ:
            raise ChargeError("Choose NiMH or NiCd")
        slow = p.get("mode") == "slow"
        c_rate = 0.1 if slow else _num(p, "c_rate", pr["c_rate"], 0.05, pr["c_max"], "Charge rate [C]")
        i_charge = cap * c_rate
        v_ceiling = cells * pr["v_cell_max"]
        if v_ceiling > PSU_V_MAX:
            raise ChargeError(f"{cells} cells need up to {v_ceiling:.1f} V – the PSU gives max {PSU_V_MAX:g} V")
        if i_charge > PSU_I_MAX:
            warn.append(f"Charge current {i_charge:.2f} A limited to {PSU_I_MAX:g} A (PSU maximum)")
            i_charge = PSU_I_MAX
        if not slow and cells < 4:
            warn.append("Fewer than 4 cells: −ΔV is hard to detect with 10 mV resolution – Slow mode is safer")
        timeout = timeout or (14.0 if slow else _r(1.5 / c_rate + 0.5, 1))
        if slow:
            ah_max = max(ah_max, _r(cap * 1.5))
        name = f"{typ['label']} {cells} cells {_cap(cap)} {'slow 0.1 C' if slow else f'{c_rate:g} C'}"
        kw = dict(i_charge=_r(i_charge), dv_per_cell=1.0 if slow else typ["dv"], v_cell_max=pr["v_cell_max"],
                  timeout_h=timeout, ah_max=ah_max, log_name=log, name=name)
        if not slow:
            kw.update(blank_min=5, i_trickle=_r(cap * 0.05), trickle_min=30)
        code = _code("nimh_charge", f"psu, {cells}", kw)
        est = 14.0 if slow else EST_FACTOR["nimh"] * cap / i_charge + 0.5
        targets = {"method": "nimh", "v_max": _r(v_ceiling, 2), "i_charge": _r(i_charge), "i_term": None}
        summary = [
            ["Battery", name],
            ["Method", "0.1 C for a fixed time" if slow else f"CC with −ΔV end ({typ['dv'] * 1000:g} mV/cell), then 0.05 C top-off 30 min"],
            ["Charge current", f"{i_charge:.3f} A"],
            ["Voltage ceiling", f"{v_ceiling:.2f} V ({pr['v_cell_max']:.2f} V/cell)"],
        ]
    else:
        c_rate = _num(p, "c_rate", pr["c_rate"], 0.02, pr["c_max"], "Charge rate [C]")
        cutoff_c = _num(p, "cutoff_c", pr["cutoff_c"], 0.005, 0.5, "Cut-off [C]")
        if pr["method"] == "lead":
            typ = pr["types"].get(p.get("lead_type") or "agm")
            if not typ:
                raise ChargeError("Choose the lead-acid type")
            v_cell = _num(p, "v_cell", typ["v_cell"], *pr["v_range"], "Absorption voltage [V/cell]")
            v_float = _num(p, "v_float", typ["v_float"], 2.15, 2.35, "Float voltage [V/cell]")
            float_h = _num(p, "float_h", pr["float_h"], 0, 48, "Float time [h]")
            lead_mode = p.get("mode") if p.get("mode") in ("recover", "recond") else "normal"
            if lead_mode != "normal":
                rec_c = _num(p, "rec_c", pr["rec_c"], 0.005, 0.1, "Recovery current [C]")
                v_rec = _num(p, "v_rec", typ["v_rec"], 2.30, typ["v_rec_max"], "Recovery voltage limit [V/cell]")
            if lead_mode == "recond":
                if not typ["v_eq"]:
                    raise ChargeError("Gel batteries must not be reconditioned (equalised) – the high voltage destroys them")
                eq_c = _num(p, "eq_c", pr["eq_c"], 0.01, 0.1, "Reconditioning current [C]")
                v_eq = _num(p, "v_eq", typ["v_eq"], 2.45, typ["v_eq_max"], "Reconditioning voltage [V/cell]")
                eq_h = _num(p, "eq_h", pr["eq_h"], 0.5, 8, "Reconditioning time [h]")
            mode_label = f"{typ['label']} {cells * 2} V" + {"normal": "", "recover": " recovery",
                                                            "recond": " recovery + reconditioning"}[lead_mode]
        else:
            storage = p.get("mode") == "storage" and pr.get("v_storage")
            if storage:
                v_cell = pr["v_storage"]
            else:
                v_cell = _num(p, "v_cell", pr["v_cell"], *pr["v_range"], "End voltage [V/cell]")
            if pr.get("balancer") and cells > 1 and not p.get("balancer"):
                raise ChargeError(f"{cells}S pack: the PSU cannot balance cells – connect a balancer / BMS and confirm it")
            mode_label = ("storage " if storage else "") + f"{cells}S"
        v_max = _r(cells * v_cell, 2)
        if v_max > PSU_V_MAX:
            raise ChargeError(f"{v_max:.2f} V is above the PSU maximum {PSU_V_MAX:g} V – fewer cells")
        i_charge = cap * c_rate
        if i_charge > PSU_I_MAX:
            warn.append(f"Charge current {i_charge:.2f} A limited to {PSU_I_MAX:g} A (PSU maximum)")
            i_charge = PSU_I_MAX
        i_term = max(0.01, cap * cutoff_c)
        if i_term >= i_charge:
            raise ChargeError("Cut-off current must be lower than the charge current")
        if not timeout and pr["method"] == "lead":
            # current-limited big batteries (e.g. 72 Ah at 5 A) need longer than the default 16 h
            timeout = max(pr["timeout_h"], round(1.3 * 1.5 * cap / i_charge))
        timeout = timeout or pr.get("timeout_h") or max(2.0, _r(1.5 / (i_charge / cap) + 1, 1))
        v_min = _r(cells * pr["v_min"], 2)
        label = PROFILES[chem]["label"].split(" (")[0]
        model = (pr.get("models") or {}).get(p.get("model") or "")
        if model:
            label = model["label"]
        name = f"{label} {mode_label} {_cap(cap)}"
        kw = dict(v_max=v_max, i_charge=_r(i_charge), i_term=_r(i_term), timeout_h=timeout, v_min=v_min)
        if pr.get("pre_v"):
            kw.update(precharge_v=_r(cells * pr["pre_v"], 2), precharge_i=_r(max(0.02, cap * pr["pre_c"])))
        kw.update(ah_max=ah_max, log_name=log, name=name)
        summary = [
            ["Battery", name],
            ["End voltage", f"{v_max:.2f} V ({v_cell:.3g} V/cell)"],
            ["Charge current", f"{i_charge:.3f} A ({i_charge / cap:.2g} C)"],
            ["Done when current <", f"{i_term:.3f} A"],
        ]
        if pr.get("pre_v"):
            summary.append(["Pre-charge", f"below {kw['precharge_v']:.2f} V with {kw['precharge_i']:.3f} A"])
        storage = pr["method"] == "cccv" and p.get("mode") == "storage" and pr.get("v_storage")
        est = (STORAGE_FACTOR if storage else EST_FACTOR[chem]) * cap / i_charge
        targets = {"method": "cccv", "v_max": v_max, "i_charge": _r(i_charge), "i_term": _r(i_term),
                   "v_cell": v_cell, "storage": bool(storage)}
        if pr["method"] == "lead":
            est += float_h
            targets.update(float_h=float_h, lead_mode=lead_mode)
            sub = lambda name: f"{log}_{name}" if log else None   # noqa: E731
            pre, post = "", ""
            if lead_mode != "normal":
                i_rec = _r(max(0.02, min(PSU_I_MAX, cap * rec_c)))
                pre = (f"# recovery decides itself: 'ok' -> normal charging, 'full' -> skip charging,\n"
                       f"# otherwise small current until the battery recovers (rest voltage + charging test every 10 min)\n"
                       f"state = lead_recover(psu, {cells}, {i_rec!r}, v_charge={v_max!r}, i_charge={kw['i_charge']!r}, "
                       f"v_limit_cell={v_rec!r}, v_ok_cell=1.80, log_name={sub('recovery')!r})\n\n")
                summary.insert(1, ["Recovery", f"first a check: rest voltage ≥ {cells * 1.80:.2f} V and it takes current at "
                                                f"{v_max:.2f} V → normal charging; full → charging skipped; otherwise "
                                                f"{i_rec:.3f} A up to {cells * v_rec:.2f} V until it recovers "
                                                f"(max 24 h, aborts if no current is taken for 3 h)"])
                warn.append("Recovery time depends on the battery (hours, up to 24 h) – not included in the estimate")
            if lead_mode == "recond":
                i_eq = _r(max(0.02, min(PSU_I_MAX, cap * eq_c)))
                post = (f"lead_equalize(psu, {_r(cells * v_eq, 2)!r}, {i_eq!r}, {eq_h!r}, "
                        f"log_name={sub('recond')!r})\n")
                summary.append(["Reconditioning", f"{i_eq:.3f} A up to {cells * v_eq:.2f} V for {eq_h:g} h"])
                est += eq_h
                targets["eq_h"] = eq_h
                warn.append("Reconditioning gasses: ventilate, keep sparks away, stop if the battery gets warm; "
                            "flooded – check the electrolyte level afterwards")
            imports = ["cccv_charge", "float_stage"] + (["lead_recover"] if pre else []) + (["lead_equalize"] if post else [])
            code = _code("cccv_charge", "psu", kw, extra=", ".join(imports))
            if pre:   # charge only when the battery is not already full
                head, call = code.split("\ncccv_charge(", 1)
                call = "cccv_charge(" + call
                code = head + "\n" + pre + 'if state != "full":\n' + "".join("    " + l + "\n" for l in call.rstrip("\n").split("\n"))
            code += post
            if float_h > 0:
                code += (f"float_stage(psu, {_r(cells * v_float, 2)!r}, {kw['i_charge']!r}, {float_h!r}, "
                         f"log_name={sub('float')!r})\n")
                summary.append(["Float", f"{cells * v_float:.2f} V for {float_h:g} h"])
        else:
            code = _code("cccv_charge", "psu", kw)
            if p.get("mode") == "storage":
                warn.append("Storage: the PSU cannot discharge – a pack already above storage voltage is left as it is")
    est = min(est, timeout)
    summary.append(["Estimated time", f"≈ {_dur(est)} from empty (less if partly charged)"])
    targets.update(cap_ah=_r(cap, 3), timeout_h=timeout, est_h=_r(est, 2), chem=chem, cells=cells, soc=SOC[chem])
    summary += [
        ["Start only above", "any voltage – recovery first" if targets.get("lead_mode", "normal") != "normal"
         else f"{_r(cells * pr['v_min'], 2):.2f} V" if pr.get("v_min") else "0.9 V/cell"],
        ["Time limit", f"{timeout:g} h"],
        ["Capacity limit", f"{ah_max:g} Ah ({ah_pct:g} %)"],
        ["CSV log", log or "off"],
    ]
    return {"name": name, "code": code, "summary": summary, "warnings": warn, "targets": targets}


def _code(fn, first, kw, extra=None):
    args = "".join(f"    {k}={v!r},\n" for k, v in kw.items())
    return (f"# Charging – generated by the Charge tab\n"
            f"from lib_batt import {extra or fn}\n\n"
            f"{fn}(\n    {first},\n{args})\n")
