# Gemini API access: thin wrapper, prompt building lives in summary.py
from google import genai


class GeminiClient:
    def __init__(self, api_key: str, model: str):
        """
        :param api_key: the Gemini API key
        :param model: the model name, e.g. "gemini-2.5-flash"
        """
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, text: str) -> str:
        """
        Sends text to the model
        :param text: the full prompt
        :return: the model's text response
        """
        response = self.client.models.generate_content(model=self.model, contents=text)
        return response.text
