# Measures load current at different voltages (e.g. an I-V curve).
# The output is switched off automatically on error or stop (psu.safe_off = True).
voltages = [1, 2, 3, 4, 5, 6, 8, 10, 12]
psu.set_i(2.0)        # current limit
psu.set_v(0)
psu.on()
print("U_set | U_out | I_out | P")
for u in voltages:
    psu.set_v(u)
    psu.wait(1.5)     # settling
    st = psu.status()
    mode = "CV" if st["cv"] else "CC"
    print(f"{u:5.1f} | {psu.vout:5.2f} | {psu.iout:5.3f} | {psu.power:6.2f}  {mode}")
psu.off()
