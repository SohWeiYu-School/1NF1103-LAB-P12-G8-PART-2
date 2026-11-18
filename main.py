"""
main.py - starts Orbit, the Source of Wealth screening system.

It does two things: it chooses the AI brand (OpenAI, with Gemini as the fallback) and
starts App. App creates every other object and coordinates them.

    python main.py                          interactive menu
    python main.py --web                    the web app (http://127.0.0.1:5000)
"""

import sys

from app.ai.ai_caller import gemini_caller, openai_caller, with_fallback
from app.application.app import App

if __name__ == "__main__":
    sys.exit(App(with_fallback(openai_caller(), gemini_caller())).start(sys.argv[1:]))
