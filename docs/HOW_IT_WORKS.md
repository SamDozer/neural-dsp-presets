# How the tones are detected

Neural DSP presets are saved with the extension `.xml`, but almost all of them are **binary** files, not text XML. This repo's tools read them directly (`tools/neuraldsp_presets.py`, Python standard library only).

## The two binary layouts

| Layout | Plugins | Looks like |
|---|---|---|
| **old** (JUCE-style) | older Archetype/Fortin/Plini/Nolly/Abasi presets, Parallax, Mesa, Darkglass | `presetNameProp <name> ... PARAM id <paramName> value <8-byte little-endian double> ...` |
| **new** (key/value tree) | "X" plugins: Petrucci X, Nolly X, Misha X, Cory Wong X, Tim Henson X, Mateus Asato X, John Mayer X, Rabea X, Gojira X, Soldano X, Fortin Nameless X | `name <name> ... selectedAmp <n> ... subModels ampParameters ... cleanGain <val> ...` (values stored as text) |

A few very old plugins (Nameless Suite) use real XML (`<Parameter ... gain1="0.41" ...>`).

## What tells you "clean" vs "distortion"

1. **Active amp slot** - `selectedAmp` (new) or `ampType` (old). Slot 0 is the clean amp in every Archetype plugin. Slot 1 is a crunch/rhythm channel (ambiguous). Slot 2 and up are rhythm/lead channels. Amp slot order differs per plugin and per format, which is why the slot alone is not enough.
2. **Gain knob of that channel** (`cleanGain`, `rhythmGain`, `leadGain`, `crunchGain` ...). Clean channels often have no gain knob at all.
3. **Drive / overdrive pedals that are switched on** (`driveActive` + `driveDrive/Gain`). A clean amp with a drive pedal at 0.45 or more counts as Distortion.
4. **Tags** embedded in some presets (`Clean`, `Jazz`, `Metal`, `High-Gain`, `Tight` ...). Used first when present.
5. **The preset name** - clear words ("clean", "djent", "metal", "sludge", "acoustic") win; band names create `Bands/<band>`.

Clean-based plugins (Cory Wong, John Mayer) default to Clean unless a drive pedal is clearly on. Fortin Nameless is a high-gain amp, so it defaults to Distortion unless the gain is very low.

## Accuracy

Checked against presets whose names clearly say clean or distorted, the settings-based rule agrees about **87%** of the time, and about **90%** once name keywords are combined with it. Many "misses" are misleading names (a preset called "Boosted Clean" with the gain at 0.76). Treat the sorting as a good first pass, not ground truth. Band folders come from names only.

## Commands

```bash
python tools/neuraldsp_presets.py analyze "Archetype Nolly"       # table + analysis.csv
python tools/neuraldsp_presets.py sort    "Archetype Nolly"       # dry run
python tools/neuraldsp_presets.py sort    "Archetype Nolly" --apply   # moves files, removes duplicates
```

Duplicates are found by hashing the preset's settings while ignoring its name, so renamed copies are caught.

## Downloading from the Neural DSP forum

`tools/download_presets.py <topic_id> [folder]` uses the forum's public Discourse JSON API: it lists a thread's posts, finds attachment links (`/uploads/...`) and public Google Drive file/folder links, and saves them under their original names. It is parallel, resumable, and writes anything it could not fetch (Mega, MediaFire, WeTransfer, Dropbox pages that need a browser) to `NOT_DOWNLOADED.txt`.

```bash
python tools/download_presets.py 31 nolly_presets    # topic id = number in the thread URL
```

Be polite to the server (the script already throttles) and respect the authors' wishes.
