# Cycles the output on/off (e.g. a device start-up test).
cycles = 5
psu.set_v(12)
psu.set_i(1.0)
for n in range(1, cycles + 1):
    psu.on()
    psu.wait(3)
    print(f"cycle {n}: I = {psu.iout:.3f} A")
    psu.off()
    psu.wait(2)
print("finished")
