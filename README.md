# 🏗️ Chatbot CAMACOL

Chatbot personalizado para la Cámara Colombiana de la Construcción (CAMACOL) utilizando Streamlit Cloud y Google AI (Gemini).

## 📋 Descripción

Este proyecto es un chatbot inteligente diseñado para proporcionar información sobre CAMACOL y el sector constructor en Colombia. Utiliza Google AI (Gemini) como modelo de lenguaje grande (LLM) para responder preguntas de manera contextualizada y precisa.

## ✨ Características

- 🤖 Chatbot inteligente con Google AI (Gemini)
- 🏗️ Información real sobre CAMACOL
- 💬 Interfaz conversacional intuitiva
- 📊 Estadísticas del sector constructor colombiano
- 🌐 Desplegado en Streamlit Cloud
- 🔒 Gestión segura de API keys

## 🚀 Instalación Local

### Requisitos

- Python 3.9 o superior
- Cuenta de Google AI (para obtener API key)

### Pasos

1. **Clonar el repositorio**
   ```bash
   git clone https://github.com/JulianTorrest/Chatbot-Camacol.git
   cd Chatbot-Camacol
   ```

2. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar API Key de Google AI**
   
   Crea un archivo `.streamlit/secrets.toml` con tu API key:
   ```toml
   GOOGLE_API_KEY = "tu_clave_de_google_ai_aqui"
   ```
   
   Para obtener tu API key:
   - Ve a [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Crea una nueva API key
   - Cópiala y pégala en el archivo secrets.toml

4. **Ejecutar la aplicación**
   ```bash
   streamlit run app.py
   ```

## 🌐 Despliegue en Streamlit Cloud

### Repositorio en GitHub
- **URL**: [https://github.com/JulianTorrest/Chatbot-Camacol](https://github.com/JulianTorrest/Chatbot-Camacol)

### Pasos para desplegar

1. **El código ya está en GitHub** ✅
   - Repositorio: https://github.com/JulianTorrest/Chatbot-Camacol
   - Branch: main

2. **Conectar con Streamlit Cloud**
   - Ve a [share.streamlit.io](https://share.streamlit.io)
   - Inicia sesión con tu cuenta de GitHub
   - Click en "New app"
   - Selecciona tu repositorio
   - Main file path: `app.py`
   - Click en "Deploy"

3. **Configurar Secrets en Streamlit Cloud**
   - Ve a tu aplicación desplegada
   - Click en "Settings" (⚙️)
   - Click en "Secrets"
   - Agrega:
     ```toml
     GOOGLE_API_KEY = "tu_clave_de_google_ai_aqui"
     ```
   - Guarda los cambios
   - La aplicación se reiniciará automáticamente

## 📚 Información Incluida en el Chatbot

El chatbot tiene acceso a información real sobre:

- **CAMACOL**: Historia, servicios, estructura organizacional
- **Servicios**: Gestión documental, información técnica, capacitación
- **Estadísticas**: Datos del sector constructor en Colombia
- **Eventos**: Ferias, seminarios, certificaciones
- **Normatividad**: Regulaciones del sector construcción

## 🎯 Uso del Chatbot

El chatbot puede responder preguntas sobre:

- ¿Qué es CAMACOL?
- ¿Cuáles son los servicios de CAMACOL?
- Información sobre el sector constructor en Colombia
- Procesos de afiliación
- Eventos y capacitaciones
- Estadísticas del sector
- Normatividad de construcción

## 🛠️ Tecnologías Utilizadas

- **Streamlit**: Framework para aplicaciones web
- **Google AI (Gemini)**: Modelo de lenguaje grande
- **Python**: Lenguaje de programación

## 📝 Estructura del Proyecto

```
.
├── app.py                      # Aplicación principal
├── requirements.txt            # Dependencias
├── README.md                   # Documentación
└── .streamlit/
    └── secrets.toml.example    # Ejemplo de configuración
```

## 🔐 Seguridad

- ⚠️ **NUNCA** subas tu API key a GitHub
- Usa `.gitignore` para excluir archivos sensibles
- Configura los secrets solo en Streamlit Cloud
- No compartas tu API key públicamente

## 🤝 Contribuciones

Este proyecto fue desarrollado específicamente para CAMACOL. Para sugerencias o mejoras, por favor contacta al equipo de desarrollo.

## 📞 Contacto

- **Sitio web CAMACOL**: [camacol.co](https://camacol.co)
- **Email**: contacto@camacol.co

## 📄 Licencia

Este proyecto es propiedad de CAMACOL - Cámara Colombiana de la Construcción.

---

Desarrollado con ❤️ para CAMACOL

