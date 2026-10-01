"""Programovateľný test (sekvencia krokov U/I/čas) – generuje skript pre ScriptRunner."""
import json


def sequence_code(steps, start=1, end=None, cycles=1):
    """steps: list of {"v":..,"i":..,"t":..}; start/end sú 1-based čísla krokov; cycles 0 = nekonečne."""
    clean = []
    for s in steps:
        try:
            clean.append((round(float(s.get("v", 0)), 2), round(float(s.get("i", 0)), 3), max(0.0, float(s.get("t", 1)))))
        except (TypeError, ValueError):
            continue
    if not clean:
        raise ValueError("Sekvencia nemá žiadne platné kroky")
    start = max(1, int(start or 1))
    end = min(len(clean), int(end or len(clean)))
    if end < start:
        raise ValueError("Koncový bod je pred začiatočným")
    cycles = max(0, int(cycles or 0))
    return f'''# Programovateľný test – vygenerované
steps = {json.dumps(clean)}
START, END, CYCLES = {start}, {end}, {cycles}   # CYCLES 0 = nekonečne
c = 0
psu.on()
while CYCLES == 0 or c < CYCLES:
    c += 1
    for k in range(START, END + 1):
        v, i, t = steps[k - 1]
        psu.set_v(v)
        psu.set_i(i)
        psu.wait(t)
        print(f"cyklus {{c}} krok {{k}}: {{v:.2f}} V / {{i:.3f}} A / {{t:g}} s -> U={{psu.vout:.2f}} V I={{psu.iout:.3f}} A")
psu.off()
print("sekvencia dokončená")
'''
