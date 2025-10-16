# test_key.py
from decouple import config

key = config('OPENAI_API_KEY', default='NO_ENCONTRADA')
print(f"Key encontrada: {key[:20]}...{key[-10:]}")
print(f"Termina en: {key[-4:]}")