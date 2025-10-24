# 🚀 Guía de Despliegue - Chatbot CAMACOL

Esta guía te ayudará a desplegar el chatbot CAMACOL en Streamlit Cloud paso a paso.

## 📋 Prerrequisitos

- ✅ Cuenta de GitHub
- ✅ Cuenta de Google AI
- ✅ Cuenta de Streamlit Cloud (gratuita)

## 🔑 Paso 1: Obtener API Key de Google AI

1. Ve a [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Inicia sesión con tu cuenta de Google
3. Click en "Create API Key"
4. Copia la API key generada
5. **Guárdala de forma segura** - la necesitarás después

## 📤 Paso 2: Subir Código a GitHub

### Opción A: Usando GitHub Desktop
1. Descarga [GitHub Desktop](https://desktop.github.com/)
2. File → Add Local Repository
3. Selecciona la carpeta del proyecto
4. Publica el repositorio en GitHub

### Opción B: Usando Git en Terminal

```bash
# Navegar a la carpeta del proyecto
cd "C:\Users\betol\OneDrive\Documentos\IA - Camacol"

# Inicializar git
git init

# Agregar archivos
git add .

# Crear commit
git commit -m "Initial commit: Chatbot CAMACOL"

# Crear repositorio en GitHub primero, luego:
git remote add origin https://github.com/TU_USUARIO/TU_REPOSITORIO.git
git branch -M main
git push -u origin main
```

## 🌐 Paso 3: Desplegar en Streamlit Cloud

1. **Acceder a Streamlit Cloud**
   - Ve a [share.streamlit.io](https://share.streamlit.io)
   - Click en "Sign in"
   - Autoriza con tu cuenta de GitHub

2. **Crear Nueva Aplicación**
   - Click en "New app"
   - Selecciona tu repositorio de GitHub
   - Branch: `main`
   - Main file path: `app.py`
   - Click en "Deploy"

3. **Configurar Secrets**
   - Una vez desplegada, ve a "Settings" (⚙️)
   - Click en "Secrets"
   - Agrega el siguiente contenido:
     ```toml
     GOOGLE_API_KEY = "pega_tu_api_key_aqui"
     ```
   - Click en "Save"
   - La aplicación se reiniciará automáticamente

## ✅ Paso 4: Verificar Despliegue

1. Espera a que el estado muestre "Running"
2. Click en "Open app" o visita la URL proporcionada
3. Prueba el chatbot con una pregunta de ejemplo
4. Verifica que las respuestas sean coherentes

## 🔧 Solución de Problemas

### Error: "No se encontró la clave de API"
- Verifica que agregaste `GOOGLE_API_KEY` en los secrets
- Asegúrate de que la API key sea válida
- Revisa que no haya espacios adicionales en el valor

### Error: "Module not found"
- Verifica que `requirements.txt` contiene todas las dependencias
- Espera a que Streamlit reinstale las dependencias
- Revisa los logs en Streamlit Cloud

### Error de conexión con Google AI
- Verifica que tu API key sea válida
- Revisa el límite de uso de tu cuenta de Google AI
- Espera unos minutos e intenta nuevamente

## 📊 Monitoreo

- Los logs están disponibles en "Settings" → "Show logs"
- Revisa las métricas de uso en el dashboard
- Streamlit Cloud proporciona estadísticas de acceso

## 🔄 Actualizaciones

Para actualizar la aplicación:

1. Haz cambios en tu código local
2. Commit y push a GitHub:
   ```bash
   git add .
   git commit -m "Descripción de cambios"
   git push
   ```
3. Streamlit Cloud detectará los cambios automáticamente
4. La aplicación se actualizará en unos segundos

## 💡 Tips

- ✅ Mantén tus secrets seguros
- ✅ Haz commits frecuentes
- ✅ Prueba localmente antes de desplegar
- ✅ Revisa los logs regularmente
- ✅ Utiliza las sugerencias del sidebar

## 📞 Soporte

- Documentación Streamlit: [docs.streamlit.io](https://docs.streamlit.io)
- Documentación Google AI: [ai.google.dev](https://ai.google.dev)
- Sitio CAMACOL: [camacol.co](https://camacol.co)

---

¡Tu chatbot CAMACOL está listo para usar! 🎉

