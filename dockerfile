# Usar una imagen base oficial de Python
FROM python:3.9-slim

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias del sistema operativo necesarias para librerías como camelot-py
# Ghostscript y las dependencias de OpenCV son cruciales
RUN apt-get update && apt-get install -y \
    ghostscript \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copiar el archivo de requerimientos primero para aprovechar el cache de Docker
COPY requirements.txt .

# Instalar las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el resto del código fuente y datos al directorio de trabajo
COPY . .

# Exponer el puerto que usa Streamlit
EXPOSE 8501

# Comando por defecto para ejecutar la aplicación Streamlit
# Se usa CMD para que pueda ser sobreescrito por docker-compose
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
