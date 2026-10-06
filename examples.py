"""Example scripts shipped with the app: copied into the user's scripts folder and kept up to date.

The user folder holds .examples.json = {file name: sha256 of the copy the app installed}.
An example the user has not changed is updated, or removed when the app no longer ships it
(e.g. it was renamed). A changed example and the user's own scripts are never touched.
"""
import hashlib
import json
import os
import shutil

MANIFEST = ".examples.json"

# (name, sha256) of every example shipped before the manifest existed (v1.0.x / v1.1.x):
# lets the first run recognise untouched old copies. Never needs updating.
LEGACY = frozenset({
    ("01_basic_example.py", "3ca4b36315942be3e0bfe779d540113cdde63fedd3be6b742da510d903527e96"),
    ("01_basic_example.py", "e7806f1370b9fb445df92d51458927d33d1846b5604a65f707caf86285d1c8b4"),
    ("01_priklad_zakladny.py", "3ca4b36315942be3e0bfe779d540113cdde63fedd3be6b742da510d903527e96"),
    ("02_rampa_napatia.py", "5cc92b152386b7ca4e3996e480ab97f448721ed8c2d83e9c166e802126ae1b29"),
    ("02_voltage_ramp.py", "5cc92b152386b7ca4e3996e480ab97f448721ed8c2d83e9c166e802126ae1b29"),
    ("02_voltage_ramp.py", "ebef33683950c8b289a7023057238f71df1d0316a709bb8d1e38b6a258d29e56"),
    ("03_iv_curve.py", "07a3506a70150557b68f0ad9fd54a4ea8fc2bbd0d8fcf476cac98f86fe5cffd0"),
    ("03_iv_curve.py", "fd2fa05bd385f512da158adeafcd0944874d266e37c28205db4351f986e23d9c"),
    ("03_vybijacia_krivka.py", "fd2fa05bd385f512da158adeafcd0944874d266e37c28205db4351f986e23d9c"),
    ("04_cyklovanie.py", "020ee4df0eb8201bdcd278cf981731b720201968a66db7a4cd584d136d7c22c0"),
    ("04_output_cycling.py", "020ee4df0eb8201bdcd278cf981731b720201968a66db7a4cd584d136d7c22c0"),
    ("04_output_cycling.py", "9c27233863b188e16ff2e6227e298ae62636741351c21eb9e69725c7e3c36952"),
    ("10_charge_liion.py", "68a1117f9d013afabc0ee7d0437eda3d8c3a479c107cfc36e4e06e332ffc0bfc"),
    ("10_charge_liion.py", "a87de8e540891f219df53d2ac287a8e09f50eae5c3ed14f0008e3e00b707be35"),
    ("10_nabijanie_liion.py", "68a1117f9d013afabc0ee7d0437eda3d8c3a479c107cfc36e4e06e332ffc0bfc"),
    ("11_charge_lifepo4.py", "0c8f22d5f9b5b2982462abea7212efe2af5da84a4b03f25d7e01f61feacaeb6a"),
    ("11_charge_lifepo4.py", "f015bd9b74a7a1359e03f58882dde1ed8782cbce0330fde0407f57326e60d77d"),
    ("11_nabijanie_lifepo4.py", "f015bd9b74a7a1359e03f58882dde1ed8782cbce0330fde0407f57326e60d77d"),
    ("12_charge_lead_acid.py", "3b5e9d98db6b34e6a1b563fbb19def9c80efce9c0bcc76048b6b968a4868077f"),
    ("12_charge_lead_acid.py", "f54cc56040621d3b98a2172ffa8a6b618d9ef677bffa8e935cfa45f7709955ee"),
    ("12_nabijanie_olovo.py", "f54cc56040621d3b98a2172ffa8a6b618d9ef677bffa8e935cfa45f7709955ee"),
    ("13_charge_nimh.py", "518942e45985b41e8477ee6004826dcecb235b13f3ec1b759b7474b1e0a439be"),
    ("13_charge_nimh.py", "a48d97e3800b3e4a2c178adc0d6137319eb4547a903f5946c16ef28d27c99ea7"),
    ("13_nabijanie_nimh.py", "518942e45985b41e8477ee6004826dcecb235b13f3ec1b759b7474b1e0a439be"),
    ("14_charge_custom.py", "856f2ee40d4f0824187aa6fcb52becefad6ff44e7deae566f83467292336f460"),
    ("14_charge_custom.py", "eebf215bd4ede84032fa9120a6ab8382a7213699e42ca24db91303e321f77c6d"),
    ("14_nabijanie_vlastne.py", "856f2ee40d4f0824187aa6fcb52becefad6ff44e7deae566f83467292336f460"),
    ("15_battery_check.py", "47df09addac5d1dc0dfa162b1ec7ca1d28af48878b683e9c1e3b74e4b608d056"),
    ("15_battery_check.py", "e9350950916c5d7189282506cf8ee26117bbaf04dec3188ce407e05f15c32d85"),
    ("15_test_kapacity_info.py", "47df09addac5d1dc0dfa162b1ec7ca1d28af48878b683e9c1e3b74e4b608d056"),
    ("16_charge_panasonic_cgr18650cg.py", "e24ff3300c838d4a9ecacf2f1f44c4888edcab5acbf2009a0439a91df21662a1"),
    ("17_charge_sanyo_ur18650a.py", "fbdddec1d51927992809cb65cdc4b1651e8e63fd0935c37206029836c0c4ba74"),
    ("lib_batt.py", "37ef94670a8861c238409336f18544894f9c466e5b34cbe8cba6227631d4fe8b"),
    ("lib_batt.py", "44bb8d070468c650360cf82d8ff6cf9af5486b636e428d475d398f439954bc3c"),
    ("lib_batt.py", "e1389d9b5f7d3c3b235b8c59cd01f89c9847eff1ea61cbdbcad1f1f23d0d1045"),
})


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sync(src, dst):
    """Installs / updates / removes the examples from src in the user folder dst. Returns {action: [files]}."""
    done = {"added": [], "updated": [], "removed": []}
    if not os.path.isdir(src) or os.path.abspath(src) == os.path.abspath(dst):
        return done
    mpath = os.path.join(dst, MANIFEST)
    try:
        with open(mpath, encoding="utf-8") as f:
            known = json.load(f)
    except (OSError, ValueError):
        known = None                     # first run of a version with the manifest
    shipped = sorted(fn for fn in os.listdir(src) if fn.endswith(".py"))
    if known is None:
        candidates = [fn for fn in os.listdir(dst) if fn.endswith(".py")]
    else:
        candidates = list(known)

    pristine = set()                     # examples installed by us and not edited since
    for fn in candidates:
        p = os.path.join(dst, fn)
        if not os.path.isfile(p):
            continue
        h = _sha(p)
        if not (known.get(fn) == h if known is not None else (fn, h) in LEGACY):
            continue
        if fn in shipped:
            pristine.add(fn)
        else:
            os.remove(p)
            done["removed"].append(fn)

    manifest = {}
    for fn in shipped:
        s, p = os.path.join(src, fn), os.path.join(dst, fn)
        exists = os.path.exists(p)
        if exists and fn not in pristine:
            continue                     # the user's version, leave it alone
        if not exists or _sha(p) != _sha(s):
            shutil.copyfile(s, p)
            done["updated" if exists else "added"].append(fn)
        manifest[fn] = _sha(p)
    tmp = mpath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    os.replace(tmp, mpath)
    return done
