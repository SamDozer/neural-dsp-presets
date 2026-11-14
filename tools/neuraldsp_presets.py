#!/usr/bin/env python3
"""Analyse and sort Neural DSP plugin presets (Archetype series, Fortin, Soldano ...).

  python neuraldsp_presets.py analyze <folder>            # print + write analysis.csv
  python neuraldsp_presets.py sort <folder> [--apply]     # dry run by default

Neural DSP presets use the extension .xml but are NOT text XML (except a few old plugins).
Two binary layouts exist and are both parsed here:

  "old"  JUCE-style  : ... presetNameProp <name> ... PARAM id <paramName> value <8-byte LE double> ...
  "new"  key/value   : ... name <name> ... selectedAmp <n> ... subModels ampParameters ... <amp>Gain <val> ...

What the analysis uses (see docs/HOW_IT_WORKS.md):
  1. selectedAmp (new) / ampType (old)  -> which amp slot is active (0 = clean, 1 = crunch/rhythm, 2+ = rhythm/lead)
  2. gain knob of that amp channel, and any active drive/overdrive pedal
  3. tags embedded in some presets (Clean, Metal, High-Gain ...)
  4. the preset name (clean / metal / djent ..., band names) - used first when it is clear
Standard library only.
"""
import csv, hashlib, os, re, shutil, struct, sys

# ---------------------------------------------------------------- parsing
CHANNEL_ORDER = ["clean", "funk", "crunch", "snob", "dumble", "vibroverb", "rhythm", "lead", "piezo"]


def tokens(data):
    return [t for t in re.sub(rb"[^\x20-\x7e]+", b"|", data).decode().split("|") if t]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return {"true": 1.0, "false": 0.0}.get(x)


def old_params(data):
    out = {}
    for m in re.finditer(rb"PARAM", data):
        seg = data[m.end():m.end() + 90]
        n = re.search(rb"id\W*?([A-Za-z][A-Za-z0-9_]{2,40})", seg)
        if not n:
            continue
        k = seg.find(b"value", n.end())
        if k < 0 or len(seg) < k + 17:
            continue
        out[re.sub(r"ID$", "", n.group(1).decode())] = struct.unpack("<d", seg[k + 9:k + 17])[0]
    return out


def features(path):
    """Return a dict describing the preset's sound-relevant settings."""
    data = open(path, "rb").read()
    F = dict(fmt=None, name=None, tags=[], chan=None, gain=None, pedal=0.0, sel=None, chans=[], kv={}, hash=None)
    if data.count(b"PARAM") > 20:                                    # old layout
        F["fmt"] = "old"
        p = old_params(data)
        F["kv"] = p
        F["hash"] = hashlib.md5(repr(sorted(p.items())).encode()).hexdigest()
        F["sel"] = p.get("ampType")
        ch = sorted({re.match(r"(clean|crunch|rhythm|lead)", k).group(1) for k in p
                     if re.match(r"(clean|crunch|rhythm|lead)(Amp)?Gain$", k)}, key=CHANNEL_ORDER.index)
        F["chans"] = ch
        if F["sel"] is not None and ch and int(F["sel"]) < len(ch):
            c = ch[int(F["sel"])]
            F["chan"], F["gain"] = c, p.get(f"{c}Gain", p.get(f"{c}AmpGain"))
        for pre in ("drive", "dist", "od", "fuzz", "boost", "overdrive", "pedalDrive"):
            if p.get(pre + "Active", 0) > 0.5:
                g = max([p.get(pre + s, 0) for s in ("Drive", "Gain", "Overdrive", "Level", "Fuzz", "Dist")] + [0])
                F["pedal"] = max(F["pedal"], g)
        return F
    t = tokens(data)
    if len(t) < 30:
        return F
    F["fmt"] = "new"
    kv = {}
    for i in range(len(t) - 1):
        kv.setdefault(t[i], t[i + 1])
    F["kv"], F["name"] = kv, kv.get("name")
    # hash ignores the name/favourite flag so renamed copies are detected as duplicates
    keep = [x for i, x in enumerate(t) if not (i and t[i - 1] in ("name", "isFavorite")) and x not in ("name", "isFavorite")]
    F["hash"] = hashlib.md5("|".join(keep).encode()).hexdigest()
    F["tags"] = [t[k + 2] for k in range(len(t) - 3) if t[k] == "tag" and t[k + 1] == "value"]
    F["sel"] = num(kv.get("selectedAmp"))
    amps = []
    if "ampParameters" in t:
        for x in t[t.index("ampParameters") + 1:][:500]:
            if x.endswith("Parameters") and x != "ampParameters":
                break
            m = re.fullmatch(r"([a-z0-9]+)Amp", x)
            if m:
                amps.append(m.group(1))
    ch = sorted(set(amps), key=lambda c: CHANNEL_ORDER.index(c) if c in CHANNEL_ORDER else 99)
    F["chans"] = ch
    if F["sel"] is not None and ch and int(F["sel"]) < len(ch):
        c = ch[int(F["sel"])]
        F["chan"] = c
        for k in (f"{c}Gain", f"{c}Drive"):
            if num(kv.get(k)) is not None:
                F["gain"] = num(kv[k])
                break
    if "ampGain1" in kv:                                              # Fortin Nameless
        F["gain"], F["chan"] = num(kv["ampGain1"]), F["chan"] or "nameless"
    for pre in ("drive", "drive1", "drive2", "dist", "od", "fuzz", "boost", "hexDrive", "grind"):
        if num(kv.get(pre + "Active", 0)) == 1.0:
            g = max([num(kv.get(pre + s)) or 0 for s in ("Drive", "Gain", "Overdrive", "Fuzz", "Dist")] + [0])
            F["pedal"] = max(F["pedal"], g)
    return F


# ---------------------------------------------------------------- classification
def sound_class(F, product=""):
    """(class, reason) from the file's own settings. class is Clean / Distortion / None."""
    tags = [t.lower() for t in F["tags"]]
    if "clean" in tags or ("jazz" in tags and "metal" not in tags):
        return "Clean", "tag"
    if any(t in tags for t in ("metal", "high-gain", "overdriven", "tight")):
        return "Distortion", "tag"
    sel, g, ped = F["sel"], F["gain"], F["pedal"]
    if F["fmt"] is None:
        return None, "unreadable"
    if "fortin" in product.lower() or "nameless" in product.lower():
        return ("Clean", "low gain") if (g is not None and g < 0.15 and ped < 0.3) else ("Distortion", "nameless amp")
    if sel is None or sel > 10:
        return None, "no amp info"
    i = int(sel)
    if any(k in product.lower() for k in ("cory", "john mayer")):     # clean-based amps
        drv = ped >= 0.6 or (F["kv"].get("snobDrive") == "true" and i > 0)
        return ("Distortion", "drive pedal") if drv else ("Clean", "clean-leaning amp")
    if i == 0:
        return ("Distortion", "drive pedal on clean amp") if ped >= 0.45 else ("Clean", "clean amp")
    if i == 1:
        return ("Distortion", "crunch + gain/pedal") if (g or 0) >= 0.5 or ped >= 0.45 else ("Clean", "low-gain crunch")
    return ("Clean", "low-gain lead") if (g is not None and g <= 0.25 and ped < 0.3) else ("Distortion", "rhythm/lead amp")


BANDS = [("Alice in Chains", r"alice in chains|\baic\b"), ("Dream Theater", r"dream theater"), ("Tool", r"\btool\b"),
         ("Periphery", r"periphery|satellites"), ("Meshuggah", r"meshuggah|^bleed\b"), ("Linkin Park", r"linkin park"),
         ("Disturbed", r"disturbed"), ("Deftones", r"deftones"), ("Mastodon", r"mastodon"), ("Gojira", r"gojira|chugg"),
         ("Metallica", r"master of puppets|enter sandman|72 seasons"), ("Pantera - Dimebag", r"pantera|dimebag"),
         ("Van Halen", r"van halen|\bevh\b|eruption"), ("Pink Floyd", r"comfortably numb|gilmour"), ("SRV", r"\bsrv\b"),
         ("John Mayer", r"john mayer|mayer "), ("Foo Fighters", r"foo fighters"), ("Blink-182", r"blink ?182"),
         ("Rage Against the Machine", r"rage against|tom morello|killing in the name"), ("Red Hot Chili Peppers", r"rhcp"),
         ("Pearl Jam", r"pearl jam"), ("Dire Straits", r"dire straits"), ("Coheed and Cambria", r"coheed"),
         ("Incubus", r"incubus"), ("Devin Townsend", r"devin townsend"), ("Spiritbox", r"spiritbox"),
         ("Black Crowes", r"black crowes"), ("Third Eye Blind", r"third eye blind"), ("King Gnu", r"king gnu"),
         ("Rush", r"\brush\b|limelight"), ("Eric Johnson", r"eric johnson"), ("Gary Moore", r"gary moore"),
         ("Rory Gallagher", r"rory gallagher"), ("System of a Down - Serj", r"serj tankian|system of a down"),
         ("ERRA", r"\berra\b"), ("Currents", r"currents"), ("TesseracT", r"tesseract"), ("Trivium", r"trivium"),
         ("Sylosis", r"sylosis"), ("Within Destruction", r"within destruction"), ("Knocked Loose", r"knocked loose"),
         ("Mr Big", r"mr big"), ("Switchfoot", r"switchfoot"), ("Daft Punk", r"daft punk"),
         ("Joy Division", r"joydivision|joy division"), ("Blind Melon", r"blind melon"),
         ("Bring Me The Horizon", r"shadow moses"), ("Black Dahlia Murder", r"black dahlia"),
         ("Fall of Troy", r"fall of troy"), ("As Blood Runs Black", r"as blood runs black"),
         ("Elder Ozone", r"elder ozone"), ("Polyphia", r"polyphia"), ("Animals as Leaders", r"abasi")]
ACOUSTIC = re.compile(r"acoustic|nylon|piezo|ambicoustic")
CLEAN_WORDS = re.compile(r"clean|chime|chimey|\barp\b|arpeggio|strum|shimmer|jazz|funk|crystal|ambient|dreamy|velvet|glass slide|comping|fingerstyle|edge of break|airy|tele ")
DIST_WORDS = re.compile(r"distort|metal|djent|chug|heavy|high gain|brutal|core\b|thrash|sludge|fuzz|filth|\bhg\b|death|recto|engl|5150|monolith|obliterat|aggressive")


def band_of(name):
    for b, rx in BANDS:
        if re.search(rx, name, re.I):
            return b


def name_class(name):
    n = name.lower()
    if ACOUSTIC.search(n):
        return "Acoustic"
    if CLEAN_WORDS.search(n):
        return "Clean"
    if DIST_WORDS.search(n):
        return "Distortion"


def categorize(path, product=""):
    stem = os.path.splitext(os.path.basename(path))[0]
    F = features(path)
    b = band_of(stem) or band_of(F["name"] or "")
    n = name_class(stem)
    s, why = sound_class(F, product)
    if b:
        return f"Bands/{b}", "band name", F
    if n == "Distortion" and s == "Clean" and not re.search(r"heavy|metal|djent|chug|brutal|high gain|thrash|sludge|core\b", stem, re.I):
        return s, why, F
    if n:
        return n, "preset name", F
    return (s or "Unsorted"), why, F


# ---------------------------------------------------------------- CLI
def preset_files(root):
    for r, _, fs in os.walk(root):
        for f in sorted(fs):
            if f.lower().endswith(".xml"):
                yield os.path.join(r, f)


def cmd_analyze(root):
    product = os.path.basename(os.path.abspath(root))
    rows = []
    for p in preset_files(root):
        cat, why, F = categorize(p, product)
        rows.append([os.path.relpath(p, root), F["fmt"], F["sel"], F["chan"], F["gain"], round(F["pedal"], 2), ";".join(F["tags"]), cat, why])
        print(f"{cat:28} {why:26} {os.path.basename(p)}")
    with open("analysis.csv", "w", newline="", encoding="utf8") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "format", "amp_slot", "amp_channel", "amp_gain", "drive_pedal", "tags", "category", "reason"])
        w.writerows(rows)
    print("wrote analysis.csv")


def cmd_sort(root, apply=False, backup="duplicates_removed"):
    product = os.path.basename(os.path.abspath(root))
    seen, plan = {}, []
    for p in preset_files(root):
        cat, why, F = categorize(p, product)
        if F["hash"] and F["hash"] in seen:
            plan.append((p, None, f"duplicate of {os.path.basename(seen[F['hash']])}"))
            continue
        if F["hash"]:
            seen[F["hash"]] = p
        plan.append((p, cat, why))
    for src, cat, why in plan:
        print(("REMOVE " if cat is None else f"{cat:28}"), why, "|", os.path.relpath(src, root))
        if not apply:
            continue
        if cat is None:
            os.makedirs(backup, exist_ok=True)
            shutil.move(src, os.path.join(backup, os.path.basename(src)))
        else:
            d = os.path.join(root, *cat.split("/"))
            os.makedirs(d, exist_ok=True)
            dst, k = os.path.join(d, os.path.basename(src)), 2
            while os.path.exists(dst) and os.path.abspath(dst) != os.path.abspath(src):
                dst = os.path.join(d, f"{os.path.splitext(os.path.basename(src))[0]} ({k}).xml")
                k += 1
            if os.path.abspath(dst) != os.path.abspath(src):
                shutil.move(src, dst)
    print("applied" if apply else "dry run only - pass --apply to move files")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "analyze":
        cmd_analyze(a[1])
    elif len(a) >= 2 and a[0] == "sort":
        cmd_sort(a[1], "--apply" in a)
    else:
        print(__doc__)
