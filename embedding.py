
import openai
import os
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

def get_embedding(text, model="text-embedding-ada-002"):
    try:
        response = openai.Embedding.create(
            input=text,
            model=model
        )
        embedding = response['data'][0]['embedding']
        return embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

if __name__ == "__main__":
    sample_text = "Hello, how can I assist you today?"
    embedding = get_embedding(sample_text)
    print(embedding)
