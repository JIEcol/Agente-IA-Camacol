#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Re-entrenamiento (Fine-Tuning) para el Agente CAMACOL.

Este script utiliza el feedback recopilado para especializar un modelo de IA,
mejorando su precisión y eficiencia para las tareas de CAMACOL.
"""

import os
import json
from pathlib import Path
import pandas as pd

# --- VERIFICACIÓN DE DEPENDENCIAS ---
try:
    import torch
    from datasets import Dataset
    from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTTrainer
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Faltan dependencias clave para el re-entrenamiento: {e}")
    print("💡 Para instalarlas, ejecuta: pip install torch transformers datasets peft trl bitsandbytes accelerate")
    DEPENDENCIES_AVAILABLE = False

# --- CONFIGURACIÓN ---

# 1. Archivo de feedback
FEEDBACK_FILE = Path("feedback_log.json")

# 2. Modelo base para el fine-tuning (un modelo pequeño y eficiente)
BASE_MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.2"

# 3. Nombre y ruta para guardar el nuevo modelo especializado
NEW_MODEL_NAME = "camacol-expert-v1"
OUTPUT_DIR = Path("./models") / NEW_MODEL_NAME

def cargar_y_preparar_datos(feedback_file: Path) -> Dataset:
    """Carga el feedback, lo filtra y lo formatea para el entrenamiento."""
    print(f"📄 Cargando datos de feedback desde {feedback_file}...")
    
    if not feedback_file.exists():
        raise FileNotFoundError("No se encontró el archivo de feedback. Asegúrate de que existan interacciones calificadas.")

    with open(feedback_file, 'r', encoding='utf-8') as f:
        feedback_data = json.load(f)
    
    # Filtrar solo las respuestas útiles
    datos_utiles = [item for item in feedback_data if item.get("is_useful")]
    print(f"👍 Encontradas {len(datos_utiles)} interacciones útiles para el entrenamiento.")

    if len(datos_utiles) < 50:
        print("⚠️ Advertencia: El número de ejemplos es bajo (<50). Se recomienda tener al menos unos cientos para un buen re-entrenamiento.")

    # Formatear para el entrenamiento
    formatted_data = []
    for item in datos_utiles:
        # Formato de instrucción/respuesta
        text = f"""<s>[INST] {item['question']} [/INST]
{item['answer']}</s>"""
        formatted_data.append({"text": text})
        
    # Convertir a un Dataset de Hugging Face
    df = pd.DataFrame(formatted_data)
    return Dataset.from_pandas(df)

def main():
    """Función principal para ejecutar el re-entrenamiento."""
    
    if not DEPENDENCIES_AVAILABLE:
        return

    print("🚀 Iniciando Proceso de Re-entrenamiento del Agente CAMACOL...")
    print("="*80)

    try:
        # 1. Cargar y preparar los datos
        dataset = cargar_y_preparar_datos(FEEDBACK_FILE)

        # 2. Configurar el modelo y el tokenizador
        print(f"🧠 Cargando modelo base: {BASE_MODEL_ID}...")
        
        # Configuración de cuantización para usar menos memoria (4-bit)
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16
        )

        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_ID,
            quantization_config=quantization_config,
            device_map="auto", # Usará GPU si está disponible
        )
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
        tokenizer.pad_token = tokenizer.eos_token

        # 3. Configurar PEFT (LoRA) para un entrenamiento eficiente
        model = prepare_model_for_kbit_training(model)
        peft_config = LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM"
        )
        model = get_peft_model(model, peft_config)

        # 4. Configurar los argumentos del entrenamiento
        training_args = TrainingArguments(
            output_dir=str(OUTPUT_DIR),
            per_device_train_batch_size=4,
            gradient_accumulation_steps=4,
            learning_rate=2e-4,
            num_train_epochs=3, # 3 épocas suele ser un buen punto de partida
            logging_steps=10,
            save_strategy="epoch",
            fp16=True, # Usar precisión mixta para acelerar
        )

        # 5. Iniciar el entrenamiento con SFTTrainer de TRL
        print("\n🔥 ¡Iniciando el Fine-Tuning! Esto puede tardar varios minutos...")
        trainer = SFTTrainer(
            model=model,
            train_dataset=dataset,
            peft_config=peft_config,
            dataset_text_field="text",
            max_seq_length=1024,
            args=training_args,
        )

        trainer.train()

        # 6. Guardar el modelo especializado
        print("💾 Guardando el nuevo modelo especializado...")
        trainer.save_model(str(OUTPUT_DIR))

        print("\n🎉 ¡Re-entrenamiento completado con éxito!")
        print(f"✅ El nuevo modelo experto '{NEW_MODEL_NAME}' ha sido guardado en: {OUTPUT_DIR}")
        print("\n💡 PRÓXIMO PASO: Integra este nuevo modelo en 'config.py' con la máxima prioridad para usarlo.")

    except Exception as e:
        print(f"\n❌ ERROR DURANTE EL RE-ENTRENAMIENTO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()