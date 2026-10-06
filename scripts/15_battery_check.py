# Battery state check without charging: switches the output on at the set voltage with a small current
# and prints the battery voltage (the supply cannot discharge; measure capacity while charging – it is printed in Ah).
V_MAX = 4.2      # safe ceiling for the battery type (Li-ion 1S 4.2, Pb 12 V 14.4, …)
psu.set_i(0.02)
psu.set_v(V_MAX)
psu.on()
psu.wait(2)
st = psu.status()
print(f"Battery voltage: {psu.vout:.2f} V, current {psu.iout:.3f} A, mode {'CV' if st['cv'] else 'CC'}")
if st["cv"] and psu.iout < 0.01:
    print("-> no battery on the output, or it is completely full")
psu.off()
