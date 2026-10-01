# Meranie stavu batérie bez nabíjania: zapne výstup na nastavené napätie s malým prúdom
# a vypíše napätie batérie (zdroj nevie vybíjať, kapacitu meraj počas nabíjania – vypisuje sa v Ah).
V_MAX = 4.2      # bezpečný strop pre daný typ (Li-ion 1S 4.2, Pb 12 V 14.4, …)
psu.set_i(0.02)
psu.set_v(V_MAX)
psu.on()
psu.wait(2)
st = psu.status()
print(f"Napätie batérie: {psu.vout:.2f} V, prúd {psu.iout:.3f} A, režim {'CV' if st['cv'] else 'CC'}")
if st["cv"] and psu.iout < 0.01:
    print("-> na výstupe nie je batéria alebo je úplne plná")
psu.off()
