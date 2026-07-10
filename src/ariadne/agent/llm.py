import os
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def ask_llm(prompt: str) -> str:
    for _ in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
            )
            return response.text

        except Exception as e:
            print("Gemini unavailable. Retrying...")
            print(e)
            time.sleep(5)

    return "Failed to contact Gemini."