# Basic example: set 5 V / 0.5 A, switch on, measure, switch off.
psu.set_v(5.0)
psu.set_i(0.5)
psu.on()
psu.wait(2)
print(f"U = {psu.vout:.2f} V, I = {psu.iout:.3f} A, P = {psu.power:.2f} W")
psu.off()
