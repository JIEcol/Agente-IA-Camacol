# ⚡ Sistema de Actualización Automática

## 🎯 ¿Cómo Funciona?

Este proyecto tiene configurado un sistema de **actualización automática** que conecta:
- 📝 Tus cambios locales
- ☁️ GitHub
- 🚀 Streamlit Cloud

## 🔄 Flujo Automático

```
1. Editas archivos localmente
   ↓
2. Haces git add + commit + push
   ↓
3. GitHub recibe los cambios
   ↓
4. GitHub Actions verifica el código (CI)
   ↓
5. Streamlit Cloud detecta cambios
   ↓
6. Streamlit Cloud se actualiza automáticamente ✨
```

## 🚀 Métodos para Actualizar

### Método 1: Git Helper (Más Fácil) ⭐

Usa el script de ayuda incluido:

```bash
# Modo interactivo
python git_helper.py

# Modo rápido (add + commit + push automático)
python git_helper.py quick
```

### Método 2: Comandos Git Manuales

```bash
# 1. Ver qué cambió
git status

# 2. Agregar cambios
git add .

# 3. Hacer commit
git commit -m "Descripción de tus cambios"

# 4. Subir a GitHub
git push origin main
```

### Método 3: Push Automático Completo

```bash
git add . && git commit -m "Actualización" && git push origin main
```

## 📊 GitHub Actions Configurados

### 1. CI (Continuous Integration)
**Archivo**: `.github/workflows/ci.yml`

Verifica automáticamente:
- ✅ Sintaxis correcta de Python
- ✅ Archivos esenciales presentes
- ✅ No hay API keys expuestas
- ✅ Dependencias correctas

**Se ejecuta**: Cada vez que haces push

### 2. Streamlit Cloud Notification
**Archivo**: `.github/workflows/streamlit-cloud.yml`

Notifica cuando:
- Cambios en la rama `main`
- Streamlit Cloud se actualiza

## 🎯 Actualización en Streamlit Cloud

### Automática (Recomendado)

Streamlit Cloud **SE ACTUALIZA AUTOMÁTICAMENTE** cuando:
1. Haces push a la rama `main`
2. Esperas 1-2 minutos
3. La aplicación se actualiza sin intervención ✨

### Configuración Actual

- **Repositorio**: https://github.com/JulianTorrest/Chatbot-Camacol
- **Rama**: `main`
- **Archivo principal**: `app.py`
- **Despliegue automático**: ✅ **ACTIVADO**

## 💡 Recomendaciones

### Para Cambios Simples

Usa el Git Helper:
```bash
python git_helper.py quick
```

### Para Cambios Importantes

Hazlo paso a paso:
```bash
git status
git add .
git commit -m "Descripción clara"
git push origin main
```

### Verificar Actualización

1. Ve a tu app en Streamlit Cloud
2. Revisa que dice "Running"
3. Espera 1-2 minutos
4. Refresca la página
5. ¡Deberías ver tus cambios!

## ⚠️ Troubleshooting

### ¿No se actualiza automáticamente?

✅ **Verifica**:
- ¿Hiciste push a `main`?
- ¿El código está en GitHub?
- ¿Esperaste 1-2 minutos?

❌ **Si sigue sin funcionar**:
- Ve a Streamlit Cloud
- Click en "..." → "Restart app"
- Revisa los logs

### Errores en GitHub Actions

Ve a: https://github.com/JulianTorrest/Chatbot-Camacol/actions

Revisa:
- ¿Qué paso falló?
- ¿Hay errores de sintaxis?
- ¿Faltan dependencias?

## 📝 Ejemplo Completo

```bash
# 1. Editas app.py (por ejemplo, cambios en la UI)

# 2. Usas Git Helper para subir
python git_helper.py quick

# 3. Esperas 1-2 minutos

# 4. Visitas tu app en Streamlit Cloud

# 5. ¡Ves tus cambios automáticamente!
```

## 🎉 Ventajas del Sistema Automático

- ✅ **Sin configuración manual** en Streamlit Cloud
- ✅ **Verificación automática** del código
- ✅ **Despliegue inmediato** de cambios
- ✅ **Historial completo** en GitHub
- ✅ **Rollback fácil** si algo falla

## 📞 Ayuda

- Lee: `CONTRIBUTING.md` para más detalles
- Usa: `python git_helper.py` para ayuda interactiva
- Revisa: GitHub Actions para logs

---

**¡Tu chatbot ahora se actualiza automáticamente en Streamlit Cloud!** 🚀

