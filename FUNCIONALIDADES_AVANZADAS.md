# 🚀 Funcionalidades Avanzadas del Chatbot CAMACOL

## ✨ Nuevas Funcionalidades Implementadas

### 1. 🔐 Autenticación

**Características:**
- Login con contraseña antes de acceder al chatbot
- Contraseña configurable en secrets
- Protección de acceso no autorizado

**Uso:**
- Contraseña por defecto: `camacol2024`
- Configura en Streamlit Cloud → Settings → Secrets:
  ```toml
  CHATBOT_PASSWORD = "tu_contraseña_segura"
  ```

### 2. 💾 Historial Persistente

**Características:**
- Guarda automáticamente cada conversación en archivos JSON
- Almacena en carpeta `historial_chats/`
- Timestamp en cada conversación
- Formato JSON legible

**Funciones:**
- **Guardar Chat Actual**: Guarda la conversación actual
- **Cargar Chat Anterior**: Carga cualquier conversación guardada
- Guardado automático después de cada respuesta

**Ubicación:** `historial_chats/chat_YYYYMMDD_HHMMSS.json`

### 3. 📤 Exportar Conversaciones

**Formatos disponibles:**
- **TXT**: Texto plano simple
- **JSON**: Formato estructurado con metadatos

**Características:**
- Descarga directa desde el sidebar
- Incluye timestamp y todos los mensajes
- Formato legible y estructurado

### 4. 🔍 Sistema de Búsqueda

**Características:**
- Busca en toda la conversación actual
- Busca por palabras clave
- Muestra resultados con contexto
- Indica cantidad de resultados encontrados

**Uso:**
- Escribe en el campo de búsqueda del sidebar
- Los resultados aparecen automáticamente
- Puedes hacer clic en resultados para navegar

### 5. 🎨 Temas (Light/Dark Mode)

**Características:**
- Tema Claro (por defecto)
- Tema Oscuro
- Cambio instantáneo
- Preferencia guardada en sesión

**Uso:**
- Selector en el sidebar
- Cambio inmediato sin recargar

### 6. 💬 Soporte de Código y Fórmulas

**Características:**
- Renderizado automático de código
- Soporte para fórmulas matemáticas
- Formato Markdown completo
- Sintaxis destacada

**Formato:**
- El LLM puede incluir código en sus respuestas
- Formato automático con indentación
- Fácil de leer y copiar

### 7. 🗑️ Gestión de Chat

**Funciones:**
- Limpiar chat actual
- Borrar historial visual
- Mantener mensaje de bienvenida
- Reset completo

### 8. 💡 Preguntas Sugeridas

**Características:**
- 6 preguntas predefinidas
- Acceso rápido a información común
- Botones interactivos
- Layout en 2 columnas

## 📋 Cómo Usar las Nuevas Funcionalidades

### Acceso Inicial

1. **Iniciar Sesión**
   - Entra a la aplicación
   - Ingresa la contraseña: `camacol2024`
   - Click en "Iniciar Sesión"

2. **Cambiar Contraseña**
   - Ve a Streamlit Cloud → Settings → Secrets
   - Agrega: `CHATBOT_PASSWORD = "nueva_contraseña"`

### Guardar y Cargar Chats

**Guardar Chat:**
- Click en "💾 Guardar Chat Actual" en el sidebar
- Se guarda automáticamente con timestamp

**Cargar Chat:**
- Ve a "Cargar Chat Anterior" en el sidebar
- Selecciona un chat de la lista
- Click en "📂 Cargar Chat"

### Exportar Conversaciones

1. Haz una conversación o carga una existente
2. Ve al sidebar → "Exportar"
3. Click en "📄 TXT" o "📦 JSON"
4. Descarga el archivo

### Buscar en Conversación

1. Ve al sidebar → "Búsqueda"
2. Escribe la palabra o frase
3. Los resultados aparecen automáticamente
4. Revisa los mensajes encontrados

### Cambiar Tema

1. Ve al sidebar → "Tema"
2. Selecciona "Claro" o "Oscuro"
3. El cambio es instantáneo

## 🎯 Configuración en Streamlit Cloud

### Secrets Requeridos

En Settings → Secrets de Streamlit Cloud:

```toml
# API Key de Google AI
GOOGLE_API_KEY = "AIzaSyD9hbctG1CX63U2-YGDMwUY6RJmY3c1VdM"

# Contraseña del chatbot (opcional, por defecto: camacol2024)
CHATBOT_PASSWORD = "tu_contraseña_segura"
```

## 📊 Estructura de Archivos

```
Proyecto/
├── app.py                          # Aplicación principal
├── requirements.txt                # Dependencias
├── .streamlit/
│   └── secrets.toml               # Configuración local
├── historial_chats/                # Carpeta de historiales
│   ├── chat_20250124_120000.json
│   ├── chat_20250124_130000.json
│   └── ...
└── config_secrets.toml.example      # Ejemplo de configuración
```

## 🔄 Actualización Automática

Los cambios se despliegan automáticamente en Streamlit Cloud cuando:
1. Haces push a GitHub
2. Esperas 1-2 minutos
3. La aplicación se actualiza

## 🛠️ Funcionalidades Técnicas

### Historial JSON

```json
{
  "timestamp": "2025-01-24T12:00:00",
  "messages": [
    {
      "role": "assistant",
      "content": "Mensaje..."
    },
    {
      "role": "user",
      "content": "Pregunta..."
    }
  ]
}
```

### Exportación TXT

```
Chatbot CAMACOL - Conversación
==================================================

[Usuario]:
¿Qué es CAMACOL?

[Asistente]:
CAMACOL es...

```

## ⚠️ Notas Importantes

- La carpeta `historial_chats/` se crea automáticamente
- Los historiales se ignoran en Git (no se suben)
- La contraseña por defecto debe cambiarse en producción
- El tema oscuro es experimental (puede mejorarse)

## 🚀 Próximas Mejoras Posibles

- [ ] Soporte para imágenes
- [ ] Soporte para voz (speech-to-text)
- [ ] Base de datos para búsqueda avanzada
- [ ] Análisis de sentimientos
- [ ] Métricas de uso
- [ ] Múltiples usuarios con roles
- [ ] Tema oscuro mejorado

---

**¡Todas las funcionalidades están implementadas y funcionando!** 🎉

