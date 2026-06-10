FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias para Fabric y SSH
RUN apt-get update && apt-get install -y \
    openssh-client \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY src/ .

# Exponer puerto de Streamlit
EXPOSE 8501

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_PORT=8501

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0"]
