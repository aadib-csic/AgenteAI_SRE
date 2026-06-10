# 🤖 Agente SRE Autónomo

**Trabajo de Fin de Máster — Máster en Deep Learning · Universidad Politécnica de Madrid**

Sistema de diagnóstico autónomo de servidores Linux remotos basado en un modelo de lenguaje local (LLaMA 3.1 8B), con capacidades de Self-Healing Agent, cumplimiento normativo RGPD y AI Act, y trazabilidad completa mediante W&B Weave.

---

## 📋 Descripción

El agente interpreta peticiones en lenguaje natural, ejecuta comandos de diagnóstico vía SSH y genera planes de mantenimiento preventivo, operando íntegramente en local para garantizar la soberanía del dato.

**Stack tecnológico:**
- LLM: LLaMA 3.1 8B Instruct (cuantización AWQ 4 bits) via Ollama
- Framework: LangChain 1.0 + LangGraph (patrón ReAct)
- Validación: Pydantic Settings + Structured Output
- Conexión remota: Fabric (SSH con claves ED25519)
- Trazabilidad: W&B Weave
- Interfaz: Streamlit

```
AgenteAI_SRE/
├── src/
│   ├── brain_wandb.py
│   ├── app.py
│   └── requirements.txt
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── docs/
│   ├── anexo_A.pdf
│   └── anexo_B.pdf
├── .env.example
└── .gitignore
```

## ⚙️ Instalación y uso

### Requisitos previos
- Python 3.11+
- Ollama instalado y corriendo
- Modelo LLaMA 3.1 8B descargado: ollama pull llama3.1:8b
- Clave SSH ED25519 con acceso al servidor remoto

### Instalación

1. Clonar el repositorio:
git clone https://github.com/aadib-csic/AgenteAI_SRE.git
cd AgenteAI_SRE

2. Crear entorno virtual e instalar dependencias:
python -m venv .venv
.venv\Scripts\activate
pip install -r src/requirements.txt

3. Configurar variables de entorno:
cp .env.example .env

### Ejecución

python -m streamlit run src/app.py

La interfaz estará disponible en http://localhost:8501

---

## 🐳 Despliegue con Docker

Desde la raíz del repositorio:
cd docker
docker-compose up --build

Descargar el modelo en Ollama (primera vez):
docker exec sre-ollama ollama pull llama3.1:8b

IMPORTANTE: Asegúrate de tener el fichero .env configurado en la raíz del repositorio antes de lanzar los contenedores.

---

## 🔧 Configuración (.env)

SSH_HOST=<ip_o_hostname_del_servidor>
SSH_USER=<usuario_ssh>
SSH_PORT=<puerto_ssh>
SSH_KEY_PATH=<ruta_absoluta_a_clave_privada>
ALLOWED_COMMANDS=uptime,free,df,ls,ps,uname,who,ss,netstat,cat,journalctl,hostname,date,du,nproc,swapon
WANDB_API_KEY=<tu_wandb_api_key>

NUNCA subas el fichero .env al repositorio.

---

## 🛠️ Herramientas del agente

execute_read_only_command - Solo lectura - Ejecuta comandos SSH validados por lista blanca
generate_maintenance_plan - Planificación - Genera planes de mantenimiento con comandos cron
rotate_logs_now - Escritura controlada - Rotación forzada de logs bajo supervisión humana

---

## 🔒 Seguridad y privacidad

- Lista blanca determinista: solo comandos explícitamente permitidos pueden ejecutarse
- Anonimización bidireccional: IPs y usuarios enmascarados en tiempo real
- Inferencia local: ningún dato abandona el perímetro de seguridad del operador
- Cumplimiento: RGPD (2016/679) y AI Act (2024/1689)

---

## 📄 Licencia

Proyecto académico desarrollado como Trabajo de Fin de Máster.
Universidad Politécnica de Madrid · Máster en Deep Learning · 2026
