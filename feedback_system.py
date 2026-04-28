#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sistema de Feedback para el Aprendizaje Autónomo del Agente.
"""

import json
from pathlib import Path
from datetime import datetime

FEEDBACK_LOG_FILE = Path("feedback_log.json")

def log_feedback(user_id: str, question: str, answer: str, feedback: str, details: str = None):
    """Registra el feedback del usuario en un archivo JSON."""
    
    is_useful = "sí" in feedback.lower() or "si" in feedback.lower()
    
    feedback_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "is_useful": is_useful,
        "feedback_response": feedback # Guardamos el 'sí' o 'no' literal
    }
    
    if details:
        feedback_entry["details"] = details
    
    try:
        data = []
        if FEEDBACK_LOG_FILE.exists() and FEEDBACK_LOG_FILE.stat().st_size > 0:
            with open(FEEDBACK_LOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        data.append(feedback_entry)
        with open(FEEDBACK_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"✅ Feedback registrado: {'Útil' if is_useful else 'No útil'}")
    except Exception as e:
        print(f"❌ Error al registrar feedback: {e}")