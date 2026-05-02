# MovieBuddy (Flask + Claude Sonnet)

Simple MovieBuddy — a tiny Flask app that talks about movies in a friendly, enthusiastic tone and gives suggestions using Anthropic's Claude Sonnet model.

Setup

1. Create a virtual environment and install deps:

```bash
python -m venv .venv
source .venv/bin/activate   # on Windows use `.venv\Scripts\activate`
pip install -r requirements.txt
```

2. Set your Anthropic API key in the environment:

```bash
export ANTHROPIC_API_KEY="sk-..."
# on Windows (cmd): set ANTHROPIC_API_KEY=sk-...
```

3. Run the app:

```bash
python app.py
```

Open http://localhost:5000 and chat about movies. The app sends prompts to the Claude Sonnet model; set `ANTHROPIC_API_KEY` before running.

Notes

- This is intentionally minimal and uses the Claude Sonnet model name. If your Anthropic API requires a different model name or request format, update `MODEL` and `ANTHROPIC_API_URL` in `app.py`.
