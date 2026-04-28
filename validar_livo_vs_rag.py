#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Validación para el Sistema LIVO vs. Archivo RAG.

Este script automatiza la verificación de consistencia entre las respuestas
generadas estáticamente en el archivo RAG y las respuestas dinámicas
generadas por el sistema LIVOSQLSystem.

Objetivo:
1. Lee cada pregunta del archivo 'preguntas_oferta_autogeneradas.txt'.
2. Para cada pregunta, consulta al sistema LIVOSQLSystem.
3. Compara el valor numérico de la respuesta del archivo RAG (esperado)
   con el valor de la respuesta de LIVO (real).
4. Reporta cualquier discrepancia encontrada.

Uso:
- Ejecutar este script desde la terminal: python validar_livo_vs_rag.py
"""

import re
import logging
from tqdm import tqdm

# --- Configuración de Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Colores para la consola ---
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    ENDC = '\033[0m'

# --- Importar y Inicializar Sistemas ---
try:
    from livo_sql import LIVOSQLSystem
    from advanced_reasoning import analizar_y_responder # CORRECCIÓN FINAL: El nombre de la función es en español
    LIVO_PATH = r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\Coordenada Urbana\LIVO_total_nov25_.xlsx"
    livo_sql_system = LIVOSQLSystem(LIVO_PATH)
    exito_livo, mensaje_livo = livo_sql_system.inicializar()
    if not exito_livo:
        raise RuntimeError(f"Fallo al inicializar LIVO SQL: {mensaje_livo}")
    logger.info("✅ Sistema LIVO SQL inicializado correctamente.")
except (ImportError, RuntimeError) as e:
    error_msg = str(e)
    if "File is already open" in error_msg or "IO Error" in error_msg:
        logger.error("❌ No se pudo inicializar el sistema LIVO SQL porque el archivo Excel está bloqueado.")
        logger.warning("💡 POSIBLE SOLUCIÓN: Asegúrate de que ningún otro programa (como el bot de Telegram o Microsoft Excel) tenga abierto el archivo 'LIVO_total_oct25_.xlsx'.")
    else:
        logger.error(f"❌ No se pudo inicializar el sistema LIVO SQL. Error: {e}")
    livo_sql_system = None

RAG_FILE_PATH = r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\preguntas_oferta_autogeneradas.txt"

def parse_rag_file(file_path):
    """Parsea el archivo de preguntas y respuestas y devuelve una lista de tuplas (pregunta, respuesta)."""
    qa_pairs = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()] # Leer todas las líneas y quitar vacías

        # Buscar el inicio del primer par P/R
        start_index = -1
        for i, line in enumerate(lines):
            if line.startswith('P:'):
                start_index = i
                break
        
        if start_index != -1:
            # Procesar desde el inicio encontrado, de 2 en 2 (ya que quitamos las líneas vacías)
            for i in range(start_index, len(lines), 2):
                if i + 1 < len(lines) and lines[i].startswith('P:') and lines[i+1].startswith('R:'):
                    pregunta = lines[i].replace('P: ', '').strip()
                    respuesta_esperada = lines[i+1].replace('R: ', '').strip()
                    qa_pairs.append((pregunta, respuesta_esperada))
    except FileNotFoundError:
        logger.error(f"El archivo RAG no fue encontrado en: {file_path}")
    return qa_pairs

def extract_value(text: str) -> str:
    """Extrae el primer valor numérico (con puntos como separadores de miles) de un texto."""
    if not text:
        return "N/A"
    # MEJORA: Buscar un número que esté cerca del final de la frase o seguido por "unidades".
    # Esto evita que se capture el año o "500" de "500 smmlv".
    # Patrón: Busca un número (con puntos) que esté opcionalmente seguido por " unidades".
    match = re.search(r'(\d[\d\.]*)\s*(unidades)?\.', text)
    if not match:
        # Fallback: si el patrón anterior falla, busca cualquier número en la frase.
        match = re.search(r'(\d[\d\.]*)', text)
    return match.group(1) if match else "N/A"

def run_validation():
    """Ejecuta el proceso de validación completo."""
    if not livo_sql_system:
        logger.error("La validación no puede continuar porque el sistema LIVO SQL no está disponible.")
        return

    logger.info(f"Cargando preguntas desde: {RAG_FILE_PATH}")
    qa_pairs = parse_rag_file(RAG_FILE_PATH)
    if not qa_pairs:
        logger.error("No se encontraron pares de P/R para validar.")
        return

    logger.info(f"Iniciando validación de {len(qa_pairs)} preguntas...")

    mismatches = []
    infra_fails = []  # Casos donde no se pudo obtener respuesta confiable

    # Usar tqdm para una barra de progreso
    for pregunta, respuesta_esperada in tqdm(qa_pairs, desc="Validando LIVO vs RAG (sin LLM)"):
        # NUEVO FLUJO: usar solo el motor de reglas de LIVOSQLSystem
        respuesta_real_texto = livo_sql_system.responder_pregunta_sin_llm(pregunta)

        # Si no hubo forma de generar o ejecutar SQL sin LLM, lo registramos como fallo
        if not isinstance(respuesta_real_texto, str) or not respuesta_real_texto.strip():
            infra_fails.append({
                "pregunta": pregunta,
                "respuesta_completa_real": f"No se pudo responder sin LLM: {respuesta_real_texto!r}"
            })
            continue

        if respuesta_real_texto.startswith("Error al ejecutar SQL sin LLM"):
            infra_fails.append({
                "pregunta": pregunta,
                "respuesta_completa_real": respuesta_real_texto
            })
            continue

        # Extraer valores
        valor_esperado = extract_value(respuesta_esperada)
        valor_real = extract_value(respuesta_real_texto)

        if valor_esperado != valor_real:
            mismatches.append({
                "pregunta": pregunta,
                "valor_esperado": valor_esperado,
                "valor_real": valor_real,
                "respuesta_completa_real": respuesta_real_texto
            })

    # --- Reporte Final ---
    print("\n" + "="*50)
    print("VALIDACIÓN COMPLETADA")
    print("="*50)

    if not mismatches:
        print(f"{Colors.GREEN}✅ ¡Éxito! Las {len(qa_pairs) - len(infra_fails)} preguntas evaluadas tuvieron coincidencia entre LIVO y RAG.{Colors.ENDC}")
    else:
        print(f"{Colors.RED}❌ Se encontraron {len(mismatches)} discrepancias de datos entre LIVO y RAG:{Colors.ENDC}")
        for i, error in enumerate(mismatches, 1):
            print(f"\n--- Discrepancia #{i} ---")
            print(f"{Colors.YELLOW}Pregunta:{Colors.ENDC} {error['pregunta']}")
            print(f"{Colors.GREEN}Valor Esperado (RAG):{Colors.ENDC} {error['valor_esperado']}")
            print(f"{Colors.RED}Valor Obtenido (LIVO):{Colors.ENDC} {error['valor_real']}")
            print(f"Respuesta completa de LIVO: {error['respuesta_completa_real']}")

    # Resumen de fallos de infraestructura (reglas/SQL sin LLM)
    if infra_fails:
        print("\n" + "-"*50)
        print(f"{Colors.YELLOW}⚠️ Advertencia:{Colors.ENDC} {len(infra_fails)} preguntas no pudieron ser evaluadas porque la generación de SQL falló en todos los proveedores de IA.")
        if infra_fails:
            print("Ejemplo de mensaje de error:")
            print(infra_fails[0]["respuesta_completa_real"])

if __name__ == '__main__':
    run_validation()
