# stem-extractor

Web UI for [demucs](https://github.com/adefossez/demucs) stem separation. Drag and drop an audio file, pick a model and output format, get stems back as a zip.

<img width="793" height="772" alt="image" src="https://github.com/user-attachments/assets/58473336-9be8-48ed-b9ca-2d2885a84a0a" />

## Usage

Requires `demucs` to be installed and in your PATH.

This app is packaged using [uv](https://docs.astral.sh/uv/getting-started/installation/). Or just do `pip install flask`

```
uv run app.py
```

Then go to `http://localhost:5000`.

Optionally configure host and port: `uv run app.py 0.0.0.0 8080`

## Supported models

- `htdemucs_6s` — 6 stems (vocals, drums, bass, guitar, piano, other)
- `htdemucs` — 4 stems (vocals, drums, bass, other)
- `hdemucs_mmi` — 4 stems (vocals, drums, bass, other)
