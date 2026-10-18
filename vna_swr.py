#!/usr/bin/env python3
"""КСВ антенн через LiteVNA: 868 МГц, 2.4, 5.2, 5.8 ГГц.

pip install pynanovna numpy
  python3 vna_swr.py cal [от_МГц до_МГц]       # калибровка OPEN/SHORT/LOAD на порту 1
  python3 vna_swr.py measure [от_МГц до_МГц]   # замер антенны, таблица + csv
Пример для LoRa 869.525: cal 860 880, затем measure 860 880.
Диапазон для cal и measure должен совпадать (калибровка хранится в файле с диапазоном в имени).
Нужен доступ к /dev/ttyACM0: группа uucp или sudo.
"""
import sys, csv, time
import numpy as np
from pynanovna import VNA

START, STOP, POINTS = 700e6, 6.0e9, 1001
if len(sys.argv) >= 4:
    START, STOP = float(sys.argv[2]) * 1e6, float(sys.argv[3]) * 1e6
CAL_FILE = f"litevna_{START/1e6:.0f}-{STOP/1e6:.0f}MHz.cal"
FOCUS = 869.525e6  # доп. строка в таблице, если попадает в диапазон
BANDS = {            # имя: (от, до, центр) в Гц
    "868 LoRa": (863e6, 870e6, 868e6),
    "2.4 WiFi": (2400e6, 2483.5e6, 2440e6),
    "5.2 WiFi": (5150e6, 5250e6, 5200e6),
    "5.8 WiFi": (5725e6, 5850e6, 5800e6),
}


def connect():
    v = VNA()
    if not v.is_connected():
        sys.exit("VNA не найден: проверь кабель и права на /dev/ttyACM0 (группа uucp)")
    v.set_sweep(START, STOP, POINTS)
    return v


def calibrate():
    v = connect()
    for step, hint in (("open", "порт 1 ПУСТОЙ"),
                       ("short", "заглушка SHORT на ПОРТ 1"),
                       ("load", "заглушка 50 Ом на ПОРТ 1")):
        input(f"[{step.upper()}] {hint}. Enter...")
        v.calibration_step(step)
        print("  ок")
    v.calibrate()
    v.save_calibration(CAL_FILE)
    print("Калибровка сохранена:", CAL_FILE)


def swr(s11):
    g = np.clip(np.abs(s11), 0, 0.9999)
    return (1 + g) / (1 - g)


def measure():
    v = connect()
    v.load_calibration(CAL_FILE)
    s11, _, f = v.sweep()
    f = np.array(f, float)
    s = swr(np.array(s11))
    rl = 20 * np.log10(np.clip(np.abs(s11), 1e-6, 1))
    print(f"{'Диапазон':10} {'КСВ@центр':>10} {'RL,дБ':>7} {'мин.КСВ':>8} {'на МГц':>8} {'макс в полосе':>13}")
    for name, (lo, hi, c) in BANDS.items():
        i = int(np.argmin(abs(f - c)))
        m = (f >= lo) & (f <= hi)
        if not m.any():
            m = np.zeros_like(f, bool); m[i] = True
        j = np.argmin(np.where((f > 0.9 * lo) & (f < 1.1 * hi), s, 1e9))
        print(f"{name:10} {s[i]:10.2f} {rl[i]:7.1f} {s[j]:8.2f} {f[j]/1e6:8.0f} {s[m].max():13.2f}")
    if START <= FOCUS <= STOP:
        k = int(np.argmin(abs(f - FOCUS)))
        print(f"{FOCUS/1e6:.3f} МГц: КСВ {s[k]:.2f}, RL {rl[k]:.1f} дБ (точка {f[k]/1e6:.3f} МГц)")
    fn = time.strftime("swr_%Y%m%d_%H%M%S.csv")
    with open(fn, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["freq_hz", "swr", "return_loss_db"])
        w.writerows(zip(f, s, rl))
    print("CSV:", fn)


if __name__ == "__main__":
    {"cal": calibrate, "measure": measure}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
