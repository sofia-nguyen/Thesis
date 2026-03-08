import openai 
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-4.1-nano",
    input="write a haiku about the changing seasons"
)

print(response.output_text)