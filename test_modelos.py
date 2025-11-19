"""
Script para probar qué modelos de Google AI están disponibles
"""

import google.generativeai as genai
import os

# Configurar API
api_key = "AIzaSyD9hbctG1CX63U2-YGDMwUY6RJmY3c1VdM"
genai.configure(api_key=api_key)

print("=" * 60)
print("Probando modelos de Google AI disponibles")
print("=" * 60)

# Lista de modelos a probar
modelos_a_probar = [
    'gemini-pro',
    'gemini-1.5-flash',
    'gemini-1.5-pro',
    'gemini-pro-vision',
    'gemini-1.0-pro',
    'models/gemini-pro',
    'models/gemini-1.5-flash',
    'models/gemini-1.5-pro',
]

modelos_que_funcionan = []

for modelo_nombre in modelos_a_probar:
    try:
        print(f"\nProbando: {modelo_nombre}")
        model = genai.GenerativeModel(modelo_nombre)
        
        # Probar con una pregunta simple
        response = model.generate_content("Hola")
        print(f"✓ FUNCIONA: {modelo_nombre}")
        print(f"  Respuesta: {response.text[:100]}")
        modelos_que_funcionan.append(modelo_nombre)
        
    except Exception as e:
        print(f"✗ NO FUNCIONA: {modelo_nombre}")
        print(f"  Error: {str(e)[:100]}")

print("\n" + "=" * 60)
print("RESUMEN:")
print("=" * 60)

if modelos_que_funcionan:
    print(f"\n✓ Modelos que funcionan ({len(modelos_que_funcionan)}):")
    for modelo in modelos_que_funcionan:
        print(f"  - {modelo}")
    print(f"\n💡 Usa el primero: {modelos_que_funcionan[0]}")
else:
    print("\n✗ Ningún modelo funcionó")
    print("Verifica tu API key en: https://makersuite.google.com/app/apikey")

print("=" * 60)

