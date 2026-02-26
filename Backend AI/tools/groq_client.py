from groq import Groq
from config.settings import GROQ_API_KEY

groq_client = Groq(api_key=GROQ_API_KEY)