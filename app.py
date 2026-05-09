from flask import Flask, render_template, request, redirect, session, url_for
import json
import logging
import os
import re
from html import escape
from dotenv import load_dotenv
from adlib_client import AdLib
import openai

# load environment variables from .env in project root
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "moviebuddy-dev-secret")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
URL_PATTERN = re.compile(r'(?i)\b((?:https?://)?(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s<>"]*)?)')
SPONSOR_LINE = "- Sponsored by AdLib"

# Initialize AdLib for ad monetization
try:
    adlib = AdLib()
    logger.info("AdLib initialized successfully")
except Exception as e:
    logger.warning("AdLib not initialized: %s", e)
    adlib = None


def call_openai(prompt: str, max_tokens: int = 400, temperature: float = 0.7) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable")

    base_url = os.environ.get("OPENAI_BASE_URL")
    openai.api_key = api_key
    if base_url:
        openai.api_base = base_url

    messages = [{"role": "user", "content": prompt}]

    resp = openai.ChatCompletion.create(
        model=MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    # Extract assistant content
    if resp and getattr(resp, "choices", None):
        return resp.choices[0].message.get("content", "").strip()
    # Fallback
    return ""


def strip_ad_footer(text: str) -> str:
    lines = []
    for line in (text or "").splitlines():
        normalized = line.strip().lower()
        if not normalized:
            lines.append(line)
            continue
        if "sponsored by adlib" in normalized:
            continue
        if set(normalized) <= {"=", "-", "*"}:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def render_message_html(text: str) -> str:
    raw = text or ""
    
    # First, handle markdown links [text](url)
    markdown_link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    
    def replace_markdown_link(match):
        display = escape(match.group(1))
        url = match.group(2).strip()
        href = url if url.lower().startswith(("http://", "https://")) else f"https://{url}"
        return f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">{display}</a>'
    
    raw = markdown_link_pattern.sub(replace_markdown_link, raw)
    
    # Then handle any remaining bare URLs
    parts = []
    last_index = 0

    for match in URL_PATTERN.finditer(raw):
        start, end = match.span()
        url = match.group(0)
        trimmed = url.rstrip(".,);!?]")
        trailing = url[len(trimmed):]
        href = trimmed if trimmed.lower().startswith(("http://", "https://")) else f"https://{trimmed}"

        parts.append(escape(raw[last_index:start]))
        parts.append(
            f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">'
            f"{escape(trimmed)}"
            "</a>"
        )
        parts.append(escape(trailing))
        last_index = end

    parts.append(escape(raw[last_index:]))
    return "".join(parts).replace("\n", "<br>")


def rewrite_ad_message(original_message: str, ad_response: dict) -> str:
    prompt = (
        "You are polishing a movie recommendation reply. "
        "Rewrite the message so the sponsored content is subtle, seamlessly interwoven, and almost indistinguishable from the chat. "
        "Use exactly four numbered items. Items 1 to 3 should be the movie recommendations. Item 4 must be the sponsored recommendation and must feel like part of the same list, not a separate ad paragraph. "
        "If there is a promo link, weave it naturally into item 4 and keep the link exactly as provided. "
        "Do not place the sponsored content after the list as a separate block. Do not use banner text, separators, or footer-like formatting. "
        "The sponsored item should read like a natural continuation of the list, as if it belongs there. "
        f"End with the exact sponsorship line on its own line: {SPONSOR_LINE}. "
        "Keep the original recommendation helpful, conversational, and concise. "
        "Return only the final message text.\n\n"
        f"Original message:\n{original_message}\n\n"
        f"AdLib response JSON:\n{json.dumps(ad_response, ensure_ascii=False, indent=2)}"
    )
    return call_openai(prompt, max_tokens=500, temperature=0.4)


@app.route("/", methods=["GET", "POST"])
def index():
    assistant_msg = ""

    ad_data = {}
    assistant_msg_html = ""

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
                assistant_msg = call_openai(system_prompt)
                
                # Monetize with AdLib
                if adlib:
                    try:
                        ad_response = adlib.adify_full(assistant_msg)
                        logger.info("AdLib raw response: %s", ad_response)
                        ad_data = ad_response.get("ad", {})
                        adified_text = ad_response.get("adified", assistant_msg)
                        cleaned_text = strip_ad_footer(adified_text)
                        logger.info("AdLib adified text: %s", adified_text)
                        logger.info("AdLib ad payload: %s", ad_data)
                        assistant_msg = rewrite_ad_message(cleaned_text, ad_response)
                        logger.info("Rewritten AdLib output: %s", assistant_msg)
                    except Exception as e:
                        logger.exception("AdLib error: %s", e)
                        
            except Exception as e:
                assistant_msg = f"Error contacting the OpenAI API: {e}"
            session["assistant_msg"] = assistant_msg
            session["assistant_msg_html"] = render_message_html(assistant_msg) if assistant_msg and "Error contacting the OpenAI API:" not in assistant_msg else escape(assistant_msg)
            session["ad_data"] = ad_data
            return redirect(url_for("index"))

    assistant_msg = session.pop("assistant_msg", "")
    assistant_msg_html = session.pop("assistant_msg_html", "")
    ad_data = session.pop("ad_data", {})

    response = render_template(
        "index.html",
        assistant_msg=assistant_msg,
        assistant_msg_html=assistant_msg_html,
        ad=ad_data,
    )
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
