# Notes for AI agents and contributors

- Presets live in `<Product>/{Clean,Distortion,Acoustic,Bands/<band>}/*.xml`. Find them via `presets_index.json`.
- `.xml` files are mostly **binary** - do not edit them as text. Use `tools/neuraldsp_presets.py` to read them.
- To add presets: drop them in a product folder and run `python tools/neuraldsp_presets.py sort "<Product>" --apply`, then rebuild the index.
- Do not add presets without a clear right to share them (see THIRD_PARTY.md).
