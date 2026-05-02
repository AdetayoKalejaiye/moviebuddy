from flask import Flask, render_template, request
import os
import requests
from dotenv import load_dotenv

# load environment variables from .env in project root
load_dotenv()

app = Flask(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/complete"
MODEL = "claude-sonnet"


def call_claude(prompt: str, max_tokens: int = 400, temperature: float = 0.7) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY environment variable")

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "max_tokens_to_sample": max_tokens,
        "temperature": temperature,
        "stop_sequences": ["\n\nHuman:"]
    }

    resp = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data.get("completion", "")


@app.route("/", methods=["GET", "POST"])
def index():
    user_msg = ""
    assistant_msg = ""

    if request.method == "POST":
        user_msg = request.form.get("message", "").strip()
        if user_msg:
            system_prompt = (
                "You are MovieBuddy, a friendly, enthusiastic assistant who loves movies."
                " Keep the tone upbeat and conversational. When asked for suggestions, give 3 concise picks with a one-line reason each."
                " If the user asks follow-ups, ask clarifying questions."
                "\n\nHuman: " + user_msg + "\n\nAssistant:"
            )
            try:
                assistant_msg = call_claude(system_prompt)
            except Exception as e:
                assistant_msg = f"Error contacting the Claude API: {e}"

    return render_template("index.html", user_msg=user_msg, assistant_msg=assistant_msg)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
