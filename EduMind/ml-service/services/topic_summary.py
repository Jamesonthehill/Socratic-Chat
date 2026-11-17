import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class TopicSummary:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_TOPIC_SUMMARY_MODEL")

        if not self.api_key:
            raise ValueError("OpenAI API key is missing.")

        self.client = OpenAI(api_key=self.api_key)

    def complete(self, prompt, system_prompt="You are a helpful assistant."):
        try:
            response = self.client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            return {
                "status": "success",
                "response": response.choices[0].message.content
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
