# Neural DSP Presets - Sorted (Archetype, Nolly X, Plini, Gojira X, Petrucci X, Misha, Fortin, Soldano & more)

Free, de-duplicated **Neural DSP plugin presets** (~1,000) for **Archetype: Nolly X, Plini, Gojira X, John Petrucci X, Misha Mansoor X, Cory Wong X, Tim Henson X, Tosin Abasi, Mateus Asato X, John Mayer X, Rabea Massaad X, Fortin Nameless, Soldano SLO-100, Parallax, Darkglass Ultra, Mesa Boogie Mark IIC+**, sorted into **clean / distortion / acoustic / band tones** (Alice in Chains, Dream Theater, Tool, Periphery, Meshuggah, Metallica, Deftones, Mastodon...). Good for djent, prog metal, post-metal, sludge, metalcore, blues, funk, ambient and clean tones. Also includes **Python tools to parse the Neural DSP preset file format and classify tones automatically**, and a downloader for Neural DSP forum threads.

Searchable index: [`presets_index.json`](presets_index.json) / [`presets_index.csv`](presets_index.csv) - how the tones are detected: [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md)

A personal collection of Neural DSP plugin presets (Archetype series, Fortin, Soldano, Parallax, Darkglass, Mesa and more), de-duplicated and sorted so they are easy to browse.

## Layout

Each product has its own folder, sorted into:

- `Clean/` – clean and low-gain tones
- `Distortion/` – crunch, rhythm, lead and high-gain tones
- `Acoustic/` – piezo / acoustic tones (where present)
- `Bands/<band>/` – tones named after a band or song (Alice in Chains, Dream Theater, Tool, Periphery…)
- `Special FX/` – synth / non-guitar sounds (Rabea only)

`Other plugins/` holds presets for the non-Archetype plugins, sorted the same way.

## How the sorting works

Preset files store the active amp channel, its gain, and which drive pedals are on, so tones were classified from the files themselves, with the preset name taking priority when it clearly says "clean", "metal", "djent" etc. Band folders come from names only. Expect a few mistakes.

## Where they come from

Presets shared by the community on the Neural DSP forum and elsewhere, plus selected presets collections. All credit belongs to the original authors (file names often include the author). Presets embed the author's original save path inside the file; that is normal for this format.

If you are an author or rights holder and want something removed, open an issue and it will be taken down.

Not affiliated with Neural DSP.

## Install

Copy the `.xml` files into the plugin's `User` preset folder (e.g. `C:\ProgramData\Neural DSP\<plugin>\User`).

## Tools

| Tool | What it does |
|---|---|
| [`tools/neuraldsp_presets.py`](tools/neuraldsp_presets.py) | `analyze` / `sort` - reads the binary preset files, detects the active amp channel, gain, drive pedals and tags, classifies Clean/Distortion/Bands, removes duplicates |
| [`tools/download_presets.py`](tools/download_presets.py) | downloads all attachments and public Drive links from a Neural DSP forum (Discourse) thread |

```bash
python tools/neuraldsp_presets.py analyze "Archetype Nolly X"
python tools/download_presets.py 31 nolly_presets
```

See [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) for how the detection works and how accurate it is, and [`THIRD_PARTY.md`](THIRD_PARTY.md) for other sources.
