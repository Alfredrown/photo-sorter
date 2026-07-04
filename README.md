# PhotoSort AI

Automatically separate portrait photos from landscape photos using local AI — no internet, no cloud, no data leaves your machine.

![PhotoSort UI](docs/screenshot.png)

## How it works

Uses **CLIP** (OpenAI's vision-language model) running entirely on your computer. CLIP understands natural language descriptions of images, so it can distinguish *"a portrait photo of a person"* from *"a landscape photo of scenery"* without any training on your photos.

- **Mac** — accelerated with Apple Silicon MPS (M1/M2/M3)
- **Windows** — runs on CPU (or CUDA GPU if available)
- Confidence threshold slider to control what goes to "uncertain" for manual review
- Originals are **never moved or deleted** — only copied into subfolders

## Requirements

- Python 3.9+
- Internet connection on **first run only** (downloads ~350MB CLIP model weights)

## Getting started

```bash
git clone https://github.com/YOUR_USERNAME/photo-sorter.git
cd photo-sorter
./run.sh        # Mac / Linux
```

**Windows:** run these instead:
```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Then open `frontend/index.html` in your browser.

## Usage

1. Click **Choose folder…** — picks a folder using your OS's native dialog
2. Click **Start classifying** — the AI processes each photo and streams results live
3. Browse results in the **Portraits / Landscapes / Uncertain** tabs
4. Adjust the **threshold slider** — lower it to force more photos into a category, higher to send borderline ones to "uncertain"
5. Click **Copy to folders** — copies files into:

```
your-folder/
└── sorted/
    ├── portraits/
    ├── landscapes/
    └── uncertain/
```

## Project structure

```
photo-sorter/
├── run.sh                   # One-command startup (Mac/Linux)
├── backend/
│   ├── app.py               # Flask API server
│   ├── classifier.py        # CLIP model (MPS / CUDA / CPU)
│   ├── picker.py            # Cross-platform folder dialog (tkinter)
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/status` | Server health check |
| GET | `/pick-folder` | Open native folder picker dialog |
| GET | `/image?path=...` | Serve a local image to the browser |
| POST | `/classify` | Classify all images in a folder (SSE streaming) |
| POST | `/sort` | Copy classified images into subfolders |

## Tech stack

- **AI model** — [OpenCLIP](https://github.com/mlfoundations/open_clip) ViT-B/32 (OpenAI weights)
- **Backend** — Python, Flask
- **Frontend** — Vanilla HTML/CSS/JS (no framework)

## License

MIT
