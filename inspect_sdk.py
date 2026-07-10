from google import genai

print(genai.__version__)

client = genai.Client(api_key="dummy")

print(dir(client.models))