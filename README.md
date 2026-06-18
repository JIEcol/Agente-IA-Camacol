# Chatbot CAMACOL

Chatbot inteligente para la Cámara Colombiana de la Construcción (CAMACOL) con soporte para Streamlit y Telegram.

## Descripción

Este proyecto es un chatbot que responde consultas sobre el sector constructor en Colombia, utilizando:
- **Base de datos LIVO** (DuckDB) con información de vivienda
- **RAG (Retrieval Augmented Generation)** para consultas documentales
- **Múltiples LLMs**: Google AI (Gemini), OpenAI, Groq, Ollama
- **Interfaz web** con Streamlit
- **Bot de Telegram** para acceso móvil

## Tabla de Contenidos

- [Requisitos Previos](#-requisitos-previos)
- [Instalación Local](#-instalación-local)
- [Ejecución Streamlit Local](#️-ejecución-streamlit-local)
- [Configuración Telegram Bot](#-configuración-telegram-bot)
- [Variables de Entorno](#-variables-de-entorno)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Solución de Problemas](#-solución-de-problemas)

---

## ✅ Requisitos Previos

### Software Necesario

| Requisito | Versión | Descarga |
|-----------|---------|----------|
| **Python** | 3.9+ | [python.org](https://www.python.org/downloads/) |
| **Git** | Cualquiera | [git-scm.com](https://git-scm.com/) |
| **Editor** | Recomendado VS Code | [code.visualstudio.com](https://code.visualstudio.com/) |

### Verificar Instalación

```bash
# Verificar Python
python --version
# Debe mostrar Python 3.9.x o superior

# Verificar pip
pip --version

# Verificar Git
git --version
```

---

## Instalación Local

### Paso 1: Clonar el Repositorio

```bash
git clone https://github.com/JulianTorrest/Chatbot-Camacol.git
cd Chatbot-Camacol
```

### Paso 2: Crear Entorno Virtual (Recomendado)

**Windows:**
```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
venv\Scripts\activate

# Verificar que está activado (debe mostrar el nombre del entorno en el prompt)
```

**Linux/Mac:**
```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
source venv/bin/activate
```

**Desactivar entorno virtual (cuando termines):**
```bash
deactivate
```

### Paso 3: Instalar Dependencias

```bash
# Asegúrate de que el entorno virtual esté activado
# El prompt debe mostrar (venv) al inicio

# Instalar todas las dependencias
pip install -r requirements.txt

# Verificar instalación
pip list
```

**Si hay errores de instalación:**
```bash
# Actualizar pip primero
python -m pip install --upgrade pip

# Instalar con opción de trusted-host (si hay problemas de SSL)
pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

---

## Ejecución Streamlit Local

### Paso 1: Configurar API Keys

Crear archivo de configuración de Streamlit:

```bash
# Crear directorio .streamlit si no existe
mkdir .streamlit

# Crear archivo de secrets
echo. > .streamlit\secrets.toml
```

Editar el archivo `.streamlit/secrets.toml`:

```toml
# API Keys de LLMs (al menos una es requerida)
GOOGLE_API_KEY = "tu_clave_de_google_ai_aqui"
OPENAI_API_KEY = "tu_clave_de_openai_aqui"
GROQ_API_KEY = "tu_clave_de_groq_aqui"

# Base de datos DuckDB
DUCKDB_PATH = "LIVO/LIVO/LIVO_total_abr26_.duckdb"

# Configuración opcional
DEFAULT_LLM_PROVIDER = "google"
DEFAULT_LLM_MODEL = "gemini-1.5-flash"
```

**Obtener API Keys:**
- **Google AI (Gemini)**: [Google AI Studio](https://makersuite.google.com/app/apikey)
- **OpenAI**: [platform.openai.com](https://platform.openai.com/api-keys)
- **Groq**: [console.groq.com](https://console.groq.com/keys)

### Paso 2: Ejecutar la Aplicación

```bash
# Asegúrate de estar en el directorio correcto y con el entorno activado
cd Chatbot-Camacol
venv\Scripts\activate

# Ejecutar Streamlit
streamlit run app.py
```

**Salida esperada:**
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

Abre tu navegador en: [http://localhost:8501](http://localhost:8501)

### Paso 3: Detener la Aplicación

En la terminal donde ejecutaste Streamlit, presiona:
```bash
Ctrl + C
```

---

## Configuración Telegram Bot

### Paso 1: Crear Bot en Telegram

1. Abre Telegram y busca: `@BotFather`
2. Envía el comando: `/newbot`
3. Sigue las instrucciones:
   - Nombre del bot: `Chatbot CAMACOL`
   - Username: `camacol_chatbot` (debe terminar en _bot)
4. BotFather te dará un **TOKEN** (guárdalo de forma segura)

### Paso 2: Configurar Token en el Proyecto

**Opción A: Archivo .env (Recomendado para desarrollo)**

Crear archivo `.env` en la raíz del proyecto:

```bash
# Crear archivo .env
echo TELEGRAM_TOKEN=tu_token_aqui > .env
echo TELEGRAM_WEBHOOK_URL=https://tu-url.ngrok-free.app >> .env
```

Contenido del archivo `.env`:
```env
TELEGRAM_TOKEN=tu_token_de_telegram_aqui
TELEGRAM_WEBHOOK_URL=https://tu-url.ngrok-free.app
```

**Opción B: Variables de Entorno del Sistema (Windows)**

```cmd
setx TELEGRAM_TOKEN "tu_token_aqui"
setx TELEGRAM_WEBHOOK_URL "https://tu-url.ngrok-free.app"
```

**Reiniciar la terminal después de configurar variables de entorno**

### Paso 3: Ejecutar Bot de Telegram

```bash
# Asegúrate de tener el entorno virtual activado
venv\Scripts\activate

# Ejecutar el bot
python bot_telegram.py
```

**Salida esperada:**
```
Bot de Telegram iniciado...
Esperando mensajes...
```

### Paso 4: Probar el Bot

1. Abre Telegram
2. Busca tu bot por el username que creaste (ej: `@camacol_chatbot`)
3. Presiona "Iniciar" o envía `/start`
4. Envía una pregunta sobre el sector constructor

### Paso 5: Detener el Bot

En la terminal, presiona:
```bash
Ctrl + C
```

---

## Variables de Entorno

### Lista Completa de Variables

| Variable | Requerida | Descripción | Valor de Ejemplo |
|----------|-----------|-------------|------------------|
| `GOOGLE_API_KEY` | Sí* | API Key de Google AI | `AIza...` |
| `OPENAI_API_KEY` | Sí* | API Key de OpenAI | `sk-...` |
| `GROQ_API_KEY` | Sí* | API Key de Groq | `gsk_...` |
| `TELEGRAM_TOKEN` | Para Telegram | Token del bot | `123456:ABC...` |
| `TELEGRAM_WEBHOOK_URL` | Para webhook | URL del servidor | `https://...` |
| `DUCKDB_PATH` | No | Ruta a la base de datos | `LIVO/LIVO/...` |

*Al menos una API Key de LLM es requerida

### Archivos de Configuración

```
Chatbot-Camacol/
├── .streamlit/
│   └── secrets.toml          # Configuración de Streamlit
├── .env                       # Variables de entorno (no subir a Git)
├── config_secrets.toml.example # Ejemplo de configuración
└── .gitignore                 # Excluye archivos sensibles
```

### Archivos que NO deben subirse a Git

Asegúrate de que `.gitignore` incluya:

```gitignore
# Secrets y configuración local
.streamlit/secrets.toml
.env
*.env
config.toml

# Entornos virtuales
venv/
env/
ENV/

# Caché de Python
__pycache__/
*.py[cod]
*$py.class
```

---

## Estructura del Proyecto

```
Chatbot-Camacol/
│
├── app.py                          # Aplicación Streamlit principal
├── bot_telegram.py                 # Bot de Telegram
├── livo_sql.py                     # Sistema SQL para consultas LIVO
├── livo_sql_optimized.py         # Versión optimizada de consultas
├── reasoning_system.py             # Sistema de razonamiento avanzado
├── rag_system.py                   # Sistema RAG para documentos
├── coyuntura_sql.py                # Consultas de coyuntura
│
├── requirements.txt                # Dependencias del proyecto
├── config.py                       # Configuración centralizada
├── llm_providers.py                # Proveedores de LLM
├── user_profile_manager.py         # Gestión de perfiles de usuario
│
├── 📁 LIVO/                           # Base de datos DuckDB
│   └── LIVO/
│       └── LIVO_total_abr26_.duckdb
│
├── 📁 .streamlit/                     # Configuración de Streamlit
│   ├── config.toml                    # Configuración de tema
│   └── secrets.toml                   # API Keys (NO subir a Git)
│
├── 📁 historial_chats/                # Historial de conversaciones
├── 📁 temp/                           # Archivos temporales
│
└── 📄 README.md                       # Este archivo
```

---

## Solución de Problemas

### Error: "ModuleNotFoundError: No module named 'streamlit'"

**Causa:** Entorno virtual no activado o dependencias no instaladas

**Solución:**
```bash
# Activar entorno virtual
venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### Error: "No se encontró la API key"

**Causa:** Archivo de secrets no configurado

**Solución:**
1. Crear carpeta `.streamlit`
2. Crear archivo `secrets.toml` con las API keys
3. Verificar que el archivo tenga el formato correcto

### Error: "No se encontraron resultados" en consultas LIVO

**Causa:** Base de datos no encontrada o ruta incorrecta

**Solución:**
```bash
# Verificar que el archivo existe
dir LIVO\LIVO\LIVO_total_abr26_.duckdb

# Si no existe, configurar la ruta correcta en secrets.toml
```

### Error: "Address already in use" (Puerto ocupado)

**Causa:** Otra instancia de Streamlit está corriendo

**Solución:**
```bash
# Cambiar el puerto
streamlit run app.py --server.port 8502
```

### Problemas con el bot de Telegram

| Problema | Solución |
|----------|----------|
| Bot no responde | Verificar que el TOKEN sea correcto |
| Error de webhook | Usar polling en desarrollo: cambiar `webhook=True` a `webhook=False` en `bot_telegram.py` |
| Bot duplicado | Eliminar el proceso anterior con Ctrl+C y reiniciar |

### Comandos Útiles para Diagnóstico

```bash
# Verificar versión de Python
python --version

# Ver dependencias instaladas
pip list

# Verificar archivo de secrets existe
dir .streamlit\secrets.toml

# Ver variables de entorno (Windows)
set | findstr TELEGRAM

# Test de conexión a base de datos
python -c "import duckdb; conn = duckdb.connect('LIVO/LIVO/LIVO_total_abr26_.duckdb'); print('OK')"
```

---

## � Comandos Rápidos de Referencia

### Streamlit Local

```bash
# Activar entorno
venv\Scripts\activate

# Ejecutar
streamlit run app.py

# Ejecutar en puerto alternativo
streamlit run app.py --server.port 8502
```

### Telegram Bot

```bash
# Activar entorno
venv\Scripts\activate

# Ejecutar bot
python bot_telegram.py

# Ejecutar en background (Linux/Mac)
python bot_telegram.py &
```

### Mantenimiento

```bash
# Actualizar dependencias
pip install --upgrade -r requirements.txt

# Generar nuevo requirements.txt
pip freeze > requirements.txt

# Limpiar caché de Python
python -m pycache.remove
```

---

## Soporte

Para reportar problemas o solicitar ayuda:

- **Email**: contacto@camacol.co
- **Sitio web**: [camacol.co](https://camacol.co)

---

## Licencia

Este proyecto es propiedad de **CAMACOL - Cámara Colombiana de la Construcción**.

---

**Última actualización:** Junio 2026
