# 🔄 Reiniciar Streamlit Cloud

## ⚠️ Problema Actual

Streamlit Cloud está mostrando el error del modelo antiguo `gemini-pro` porque está usando una versión cacheada del código.

## ✅ Solución: Reiniciar la Aplicación

### Paso 1: Subir Cambios a GitHub

Los cambios ya están subidos. Si necesitas subir cambios nuevos:

```bash
python git_helper.py quick
```

### Paso 2: Reiniciar en Streamlit Cloud

1. Ve a tu aplicación en **https://share.streamlit.io**
2. Click en los **"..."** (tres puntos) en la esquina superior derecha
3. Selecciona **"Restart app"**
4. Espera 1-2 minutos
5. La aplicación se reiniciará con el código más reciente

### Paso 3: Verificar

1. Haz una pregunta al chatbot
2. El modelo debería funcionar correctamente con `gemini-1.5-flash`

## 🆘 Si Sigue Sin Funcionar

### Opción A: Actualizar Secrets

1. Ve a **Settings** → **Secrets**
2. Verifica que tu API key sea correcta:
   ```toml
   GOOGLE_API_KEY = "AIzaSyD9hbctG1CX63U2-YGDMwUY6RJmY3c1VdM"
   ```
3. Click en **Save**
4. La app se reiniciará automáticamente

### Opción B: Borrar y Re-desplegar

1. Ve a **Settings** → **General**
2. Scroll hasta abajo
3. Click en **"Delete app"**
4. Click en **"New app"**
5. Selecciona el mismo repositorio
6. Click en **Deploy**

## 📝 Nota Importante

El problema NO es el código. El código está correcto con `gemini-1.5-flash`.

El problema es que **Streamlit Cloud necesita reiniciarse** para cargar la nueva versión.

---

**Después de reiniciar, el chatbot debería funcionar perfectamente** ✅

