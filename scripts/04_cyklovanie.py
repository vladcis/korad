# Cyklické zapínanie/vypínanie výstupu (napr. test štartu zariadenia).
cykly = 5
psu.set_v(12)
psu.set_i(1.0)
for n in range(1, cykly + 1):
    psu.on()
    psu.wait(3)
    print(f"cyklus {n}: I = {psu.iout:.3f} A")
    psu.off()
    psu.wait(2)
print("koniec")
