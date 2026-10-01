"""Driver pre laboratórne zdroje KORAD KA3005P / KA3005PS (a kompatibilné) cez USB/RS232.

Protokol: 9600 8N1, textové príkazy bez ukončovacieho znaku, napr. "VSET1:12.34".
Stavový bajt (STATUS?): bit0 CV(1)/CC(0), bit4 beep, bit5 OCP, bit6 výstup, bit7 OVP.
"""
import threading
import time

import serial
from serial.tools import list_ports


class KoradError(Exception):
    pass


class Korad:
    GAP = 0.08  # minimálna medzera medzi príkazmi [s] – zdroj pri rýchlej komunikácii resetuje USB

    def __init__(self, port=None, baud=9600, timeout=1.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser = None
        self.idn = None
        self.lock = threading.RLock()
        self.on_command = None  # callback(cmd: str, resp: str)
        self._last_tx = 0.0

    # ---------- pripojenie ----------
    @staticmethod
    def candidates():
        """Sériové porty (Linux /dev/tty*, macOS /dev/cu.*, Windows COMx). Korad (Winbond 0416:5011) ide prvý."""
        ports = []
        for p in list_ports.comports():
            dev = p.device
            if dev.startswith("/dev/tty.") :  # macOS: preferuj /dev/cu.*
                continue
            score = 0 if (p.vid == 0x0416 and p.pid == 0x5011) else (1 if (p.vid or "USB" in (p.hwid or "")) else 2)
            ports.append((score, dev, p.description or ""))
        ports.sort()
        usb = [d for sc, d, _ in ports if sc < 2]
        return usb or [d for _, d, _ in ports]

    @staticmethod
    def port_list():
        out = []
        for p in list_ports.comports():
            if p.device.startswith("/dev/tty."):
                continue
            out.append({"device": p.device, "description": p.description or "", "hwid": p.hwid or "",
                        "korad": bool(p.vid == 0x0416 and p.pid == 0x5011)})
        return out

    @property
    def connected(self):
        return self.ser is not None and self.ser.is_open

    def connect(self, port=None):
        with self.lock:
            self.close()
            ports = [port or self.port] if (port or self.port) else self.candidates()
            errors = []
            for p in ports:
                try:
                    s = serial.Serial(p, self.baud, timeout=self.timeout, write_timeout=1)
                    time.sleep(0.05)
                    self.ser = s
                    idn = self._tx("*IDN?", until_timeout=True).strip()
                    if idn:
                        self.port = p
                        self.idn = idn
                        return idn
                    errors.append(f"{p}: no response")
                    s.close()
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{p}: {e}")
                self.ser = None
            raise KoradError("PSU not found. " + ("; ".join(errors) if errors else "No serial ports."))

    def close(self):
        with self.lock:
            if self.ser is not None:
                try:
                    self.ser.close()
                except Exception:  # noqa: BLE001
                    pass
            self.ser = None
            self.idn = None

    # ---------- nízka úroveň ----------
    def _drain(self):
        """Vyprázdni prípadné oneskorené odpovede, aby sa nepomiešali s ďalším príkazom."""
        try:
            old = self.ser.timeout
            self.ser.timeout = 0.15
            while self.ser.read(64):
                pass
            self.ser.timeout = old
        except (serial.SerialException, OSError):
            pass

    def _tx(self, cmd, nbytes=0, until_timeout=False):
        with self.lock:
            if not self.connected:
                raise KoradError("PSU is not connected")
            wait = self.GAP - (time.monotonic() - self._last_tx)
            if wait > 0:
                time.sleep(wait)
            try:
                self.ser.reset_input_buffer()
                self.ser.write(cmd.encode("ascii"))
                self.ser.flush()
                if nbytes:
                    data = self.ser.read(nbytes)
                    if len(data) < nbytes:
                        self._drain()
                elif until_timeout:
                    data = self.ser.read(64)
                else:
                    data = b""
            except (serial.SerialException, OSError) as e:
                self.close()
                raise KoradError(f"Serial port error: {e}") from e
            finally:
                self._last_tx = time.monotonic()
            resp = data.decode("ascii", "replace")
            if self.on_command:
                try:
                    self.on_command(cmd, resp)
                except Exception:  # noqa: BLE001
                    pass
            return resp

    def raw(self, cmd, nbytes=0):
        """Pošle ľubovoľný príkaz. nbytes=0 -> bez čakania na odpoveď (set), inak číta odpoveď."""
        if nbytes:
            return self._tx(cmd, until_timeout=True)
        return self._tx(cmd)

    def _float(self, s, what):
        s = s.strip().rstrip("\x00")
        try:
            return float(s[:6])
        except ValueError as e:
            with self.lock:
                if self.connected:
                    self._drain()
            raise KoradError(f"Invalid response to {what}: {s!r}") from e

    # ---------- čítanie ----------
    def idn_query(self):
        return self._tx("*IDN?", until_timeout=True).strip()

    def get_vset(self):
        return self._float(self._tx("VSET1?", 5), "VSET1?")

    def get_iset(self):
        return self._float(self._tx("ISET1?", 5), "ISET1?")

    def get_vout(self):
        return self._float(self._tx("VOUT1?", 5), "VOUT1?")

    def get_iout(self):
        return self._float(self._tx("IOUT1?", 5), "IOUT1?")

    def get_ocp_limit(self):
        """Prah OCP [A] (KA3005PS; staršie firmvéry neodpovedajú -> None)."""
        r = self._tx("OCP1?", 5)
        return self._float(r, "OCP1?") if r.strip() else None

    def get_ovp_limit(self):
        """Prah OVP [V]."""
        r = self._tx("OVP1?", 5)
        return self._float(r, "OVP1?") if r.strip() else None

    def set_ocp_limit(self, amps):
        amps = max(0.0, min(5.1, float(amps)))
        self._tx(f"OCP1:{amps:05.3f}")
        return amps

    def set_ovp_limit(self, volts):
        volts = max(0.0, min(31.0, float(volts)))
        self._tx(f"OVP1:{volts:05.2f}")
        return volts

    def status(self):
        b = self._tx("STATUS?", 1)
        if not b:
            raise KoradError("STATUS? no response")
        v = ord(b[0])
        return {
            "cv": bool(v & 0x01),
            "beep": bool(v & 0x10),
            "ocp": bool(v & 0x20),
            "output": bool(v & 0x40),
            "ovp": bool(v & 0x80),
            "raw": v,
        }

    # ---------- nastavenie ----------
    def set_v(self, volts):
        volts = max(0.0, min(31.0, float(volts)))
        self._tx(f"VSET1:{volts:05.2f}")
        return volts

    def set_i(self, amps):
        amps = max(0.0, min(5.1, float(amps)))
        self._tx(f"ISET1:{amps:05.3f}")
        return amps

    def output(self, on):
        self._tx("OUT1" if on else "OUT0")

    def ocp(self, on):
        self._tx("OCP1" if on else "OCP0")

    def ovp(self, on):
        self._tx("OVP1" if on else "OVP0")

    def beep(self, on):
        self._tx("BEEP1" if on else "BEEP0")

    def save(self, slot):
        slot = int(slot)
        if not 1 <= slot <= 5:
            raise KoradError("Memory slot must be 1–5")
        self._tx(f"SAV{slot}")

    def recall(self, slot):
        slot = int(slot)
        if not 1 <= slot <= 5:
            raise KoradError("Memory slot must be 1–5")
        self._tx(f"RCL{slot}")
