#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo para la gestión de perfiles de usuario.
Guarda y recupera preferencias para personalizar la experiencia del chatbot.
"""

import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

# Importar LLM para la inferencia de perfil
from llm_providers import llamar_api_ia
from config import AI_PROVIDERS

class UserProfileManager:
    """Gestiona los perfiles y preferencias de los usuarios."""

    def __init__(self, profile_path: str = 'user_profiles.json'):
        self.profiles_file = Path(profile_path)
        self.profiles = self._load_profiles()

    def _load_profiles(self) -> Dict:
        """
        Carga los perfiles desde un archivo JSON, con recuperación de errores robusta.
        Si el archivo está corrupto, intenta recuperarlo. Si falla, crea uno nuevo.
        """
        if not self.profiles_file.exists() or self.profiles_file.stat().st_size == 0:
            return {}

        try:
            with open(self.profiles_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"⚠️ Error de JSON en {self.profiles_file}: {e}. Intentando recuperar...")
            try:
                # Mover el archivo corrupto para no perderlo
                corrupt_path = self.profiles_file.with_suffix('.json.corrupt')
                self.profiles_file.rename(corrupt_path)
                print(f"   Archivo corrupto renombrado a: {corrupt_path.name}")
            except OSError:
                pass # Si no se puede renombrar, no es crítico
            
            # Crear un archivo nuevo y vacío
            print("❌ La recuperación falló. Se creará un archivo de perfiles nuevo y vacío.")
            self._save_profiles_to_file({}) # Guardar un JSON vacío
            return {}
        except IOError as e:
            print(f"⚠️ Error de I/O cargando perfiles: {e}. Se creará un archivo nuevo.")
            return {}

    def _save_profiles_to_file(self, profiles_data: Dict):
        """Guarda un diccionario de perfiles específico en el archivo JSON."""
        try:
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump(profiles_data, f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"❌ Error guardando perfiles en archivo: {e}")

    def _save_profiles(self):
        """Guarda los perfiles actuales en el archivo JSON."""
        self._save_profiles_to_file(self.profiles)

    def get_profile(self, user_id: str) -> Optional[Dict]:
        """Obtiene el perfil de un usuario."""
        return self.profiles.get(user_id)

    def update_profile(self, user_id: str, conversation_state: Dict):
        """
        Actualiza el perfil de un usuario con las entidades de la conversación actual.
        """
        if not user_id:
            return

        if user_id not in self.profiles:
            self.profiles[user_id] = {
                "preferences": {},
                "last_seen": None,
                "inferred_profile": "General" # Perfil por defecto
            }
        
        profile = self.profiles[user_id]

        for entity, value in conversation_state.items():
            if value:
                if entity not in profile["preferences"]:
                    profile["preferences"][entity] = {}
                
                profile["preferences"][entity][value] = profile["preferences"][entity].get(value, 0) + 1

        profile["last_seen"] = datetime.now().isoformat()
        self._save_profiles()
        print(f"✅ Perfil de usuario '{user_id}' actualizado.")

    def inferir_perfil(self, user_id: str, historial_preguntas: list) -> str:
        """
        Usa un LLM para inferir el perfil del usuario basado en su historial de preguntas.
        """
        if not historial_preguntas or not user_id in self.profiles:
            return "General"

        # Usar un proveedor rápido para esta tarea
        provider = next((p for p in AI_PROVIDERS if p["name"] == "Groq"), None)
        if not provider:
            return self.profiles[user_id].get("inferred_profile", "General")

        preguntas_str = "\n".join([f"- {q}" for q in historial_preguntas[-5:]]) # Analizar las últimas 5 preguntas

        prompt = f"""
        Analiza el siguiente historial de preguntas de un usuario y clasifícalo en uno de los siguientes perfiles: [Estudiante, Economista/Investigador, Directivo/Gerencial, General].

        - **Estudiante:** Preguntas generales, definiciones ("¿Qué es...?"), resúmenes.
        - **Economista/Investigador:** Preguntas técnicas, sobre variaciones, correlaciones, datos específicos, metodología.
        - **Directivo/Gerencial:** Preguntas sobre KPIs, resúmenes ejecutivos, rankings, competencia, riesgos, oportunidades.
        - **General:** Preguntas variadas sin un patrón claro.

        Historial de Preguntas:
        {preguntas_str}

        Responde solo con la categoría del perfil (ej: "Economista/Investigador").
        """

        perfil_inferido, _ = llamar_api_ia(prompt, provider)

        if perfil_inferido and perfil_inferido.strip() in ["Estudiante", "Economista/Investigador", "Directivo/Gerencial", "General"]:
            self.profiles[user_id]["inferred_profile"] = perfil_inferido.strip()
            self._save_profiles()
            return perfil_inferido.strip()
        
        return self.profiles[user_id].get("inferred_profile", "General")

# Instancia global para ser usada por otros módulos
user_profile_manager = UserProfileManager()
