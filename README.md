# 🤖 Agente SRE Autónomo

**Trabajo de Fin de Máster — Máster en Deep Learning · Universidad Politécnica de Madrid**

Sistema de diagnóstico autónomo de servidores Linux remotos basado en un modelo de lenguaje local (LLaMA 3.1 8B), con capacidades de Self-Healing Agent, cumplimiento normativo RGPD y AI Act, y trazabilidad completa mediante W&B Weave.

---

## 📋 Descripción

El agente interpreta peticiones en lenguaje natural, ejecuta comandos de diagnóstico vía SSH y genera planes de mantenimiento preventivo, operando íntegramente en local para garantizar la soberanía del dato.

**Stack tecnológico:**
- **LLM:** LLaMA 3.1 8B Instruct (cuantización AWQ 4 bits) via Ollama
- **Framework:** LangChain 1.0 + LangGraph (patrón ReAct)
- **Validación:** Pydantic Settings + Structured Output
- **Conexión remota:** Fabric (SSH con claves ED25519)
- **Trazabilidad:** W&B Weave
- **Interfaz:** Streamlit

---

## 🗂️ Estructura del repositorio

```
AgenteAI_SRE/
├── src/
│   ├── brain_wandb.py      # Núcleo del agente (LLM + tools + pipeline)
│   ├── app.py              # Interfaz Streamlit
│   └── requirements.txt    # Dependencias Python
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── docs/
│   ├── anexo_A.pdf         # Validación cruzada de resultados
│   └── anexo_B.pdf         # Benchmark de evaluación (21 casos)
├── .env.example            # Plantilla de configuración
└── .gitignore
```

---

## ⚙️ Instalación y uso

### Requisitos previos
- Python 3.11+
- [Ollama](https://ollama.com) instalado y corriendo
- Modelo LLaMA 3.1 8B descargado: `ollama pull llama3.1:8b`
- Clave SSH ED25519 con acceso al servidor remoto

### Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/aadib-csic/AgenteAI_SRE.git
cd AgenteAI_SRE

# 2. Crear entorno virtual e instalar dependencias
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r src/requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales SSH y API key de W&B
```

### Ejecución

```bash
python -m streamlit run src/app.py
```

La interfaz estará disponible en `http://localhost:8501`

---

## 🐳 Despliegue con Docker

```bash
# Construir y lanzar los contenedores
cd docker
docker-compose up --build

# Descargar el modelo en Ollama (primera vez)
docker exec sre-ollama ollama pull llama3.1:8b
```

---

## 🔧 Configuración (.env)

```env
SSH_HOST=<ip_o_hostname_del_servidor>
SSH_USER=<usuario_ssh>
SSH_PORT=<puerto_ssh>
SSH_KEY_PATH=<ruta_absoluta_a_clave_privada>
ALLOWED_COMMANDS=uptime,free,df,ls,ps,uname,who,ss,netstat,cat,journalctl,hostname,date,du,nproc,swapon
WANDB_API_KEY=<tu_wandb_api_key>
```

⚠️ **Nunca subas el fichero `.env` al repositorio.**

---

## 🛠️ Herramientas del agente

| Herramienta | Tipo | Descripción |
|---|---|---|
| `execute_read_only_command` | Solo lectura | Ejecuta comandos SSH validados por lista blanca |
| `generate_maintenance_plan` | Planificación | Genera planes de mantenimiento con comandos cron |
| `rotate_logs_now` | Escritura controlada | Rotación forzada de logs bajo supervisión humana |

---

## 📊 Evaluación

El sistema fue evaluado sobre un benchmark de **21 casos** distribuidos en **6 dimensiones**:

| Dimensión | Casos | Resultado |
|---|---|---|
| Funcionalidad | 4 | ✅ 4/4 |
| Diagnóstico | 4 | ✅ 4/4 |
| Seguridad | 4 | ✅ 4/4 |
| Privacidad (RGPD) | 4 | ✅ 4/4 |
| Memoria conversacional | 3 | ✅ 3/3 |
| Mantenimiento preventivo | 2 | ✅ 2/2 |
| **Total** | **21** | **✅ 100%** |

Los informes de evaluación y validación cruzada están disponibles en la carpeta `docs/`.

---

## 🔒 Seguridad y privacidad

- **Lista blanca determinista:** solo comandos explícitamente permitidos pueden ejecutarse
- **Anonimización bidireccional:** IPs y usuarios enmascarados en tiempo real (`[IP_OCULTA]`, `[USUARIO_ANONIMO]`)
- **Inferencia local:** ningún dato abandona el perímetro de seguridad del operador
- **Cumplimiento:** RGPD (2016/679) y AI Act (2024/1689)

---

## 📄 Licencia

Proyecto académico desarrollado como Trabajo de Fin de Máster.
Universidad Politécnica de Madrid · Máster en Deep Learning · 2026
