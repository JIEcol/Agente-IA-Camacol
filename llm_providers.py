"""
Funciones para llamar a diferentes proveedores de LLM
"""
import requests
from config import AIModel, AI_PROVIDERS

# --- MEJORA: Cargar la Constitución Ética ---
try:
    with open("ethical_constitution.md", "r", encoding="utf-8") as f:
        ETHICAL_CONSTITUTION = f.read()
    print("✅ Constitución Ética cargada.")
except FileNotFoundError:
    ETHICAL_CONSTITUTION = "No se encontró la constitución ética. Actuar con veracidad y profesionalismo."
    print("⚠️ No se encontró el archivo ethical_constitution.md.")

# Usaremos Groq para la autocorrección por su velocidad
SELF_CORRECTION_PROVIDER = next((p for p in AI_PROVIDERS if p["name"] == "Groq"), None)

def llamar_api_ia(prompt, provider_config):
    """Llama a la API del proveedor de IA especificado"""
    # Para Ollama no necesita API key
    if provider_config["type"] == AIModel.OLLAMA:
        return llamar_ollama(prompt, provider_config)
    
    # Para el resto, obtener API key
    import os
    from dotenv import load_dotenv
    load_dotenv()
    # Usamos os.getenv para que funcione en cualquier entorno (Streamlit, Telegram, etc.)
    api_key = os.getenv(provider_config["api_key_env"])
    
    if not api_key:
        return None, f"No se encontró la clave de API para {provider_config['name']}"
    
    try:
        # Mapeo de proveedores a funciones
        provider_map = {
            AIModel.GROQ: llamar_groq,
            AIModel.GEMINI: llamar_gemini,
            AIModel.DEEPSEEK: llamar_deepseek,
            AIModel.OPENAI: llamar_openai,
            AIModel.CEREBRAS: llamar_cerebras,
            AIModel.MISTRAL: llamar_mistral,
            AIModel.HUGGINGFACE: llamar_huggingface
        }
        
        func = provider_map.get(provider_config["type"])
        if func:
            return func(prompt, api_key, provider_config)
        else:
            return None, f"Proveedor no soportado: {provider_config['name']}"
            
    except Exception as e:
        return None, f"Error con {provider_config['name']}: {str(e)}"

def self_correct_response(original_prompt: str, draft_response: str) -> str:
    """
    Implementa la capacidad de autocorrección.
    Critica una respuesta borrador y la refina si es necesario.
    """
    if not SELF_CORRECTION_PROVIDER or not draft_response:
        return draft_response

    critique_prompt = f"""
    Eres un supervisor de calidad de un asistente de IA. Tu tarea es criticar y, si es necesario, corregir la siguiente respuesta.

    PREGUNTA ORIGINAL DEL USUARIO:
    ---
    {original_prompt}
    ---

    RESPUESTA BORRADOR GENERADA:
    ---
    {draft_response}
    ---

    REGLAS DE CRÍTICA:
    1.  **Veracidad:** ¿La respuesta es factualmente correcta y consistente con la pregunta?
    2.  **Completitud:** ¿Responde a TODAS las partes de la pregunta del usuario?
    3.  **Claridad:** ¿Es la respuesta clara, concisa y fácil de entender?
    4.  **Profesionalismo:** ¿Mantiene un tono profesional y adecuado para CAMACOL?
    5.  **Alucinaciones:** ¿Contiene información inventada o que no se puede deducir?

    INSTRUCCIONES:
    - **VERIFICACIÓN ÉTICA OBLIGATORIA:** La respuesta DEBE cumplir con la siguiente Constitución Ética. Si la viola (ej. da un consejo de inversión), la respuesta debe ser corregida para alinearse con los principios.
      ---
      {ETHICAL_CONSTITUTION}
      ---
    - Si la respuesta borrador cumple con todas las reglas, responde EXACTAMENTE con: [OK].
    - Si la respuesta borrador tiene errores o puede ser mejorada, reescríbela para que sea perfecta. NO expliques los cambios, solo proporciona la versión corregida.
    """

    # Usar un proveedor rápido para la corrección
    corrected_response, error = llamar_api_ia(critique_prompt, SELF_CORRECTION_PROVIDER)

    if error:
        print(f"⚠️ Error en autocorrección: {error}. Usando respuesta original.")
        return draft_response

    if corrected_response.strip() == "[OK]":
        return draft_response # El borrador era bueno
    else:
        print("✅ Respuesta AUTOCORREGIDA por el supervisor interno.")
        return corrected_response # Devolver la versión refinada

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
def llamar_groq(prompt, api_key, config):
    """Función específica para Groq con timeout extendido"""
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
    
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    
    if response.status_code == 200:
        data = response.json()
        return data['choices'][0]['message']['content'], None
    return None, f"Error {response.status_code}: {response.text}"

llamar_deepseek = llamar_openai_compatible
llamar_openai = llamar_openai_compatible
llamar_cerebras = llamar_openai_compatible
llamar_mistral = llamar_openai_compatible

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