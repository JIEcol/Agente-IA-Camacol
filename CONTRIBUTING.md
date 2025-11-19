# 🤝 Guía de Contribución - Chatbot CAMACOL

## 🔄 Flujo de Trabajo con GitHub

### Actualización Automática

Este proyecto está configurado para actualizarse automáticamente:

1. **Haces cambios localmente**
2. **Git detecta los cambios**
3. **Haces commit y push**
4. **GitHub recibe los cambios**
5. **Streamlit Cloud se actualiza automáticamente** ⚡

### 📝 Pasos para Contribuir

#### 1. Clonar el Repositorio
```bash
git clone https://github.com/JulianTorrest/Chatbot-Camacol.git
cd Chatbot-Camacol
```

#### 2. Crear una Rama para tus Cambios
```bash
git checkout -b tu-nombre-de-rama
# Por ejemplo: git checkout -b fix/actualizar-modelo
```

#### 3. Hacer Cambios
- Edita los archivos necesarios
- Prueba localmente con `streamlit run app.py`

#### 4. Commit y Push
```bash
git add .
git commit -m "Descripción clara de los cambios"
git push origin tu-nombre-de-rama
```

#### 5. Crear Pull Request
- Ve a GitHub
- Click en "Pull Request"
- Describe tus cambios
- Espera la revisión

#### 6. Merge Automático
- Una vez aprobado, haz merge
- Streamlit Cloud se actualizará automáticamente ✨

## 🚀 Actualización Automática en Streamlit Cloud

### ¿Cómo Funciona?

Cuando haces `git push` a la rama `main`:

1. ✅ **GitHub recibe el código**
2. ✅ **GitHub Actions verifica el código** (CI)
3. ✅ **Streamlit Cloud detecta el cambio**
4. ✅ **Streamlit Cloud despliega automáticamente** (CD)

### Configuración Actual

- **Repositorio**: https://github.com/JulianTorrest/Chatbot-Camacol
- **Rama principal**: `main`
- **Archivo principal**: `app.py`
- **Despliegue automático**: ✅ Activado

## 🔧 Workflows Configurados

### 1. CI (Continuous Integration)
Archivo: `.github/workflows/ci.yml`

Verifica:
- ✅ Sintaxis de Python
- ✅ Archivos esenciales presentes
- ✅ No hay API keys expuestas
- ✅ Dependencias correctas

### 2. Streamlit Cloud Notification
Archivo: `.github/workflows/streamlit-cloud.yml`

Notifica cuando:
- Se hace push a `main`
- Streamlit Cloud se actualiza

## 📋 Comandos Útiles

### Verificar estado local
```bash
git status
```

### Ver commits recientes
```bash
git log --oneline -5
```

### Actualizar desde GitHub
```bash
git pull origin main
```

### Hacer push de cambios
```bash
git add .
git commit -m "Tu mensaje"
git push origin main
```

## ⚠️ Importante

### Nunca Subas:
- ❌ API keys
- ❌ Archivos `.streamlit/secrets.toml`
- ❌ Información sensible
- ❌ Archivos grandes innecesarios

### Siempre Revisa:
- ✅ `.gitignore` está actualizado
- ✅ No hay secrets en el código
- ✅ Dependencias en `requirements.txt`
- ✅ README actualizado

## 🐛 Resolución de Problemas

### Streamlit Cloud no se actualiza
- Verifica que hiciste push a `main`
- Revisa los logs en Streamlit Cloud
- Espera 1-2 minutos

### Errores en GitHub Actions
- Revisa los logs del workflow
- Verifica que no hay API keys expuestas
- Asegúrate de que `requirements.txt` es correcto

### Conflictos de merge
```bash
git pull origin main
# Resuelve conflictos
git add .
git commit -m "Resolver conflictos"
git push origin main
```

## 📞 Ayuda

- **Issues**: Abre un issue en GitHub
- **Discusiones**: Usa GitHub Discussions
- **Documentación**: Lee el README.md

---

**¡Gracias por contribuir al proyecto CAMACOL!** 🏗️

