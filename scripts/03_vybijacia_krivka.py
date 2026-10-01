# Meranie prúdu záťaže pri rôznych napätiach (napr. I-U charakteristika).
# Výstup sa pri chybe alebo zastavení automaticky vypne (psu.safe_off = True).
napatia = [1, 2, 3, 4, 5, 6, 8, 10, 12]
psu.set_i(2.0)        # prúdový limit
psu.set_v(0)
psu.on()
print("U_set | U_out | I_out | P")
for u in napatia:
    psu.set_v(u)
    psu.wait(1.5)     # ustálenie
    st = psu.status()
    mode = "CV" if st["cv"] else "CC"
    print(f"{u:5.1f} | {psu.vout:5.2f} | {psu.iout:5.3f} | {psu.power:6.2f}  {mode}")
psu.off()
