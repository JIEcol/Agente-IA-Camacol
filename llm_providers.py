"""
Funciones para llamar a diferentes proveedores de LLM
"""
import requests
import streamlit as st
from config import AIModel

def llamar_api_ia(prompt, provider_config):
    """Llama a la API del proveedor de IA especificado"""
    # Para Ollama no necesita API key
    if provider_config["type"] == AIModel.OLLAMA:
        return llamar_ollama(prompt, provider_config)
    
    # Para el resto, obtener API key
    api_key = st.secrets.get(provider_config["api_key_env"])
    
    if not api_key:
        return None, f"No se encontró la clave de API para {provider_config['name']}"
    
    try:
        # Mapeo de proveedores a funciones
        provider_map = {
            AIModel.GROQ: llamar_groq,
            AIModel.GEMINI: llamar_gemini,
            AIModel.DEEPSEEK: llamar_deepseek,
            AIModel.OPENAI: llamar_openai,
            AIModel.KIMI: llamar_kimi,
            AIModel.CEREBRAS: llamar_cerebras,
            AIModel.MISTRAL: llamar_mistral,
            AIModel.COHERE: llamar_cohere,
            AIModel.AI21: llamar_ai21,
            AIModel.HUGGINGFACE: llamar_huggingface
        }
        
        func = provider_map.get(provider_config["type"])
        if func:
            return func(prompt, api_key, provider_config)
        else:
            return None, f"Proveedor no soportado: {provider_config['name']}"
            
    except Exception as e:
        return None, f"Error con {provider_config['name']}: {str(e)}"

# Funciones OpenAI-compatible (la mayoría)
def llamar_openai_compatible(prompt, api_key, config):
    """Función genérica para proveedores compatibles con OpenAI"""
    url = f"{config['base_url']}/chat/completions"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {api_key}"
    }
    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        return data['choices'][0]['message']['content'], None
    return None, f"Error {response.status_code}: {response.text}"

# Usar la función genérica para la mayoría
llamar_groq = llamar_openai_compatible
llamar_deepseek = llamar_openai_compatible
llamar_openai = llamar_openai_compatible
llamar_kimi = llamar_openai_compatible
llamar_cerebras = llamar_openai_compatible
llamar_mistral = llamar_openai_compatible
llamar_ai21 = llamar_openai_compatible

# Funciones específicas
def llamar_gemini(prompt, api_key, config):
    """Implementación específica para Google Gemini"""
    url = f"{config['base_url']}/{config['model']}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        if 'candidates' in data and data['candidates']:
            return data['candidates'][0]['content']['parts'][0]['text'], None
    return None, f"Error {response.status_code}: {response.text}"

def llamar_ollama(prompt, config):
    """Implementación específica para Ollama (local, sin API key)"""
    url = f"{config['base_url']}/api/generate"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "model": config["model"],
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('response', ''), None
        return None, f"Error {response.status_code}: {response.text}"
    except requests.exceptions.ConnectionError:
        return None, "Ollama no está ejecutándose"
    except requests.exceptions.Timeout:
        return None, "Timeout: Ollama tardó demasiado"

def llamar_cohere(prompt, api_key, config):
    """Implementación específica para Cohere"""
    url = f"{config['base_url']}/chat"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {api_key}"
    }
    payload = {
        "model": config["model"],
        "message": prompt,
        "temperature": 0.7
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        return data['text'], None
    return None, f"Error {response.status_code}: {response.text}"

def llamar_huggingface(prompt, api_key, config):
    """Implementación específica para Hugging Face"""
    url = f"{config['base_url']}/{config['model']}"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {api_key}"
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": 0.7,
            "max_new_tokens": 2000
        }
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0].get('generated_text', ''), None
        return str(data), None
    return None, f"Error {response.status_code}: {response.text}"