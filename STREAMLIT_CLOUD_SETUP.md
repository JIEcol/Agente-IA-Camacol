# 🚀 Guía de Despliegue en Streamlit Cloud

## ✅ Estado Actual

- ✅ Código subido a GitHub: https://github.com/JulianTorrest/Chatbot-Camacol
- ✅ API Key configurada localmente
- ✅ Dependencias instaladas
- ✅ Aplicación funcionando localmente

## 📋 Pasos para Desplegar en Streamlit Cloud

### Paso 1: Acceder a Streamlit Cloud

1. Ve a **https://share.streamlit.io**
2. Click en **"Sign in"** (esquina superior derecha)
3. Autoriza con tu cuenta de **GitHub**
4. Acepta los permisos solicitados

### Paso 2: Crear Nueva Aplicación

1. Una vez dentro, click en **"New app"** (botón verde)
2. Verás un formulario de configuración:
   - **Repository**: Selecciona `JulianTorrest/Chatbot-Camacol`
   - **Branch**: `main`
   - **Main file path**: `app.py`
3. Click en **"Deploy"** (botón verde)

### Paso 3: Configurar Secrets (CRÍTICO)

Una vez que la aplicación se está desplegando:

1. Click en **"Settings"** (⚙️ icono en la parte superior)
2. En el menú lateral, click en **"Secrets"**
3. En el editor de texto, pega exactamente esto:

```toml
GOOGLE_API_KEY = "AIzaSyD9hbctG1CX63U2-YGDMwUY6RJmY3c1VdM"
```

4. Click en **"Save"** (botón verde)
5. La aplicación se reiniciará automáticamente

### Paso 4: Verificar Despliegue

1. Espera unos minutos a que el estado muestre **"Running"**
2. Click en **"Open app"** o visita la URL que aparece
3. Prueba el chatbot con una pregunta de ejemplo

## 🔍 Verificación

Tu aplicación debería estar disponible en una URL como:
```
https://chatbot-camacol.streamlit.app
```

## 🧪 Probar el Chatbot

Una vez desplegado, prueba estas preguntas:

- "¿Qué es CAMACOL?"
- "¿Cuáles son los servicios principales?"
- "Información sobre el sector constructor"
- "¿Cómo puedo afiliarme?"

## 📊 Monitoreo

- **Logs**: Ve a Settings → Show logs para ver los logs de la aplicación
- **Estadísticas**: El dashboard muestra métricas de uso
- **Actualizaciones**: Cualquier push a GitHub actualiza automáticamente la app

## 🔄 Actualizar la Aplicación

Cuando hagas cambios en el código:

```bash
git add .
git commit -m "Descripción de cambios"
git push
```

Streamlit Cloud detectará los cambios automáticamente y desplegará la nueva versión.

## ⚠️ Solución de Problemas

### Error: "No se encontró la clave de API"
- Verifica que agregaste `GOOGLE_API_KEY` en Settings → Secrets
- Revisa que la API key sea válida
- Verifica que no haya espacios adicionales

### Error: "Module not found"
- Verifica que `requirements.txt` contiene todas las dependencias
- Espera a que Streamlit reinstale las dependencias
- Revisa los logs en Settings → Show logs

### Error de conexión con Google AI
- Verifica que tu API key sea válida
- Revisa el límite de uso en Google AI Studio
- Espera unos minutos e intenta nuevamente

## 🔐 Seguridad

- ✅ Tu API key está protegida en los secrets de Streamlit Cloud
- ✅ No se expone públicamente en el código
- ✅ Solo accesible desde la aplicación desplegada

## 📱 Aplicación Móvil

Tu chatbot será accesible desde cualquier dispositivo:
- 📱 Smartphones
- 💻 Tablets
- 🖥️ Computadoras de escritorio

## 🎉 ¡Listo!

Tu chatbot CAMACOL estará disponible públicamente en Streamlit Cloud.

---

**Nota**: El archivo `.streamlit/secrets.toml` local NO se usa en Streamlit Cloud. 
Debes configurar los secrets desde la interfaz web de Streamlit Cloud.

