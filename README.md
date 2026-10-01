# KORAD KA3005P/PS – webové / desktop ovládanie

Lokálne GUI pre laboratórny zdroj KORAD KA3005P, KA3005PS (a kompatibilné Tenma 72-2535, RND 320-KA3005P…)
pripojený cez USB. Jeden kód beží ako lokálny web server alebo ako desktop aplikácia (Linux / macOS / Windows).

## Funkcie
- **Panel** v štýle predného panelu zdroja: 7-segmentový displej U / I / P, indikátory CV, CC, OCP, OVP, ON, LOCK
- nastavenie U a I (číselne, posuvník, krokovanie), ON/OFF, OCP, OVP, BEEP, A/mA, pamäte M1–M5 (vyvolať / uložiť)
- 6 predvolieb U/I (ako v originálnom programe), živý graf U / I / P
- **Program** – programovateľný test: tabuľka krokov U / I / čas, začiatočný a koncový bod, počet cyklov (0 = nekonečne)
- **Skripty** – Python skripty s objektom `psu` (ukladať, editovať, spúšťať, zastaviť), výstup v reálnom čase
- **Logy** – CSV logovanie U/I/P s nastaviteľným intervalom, prehliadanie grafom aj tabuľkou, sťahovanie
- **Konzola** – priame príkazy zdroju (`VSET1:05.00`, `STATUS?`…), história príkazov a udalostí
- automatické znovupripojenie po výpadku USB

## Spustenie – web server
```sh
pip install -r requirements.txt       # flask, pyserial
python3 app.py                        # http://127.0.0.1:8585
python3 app.py --port 9000 --device /dev/ttyACM0 --host 0.0.0.0   # voliteľné
```
Na Windows je port napr. `--device COM5`, na macOS `/dev/cu.usbmodemXXXX`. Bez `--device` sa zdroj nájde automaticky.

## Spustenie – desktop aplikácia
```sh
pip install pywebview               # Linux navyše: sudo apt install python3-gi gir1.2-webkit2-4.1
python3 desktop.py                  # otvorí natívne okno
python3 desktop.py --browser        # alebo len prehliadač
```
Zabalenie do jedného súboru (na každom OS zvlášť):
```sh
pip install pyinstaller
pyinstaller --onefile --add-data "static:static" --name korad desktop.py     # Windows: "static;static"
```

## Linux – práva a ModemManager
```sh
sudo usermod -aG dialout $USER      # prístup k /dev/ttyACM0 (odhlásiť/prihlásiť)
sudo cp 99-korad.rules /etc/udev/rules.d/ && sudo udevadm control --reload && sudo udevadm trigger
```
Pravidlo zabráni ModemManageru, aby zdroj skúšal ako modem, a vytvorí symlink `/dev/korad`.

## Skriptovanie
Skripty sú v `scripts/*.py`, bežia vo vlákne servera. Dostupné: `psu`, `print`/`log`, `time`, `math`.

| volanie | význam |
|---|---|
| `psu.set_v(12.0)`, `psu.set_i(0.5)`, `psu.set(volts=, amps=)` | nastavenie U [V], I [A] |
| `psu.on()`, `psu.off()`, `psu.output(bool)` | výstup |
| `psu.vout`, `psu.iout`, `psu.power`, `psu.vset`, `psu.iset` | meranie / nastavené hodnoty |
| `psu.status()` | `{"cv","ocp","ovp","output","beep"}` |
| `psu.wait(s)` (= `time.sleep`) | pauza, dá sa prerušiť tlačidlom Stop |
| `psu.ramp_v(od, do, trvanie, step)`, `psu.ramp_i(...)` | lineárna rampa |
| `psu.ocp(b)`, `psu.ovp(b)`, `psu.beep(b)`, `psu.save(n)`, `psu.recall(n)` | funkcie, pamäte 1–5 |
| `psu.log_start("nazov", interval)`, `psu.log_stop()` | CSV logovanie |
| `psu.raw("VSET1:05.00")`, `psu.raw("STATUS?", 1)` | ľubovoľný príkaz |
| `psu.safe_off = False` | nevypínať výstup pri chybe / zastavení (predvolene sa vypne) |

### Nabíjanie batérií
Skripty `10_`–`15_` používajú knižnicu `scripts/lib_batt.py` (`cccv_charge`, `nimh_charge`, `float_stage`).
Parametre (počet článkov, kapacita, C-rate, koncové napätie) sú na začiatku každého skriptu.

| skript | chémia | metóda |
|---|---|---|
| `10_nabijanie_liion.py` | Li-ion / LiPo 1S–7S | prednabíjanie → CC → CV, koniec pri C/20 |
| `11_nabijanie_lifepo4.py` | LiFePO4 (4S = 12 V) | CC → CV 3.60 V/čl., koniec pri C/20 |
| `12_nabijanie_olovo.py` | Pb 12 V (AGM, gél, klasická) | bulk → absorpcia 14.4 V → float 13.6 V |
| `13_nabijanie_nimh.py` | NiMH / NiCd | CC s ukončením −ΔV, alebo pomalé 0.1 C na čas |
| `14_nabijanie_vlastne.py` | čokoľvek | CC/CV s ručnými hodnotami |
| `15_test_kapacity_info.py` | – | len zmeria napätie batérie |

Knižnica pred štartom overí, že batéria je pripojená a má napätie v rozumnom rozsahu, počíta nabité Ah,
hlási prechod CC → CV a vypne výstup pri časovom limite, prekročení kapacity, chybe alebo tlačidle Stop.
Zdroj nemeria teplotu – nabíjaj pod dozorom, skontroluj polaritu a počet článkov. Skripty vo `scripts/`
môžu importovať vlastné knižnice `lib_*.py` z toho istého priečinka (načítajú sa nanovo pri každom behu).

## Protokol zdroja (pre konzolu)
`*IDN?`, `STATUS?` (bajt: bit0 CV/CC, bit4 beep, bit5 OCP, bit6 výstup, bit7 OVP), `VSET1:xx.xx`, `VSET1?`,
`ISET1:x.xxx`, `ISET1?`, `VOUT1?`, `IOUT1?`, `OUT0/1`, `OCP0/1`, `OVP0/1`, `BEEP0/1`, `SAV1-5`, `RCL1-5`.
9600 Bd, bez ukončovacieho znaku. Zdroj potrebuje ~50–100 ms medzi príkazmi; driver to rieši sám.

## Štruktúra
```
app.py        Flask server, REST API, SSE stream, polling zdroja
korad.py      sériový driver (autodetekcia portu, Linux/macOS/Windows)
scripting.py  spúšťanie skriptov (objekt psu)
sequencer.py  programovateľný test -> skript
datalog.py    CSV logovanie + udalosti
desktop.py    desktop okno (pywebview)
static/       HTML / CSS / JS
scripts/      používateľské skripty      data/  predvoľby a sekvencie      logs/  CSV logy
```
