# test_openai_direct.py
import sys
import os

# Agregar el proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecuador_turismo.settings')

import django
django.setup()

from django.conf import settings

print("=" * 50)
print("TEST OPENAI - DIAGNÓSTICO COMPLETO")
print("=" * 50)

# Test 1: Configuración
print("\n1️⃣ CONFIGURACIÓN:")
print(f"   API Key configurada: {'✅ Sí' if settings.OPENAI_API_KEY else '❌ NO'}")
if settings.OPENAI_API_KEY:
    print(f"   Primeros 20 chars: {settings.OPENAI_API_KEY[:20]}...")
    print(f"   Últimos 10 chars: ...{settings.OPENAI_API_KEY[-10:]}")

# Test 2: Importación
print("\n2️⃣ IMPORTACIÓN:")
try:
    from openai import OpenAI
    print("   ✅ OpenAI importado correctamente")
    import openai
    print(f"   Versión: {openai.__version__}")
except ImportError as e:
    print(f"   ❌ Error importando: {e}")
    sys.exit(1)

# Test 3: Verificar httpx
print("\n3️⃣ DEPENDENCIAS:")
try:
    import httpx
    print(f"   ✅ httpx: {httpx.__version__}")
except ImportError:
    print("   ❌ httpx no instalado")

try:
    import httpcore
    print(f"   ✅ httpcore: {httpcore.__version__}")
except ImportError:
    print("   ❌ httpcore no instalado")

# Test 4: Crear cliente
print("\n4️⃣ CREAR CLIENTE:")
try:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    print("   ✅ Cliente creado exitosamente")
except Exception as e:
    print(f"   ❌ Error creando cliente: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Llamada simple
print("\n5️⃣ LLAMADA A API:")
try:
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Di solo: OK"}],
        max_tokens=10
    )
    respuesta = response.choices[0].message.content
    print(f"   ✅ OpenAI respondió: '{respuesta}'")
except Exception as e:
    print(f"   ❌ Error en llamada: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 50)
print("✅ TODOS LOS TESTS PASARON")
print("=" * 50)