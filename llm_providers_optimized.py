"""
Versión optimizada de llm_providers.py con timeouts, logging y control de reintentos
"""
import requests
import time
import logging
from typing import Dict, List, Tuple, Optional
from config import AIModel, AI_PROVIDERS

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- MEJORA: Cargar la Constitución Ética ---
try:
    with open("ethical_constitution.md", "r", encoding="utf-8") as f:
        ETHICAL_CONSTITUTION = f.read()
    print("Constitución Ética cargada.")
except FileNotFoundError:
    ETHICAL_CONSTITUTION = "No se encontró la constitución ética. Actuar con veracidad y profesionalismo."
    print("No se encontró el archivo ethical_constitution.md.")

# Usaremos Groq para la autocorrección por su velocidad
SELF_CORRECTION_PROVIDER = next((p for p in AI_PROVIDERS if p["name"] == "Groq"), None)

# Constantes de configuración
MAX_REINTENTOS = 3
TIMEOUT_BASE = 350  # segundos (aplica para todos los LLM)
TIMEOUT_OLLAMA = 350  # segundos
TIMEOUT_GROQ = 350  # segundos

class LLMPerformanceTracker:
    """Clase para tracking de rendimiento de LLM"""
    
    def __init__(self):
        self.metrics = {}
    
    def track_call(self, provider: str, component: str, tiempo: float, 
                   reintentos: int, exito: bool, error_msg: str = None):
        """Registra métricas de una llamada al LLM"""
        key = f"{provider}_{component}"
        if key not in self.metrics:
            self.metrics[key] = {
                'total_calls': 0,
                'successful_calls': 0,
                'failed_calls': 0,
                'total_time': 0,
                'total_retries': 0,
                'avg_time': 0,
                'timeout': TIMEOUT_BASE,
                'errors': []
            }
        
        self.metrics[key]['total_calls'] += 1
        self.metrics[key]['total_time'] += tiempo
        self.metrics[key]['total_retries'] += reintentos
        
        if exito:
            self.metrics[key]['successful_calls'] += 1
        else:
            self.metrics[key]['failed_calls'] += 1
            if error_msg:
                self.metrics[key]['errors'].append(error_msg)
        
        self.metrics[key]['avg_time'] = self.metrics[key]['total_time'] / self.metrics[key]['total_calls']
    
    def get_excel_data(self) -> Dict:
        """Retorna datos en formato para Excel"""
        excel_data = {
            'proveedor': [],
            'componente': [],
            'total_llamadas': [],
            'llamadas_exitosas': [],
            'llamadas_fallidas': [],
            'tiempo_promedio': [],
            'reintentos_totales': [],
            'timeout_configurado': [],
            'logging_detalles': []
        }
        
        for key, metrics in self.metrics.items():
            provider, component = key.split('_', 1)
            excel_data['proveedor'].append(provider)
            excel_data['componente'].append(component)
            excel_data['total_llamadas'].append(metrics['total_calls'])
            excel_data['llamadas_exitosas'].append(metrics['successful_calls'])
            excel_data['llamadas_fallidas'].append(metrics['failed_calls'])
            excel_data['tiempo_promedio'].append(round(metrics['avg_time'], 3))
            excel_data['reintentos_totales'].append(metrics['total_retries'])
            excel_data['timeout_configurado'].append(metrics['timeout'])
            
            # Logging detallado
            log_detalle = f"Llamadas: {metrics['total_calls']}, Éxito: {metrics['successful_calls']}, "
            log_detalle += f"Tiempo avg: {metrics['avg_time']:.3f}s, Reintentos: {metrics['total_retries']}"
            if metrics['errors']:
                log_detalle += f", Errores: {', '.join(metrics['errors'][-3:])}"  # Últimos 3 errores
            excel_data['logging_detalles'].append(log_detalle)
        
        return excel_data

# Instancia global del tracker
performance_tracker = LLMPerformanceTracker()

def llamar_api_ia_con_timeout(prompt: str, provider_config: Dict, component: str = "generacion") -> Tuple[Optional[str], Optional[str], Dict]:
    """
    Versión mejorada con timeout, reintentos y logging detallado
    Returns: (respuesta, error, metrics)
    """
    start_time = time.time()
    reintentos = 0
    last_error = None
    
    for intento in range(MAX_REINTENTOS):
        try:
            logger.info(f"Intento {intento + 1}/{MAX_REINTENTOS} para {provider_config['name']} - {component}")
            
            # Llamada al LLM con timeout específico
            respuesta, error = llamar_api_ia_interno(prompt, provider_config)
            
            if respuesta:
                tiempo_total = time.time() - start_time
                metrics = {
                    'tiempo_total': tiempo_total,
                    'reintentos': reintentos,
                    'exito': True,
                    'intento_exitoso': intento + 1
                }
                
                # Registrar en performance tracker
                performance_tracker.track_call(
                    provider_config['name'], component, tiempo_total, reintentos, True
                )
                
                logger.info(f"✅ Éxito en intento {intento + 1} - Tiempo: {tiempo_total:.3f}s")
                return respuesta, None, metrics
            else:
                last_error = error
                reintentos += 1
                logger.warning(f"❌ Intento {intento + 1} fallido: {error}")
                
        except Exception as e:
            last_error = str(e)
            reintentos += 1
            logger.error(f"❌ Excepción en intento {intento + 1}: {e}")
    
    # Todos los intentos fallaron
    tiempo_total = time.time() - start_time
    metrics = {
        'tiempo_total': tiempo_total,
        'reintentos': reintentos,
        'exito': False,
        'ultimo_error': last_error
    }
    
    # Registrar en performance tracker
    performance_tracker.track_call(
        provider_config['name'], component, tiempo_total, reintentos, False, last_error
    )
    
    logger.error(f"❌ Todos los intentos fallaron - Tiempo total: {tiempo_total:.3f}s")
    return None, last_error, metrics

def llamar_api_ia_interno(prompt: str, provider_config: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Función interna que maneja la llamada al LLM según el tipo"""
    # Para Ollama no necesita API key
    if provider_config["type"] == AIModel.OLLAMA:
        return llamar_ollama_optimizado(prompt, provider_config)
    
    # Para el resto, obtener API key
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ModuleNotFoundError:
        pass

    api_key = os.getenv(provider_config["api_key_env"])
    
    if not api_key:
        return None, f"No se encontró la clave de API para {provider_config['name']}"
    
    try:
        # Mapeo de proveedores a funciones
        provider_map = {
            AIModel.GROQ: llamar_groq_optimizado,
            AIModel.GEMINI: llamar_gemini_optimizado,
            AIModel.DEEPSEEK: llamar_deepseek_optimizado,
            AIModel.OPENAI: llamar_openai_optimizado,
            AIModel.CEREBRAS: llamar_cerebras_optimizado,
            AIModel.MISTRAL: llamar_mistral_optimizado,
            AIModel.HUGGINGFACE: llamar_huggingface_optimizado
        }
        
        func = provider_map.get(provider_config["type"])
        if func:
            return func(prompt, api_key, provider_config)
        else:
            return None, f"Proveedor no soportado: {provider_config['name']}"
            
    except Exception as e:
        return None, f"Error con {provider_config['name']}: {str(e)}"

# Funciones optimizadas para cada proveedor
def llamar_openai_compatible_optimizado(prompt: str, api_key: str, config: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Función genérica optimizada para proveedores compatibles con OpenAI"""
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
    
    response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_BASE)
    
    if response.status_code == 200:
        data = response.json()
        return data['choices'][0]['message']['content'], None
    return None, f"Error {response.status_code}: {response.text}"

def llamar_groq_optimizado(prompt: str, api_key: str, config: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Groq optimizado con timeout extendido"""
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
    
    response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_GROQ)
    
    if response.status_code == 200:
        data = response.json()
        return data['choices'][0]['message']['content'], None
    return None, f"Error {response.status_code}: {response.text}"

def llamar_ollama_optimizado(prompt: str, config: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Ollama optimizado con timeout configurable"""
    url = f"{config['base_url']}/api/generate"
    headers = {'Content-Type': 'application/json'}

    timeout_sec = config.get("timeout", TIMEOUT_OLLAMA)
    max_tokens = config.get("max_tokens", 512)
    temperature = config.get("temperature", 0.1)

    payload = {
        "model": config["model"],
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
            "stop": ["```\n\n", "PREGUNTA:", "Usuario:"]
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=(5.0, float(timeout_sec)))
        
        if response.status_code == 200:
            data = response.json()
            return data.get('response', ''), None
        return None, f"Error {response.status_code}: {response.text}"
    except requests.exceptions.ConnectionError:
        return None, "Ollama no está ejecutándose"
    except requests.exceptions.Timeout:
        return None, f"Timeout: Ollama tardó más de {timeout_sec}s"

# Alias para las demás funciones
llamar_deepseek_optimizado = llamar_openai_compatible_optimizado
llamar_openai_optimizado = llamar_openai_compatible_optimizado
llamar_cerebras_optimizado = llamar_openai_compatible_optimizado
llamar_mistral_optimizado = llamar_openai_compatible_optimizado

def llamar_gemini_optimizado(prompt: str, api_key: str, config: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Gemini optimizado"""
    url = f"{config['base_url']}/{config['model']}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_BASE)
    
    if response.status_code == 200:
        data = response.json()
        if 'candidates' in data and data['candidates']:
            return data['candidates'][0]['content']['parts'][0]['text'], None
    return None, f"Error {response.status_code}: {response.text}"

def llamar_huggingface_optimizado(prompt: str, api_key: str, config: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Hugging Face optimizado"""
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
    
    response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_BASE)
    
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0].get('generated_text', ''), None
        return str(data), None
    return None, f"Error {response.status_code}: {response.text}"

def self_correct_response_optimizada(original_prompt: str, draft_response: str) -> Tuple[str, Dict]:
    """
    Versión optimizada de autocorrección con tracking
    """
    if not SELF_CORRECTION_PROVIDER or not draft_response:
        return draft_response, {'correccion_aplicada': False}

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

    # Usar el proveedor optimizado para la corrección
    corrected_response, error, metrics = llamar_api_ia_con_timeout(
        critique_prompt, SELF_CORRECTION_PROVIDER, "correccion"
    )

    if error or not corrected_response:
        logger.warning(f"Error en autocorrección: {error}. Usando respuesta original.")
        return draft_response, {'correccion_aplicada': False, 'error_correccion': error}

    if corrected_response.strip() == "[OK]":
        logger.info("Respuesta borrador aprobada sin cambios")
        return draft_response, {'correccion_aplicada': False, 'metrics': metrics}
    else:
        logger.info("Respuesta AUTOCORREGIDA por el supervisor interno.")
        return corrected_response, {'correccion_aplicada': True, 'metrics': metrics}

# Función principal para compatibilidad
def llamar_api_ia(prompt: str, provider_config: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Función de compatibilidad que usa la versión optimizada"""
    respuesta, error, metrics = llamar_api_ia_con_timeout(prompt, provider_config)
    return respuesta, error

# Función para obtener datos de Excel
def get_performance_excel_data() -> Dict:
    """Retorna datos de rendimiento para Excel"""
    return performance_tracker.get_excel_data()
