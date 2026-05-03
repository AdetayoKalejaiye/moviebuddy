from flask import Flask, render_template, request
import logging
import os
from dotenv import load_dotenv
from adlib_client import AdLib
import openai

# load environment variables from .env in project root
load_dotenv()

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

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


@app.route("/", methods=["GET", "POST"])
def index():
    user_msg = ""
    assistant_msg = ""

    ad_data = {}
    
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
                        assistant_msg = ad_response.get("adified", assistant_msg)
                        ad_data = ad_response.get("ad", {})
                        logger.info("AdLib adified text: %s", assistant_msg)
                        logger.info("AdLib ad payload: %s", ad_data)
                    except Exception as e:
                        logger.exception("AdLib error: %s", e)
                        
            except Exception as e:
                assistant_msg = f"Error contacting the OpenAI API: {e}"

    return render_template("index.html", user_msg=user_msg, assistant_msg=assistant_msg, ad=ad_data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
