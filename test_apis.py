#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para probar las APIs gratuitas
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_groq():
    """Probar API de Groq"""
    api_key = os.getenv("GROQ_API_KEY")
    print(f"🔑 Groq API Key: {api_key[:20]}..." if api_key else "❌ No Groq API Key")
    
    if not api_key:
        return False, "No API key"
    
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "messages": [{"role": "user", "content": "Hello, respond with just 'OK'"}],
            "model": "llama-3.3-70b-versatile",
            "max_tokens": 10
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            message = result['choices'][0]['message']['content']
            return True, f"✅ Groq funciona: {message}"
        else:
            return False, f"❌ Groq error {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"❌ Groq excepción: {str(e)}"

def test_gemini():
    """Probar API de Gemini"""
    api_key = os.getenv("GOOGLE_API_KEY")
    print(f"🔑 Gemini API Key: {api_key[:20]}..." if api_key else "❌ No Gemini API Key")
    
    if not api_key:
        return False, "No API key"
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{
                "parts": [{"text": "Hello, respond with just 'OK'"}]
            }]
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                message = result['candidates'][0]['content']['parts'][0]['text']
                return True, f"✅ Gemini funciona: {message}"
            else:
                return False, f"❌ Gemini respuesta vacía: {result}"
        else:
            return False, f"❌ Gemini error {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"❌ Gemini excepción: {str(e)}"

def test_deepseek():
    """Probar API de DeepSeek"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    print(f"🔑 DeepSeek API Key: {api_key[:20]}..." if api_key else "❌ No DeepSeek API Key")
    
    if not api_key:
        return False, "No API key"
    
    try:
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "messages": [{"role": "user", "content": "Hello, respond with just 'OK'"}],
            "model": "deepseek-chat",
            "max_tokens": 10
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            message = result['choices'][0]['message']['content']
            return True, f"✅ DeepSeek funciona: {message}"
        else:
            return False, f"❌ DeepSeek error {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"❌ DeepSeek excepción: {str(e)}"

def test_ollama(model="llama3.1:8b", timeout=30):
    """Probar Ollama local con timeout personalizado"""
    try:
        url = "http://localhost:11434/api/generate"
        data = {
            "model": model,
            "prompt": "Hola, responde solo con 'OK'",
            "stream": False
        }
        
        # Ajustar timeout según el modelo
        if "qwen" in model:
            timeout = 45  # Qwen es más lento
        elif "mistral" in model:
            timeout = 40  # Mistral también puede ser más lento
        
        response = requests.post(url, json=data, timeout=timeout)
        
        if response.status_code == 200:
            result = response.json()
            return True, f"✅ Ollama ({model}) responde en {response.elapsed.total_seconds():.1f}s"
        else:
            return False, f"❌ Ollama ({model}) error {response.status_code}"
            
    except Exception as e:
        return False, f"❌ Ollama ({model}) error: {str(e)}"

def test_kimi():
    """Probar Kimi (Moonshot AI)"""
    api_key = os.getenv("KIMI_API_KEY")
    if not api_key:
        return False, "❌ No se encontró KIMI_API_KEY"
    
    try:
        url = "https://api.moonshot.cn/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "moonshot-v1-8k",
            "messages": [{"role": "user", "content": "Responde solo con 'OK'"}],
            "temperature": 0.3
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=15)
        
        if response.status_code == 200:
            return True, "✅ Kimi funciona correctamente"
        else:
            return False, f"❌ Kimi error {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"❌ Kimi no disponible: {str(e)}"

def test_cerebras():
    """Probar Cerebras"""
    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        return False, "❌ No se encontró CEREBRAS_API_KEY"
    
    try:
        url = "https://api.cerebras.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama3.1-8b",
            "messages": [{"role": "user", "content": "Responde solo con 'OK'"}],
            "temperature": 0.3
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=15)
        
        if response.status_code == 200:
            return True, "✅ Cerebras funciona correctamente"
        else:
            return False, f"❌ Cerebras error {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"❌ Cerebras no disponible: {str(e)}"

if __name__ == "__main__":
    print("🧪 Probando APIs gratuitas...\n")
    
    # Lista de todas las pruebas a ejecutar
    test_functions = [
        ("Groq", test_groq),
        ("Gemini", test_gemini),
        ("DeepSeek", test_deepseek),
        ("Cerebras", test_cerebras),
        # ("Mistral AI", test_mistral), # Descomentar si se quiere probar
    ]
    
    for name, test_func in test_functions:
        print(f"🔍 Probando {name}...")
        success, message = test_func()
        print(f"   {message}\n")
    
    # Probar cada modelo de Ollama individualmente
    print("\n🧪 Probando modelos de Ollama...\n")
    ollama_models = [
        "llama3.1:8b",
        "qwen2.5:7b",
        "mistral:7b"
    ]
    
    for model in ollama_models:
        print(f"🔍 Probando Ollama ({model})...")
        success, message = test_ollama(model)
        print(f"   {message}\n")
    
    print("✅ Todas las pruebas completadas.")