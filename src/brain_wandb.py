import os
import re
import json
import uuid
from datetime import datetime
from typing import Any, Literal
from fabric import Connection
from dotenv import load_dotenv
import weave

# --- PYDANTIC ---
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- LANGCHAIN 1.0 ---
from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import before_model
from langchain.messages import RemoveMessage
from langchain.tools import tool
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime
from langchain_core.runnables import RunnableConfig

load_dotenv()


# validación de .env al arrancar 

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    SSH_HOST: str
    SSH_USER: str
    SSH_PORT: int = 2422
    SSH_KEY_PATH: str
    ALLOWED_COMMANDS: str
    WANDB_API_KEY: str

settings = Settings()


# ── Pydantic Structured Output ────────────────────────────────────────────────

class SREResponse(BaseModel):
    """Respuesta estructurada del agente SRE."""

    security_status: Literal["PERMITIDO", "BLOQUEADO"] = Field(
        description="Si la operación fue permitida o bloqueada por el protocolo de seguridad"
    )
    risk_level: Literal["BAJO", "MEDIO", "ALTO", "BLOQUEADO"] = Field(
        description="Nivel de riesgo evaluado para la operación solicitada"
    )
    action: str = Field(
        description="Acción concreta tomada por el agente, en una frase"
    )
    summary: str = Field(
        description="Resumen técnico claro de los resultados para el ingeniero"
    )
    compliance_note: str = Field(
        description="Nota de cumplimiento normativo RGPD/AI Act si aplica, si no 'N/A'"
    )


# ── Pydantic: esquema de entrada del tool de mantenimiento ───────────────────

class MaintenanceTask(BaseModel):
    """Parámetros validados para la tarea de mantenimiento preventivo."""
    task_type: Literal["clean_tmp", "rotate_logs", "backup_configs"] = Field(
        description="Tipo de tarea de mantenimiento a programar"
    )
    frequency: Literal["daily", "weekly", "monthly"] = Field(
        description="Frecuencia de ejecución de la tarea"
    )


# ── Weave (W&B) ───────────────────────────────────────────────────────────────
weave.init(project_name="sre-brain-tfm")


# ── Logging ───────────────────────────────────────────────────────────────────

def log_event(event_type: str, details: dict) -> None:
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": event_type,
        "details": details,
    }
    with open("audit_trail.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


# ── SSH diagnóstico ───────────────────────────────────────────────────────────

@weave.op()
def _ssh_execute(command: str) -> str:
    """Capa trazable por Weave: ejecuta el comando SSH y devuelve la salida."""
    try:
        c = Connection(
            host=settings.SSH_HOST,
            user=settings.SSH_USER,
            port=settings.SSH_PORT,
            connect_kwargs={
                "key_filename": os.path.normpath(settings.SSH_KEY_PATH),
                "timeout": 30,
                "look_for_keys": False,
                "allow_agent": False,
            },
        )
        result = c.run(command, hide=True)
        output = result.stdout.strip()

        # 1. IPs simples
        output = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP_OCULTA]", output)
        # 2. IPs con puerto
        output = re.sub(r"\[IP_OCULTA\]:\d+", "[IP:PUERTO_OCULTO]", output)
        # 3. Usuarios
        output = re.sub(r"(?:user|username|login|name)[:= ]+[\w-]+", "[USUARIO_ANONIMO]", output, flags=re.IGNORECASE)
        # 4. Hostnames
        output = re.sub(r"\b[\w-]+\.(?:local|com|es|net|org|io)\b", "[HOSTNAME_ANONIMO]", output, flags=re.IGNORECASE)
        # 5. Emails
        output = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[EMAIL_ANONIMO]", output)

        return output if output else "Comando ejecutado con éxito (sin salida)."

    except Exception as e:
        raise RuntimeError(f"Error SSH: {e}")


@tool
def execute_read_only_command(command: str) -> str:
    """
    Ejecuta comandos de diagnóstico de SOLO LECTURA vía SSH.
    Usa las credenciales definidas en las variables de entorno.
    Devuelve la salida del servidor o un mensaje de error/bloqueo.
    """
    log_event("TOOL_ATTEMPT", {"command": command})

    allowed_commands = [c.strip() for c in settings.ALLOWED_COMMANDS.split(",") if c.strip()]
    base_command = command.strip().split()[0].lower()

    if base_command not in allowed_commands:
        log_event("SECURITY_BLOCK", {"command": command})
        return f"BLOQUEO: El comando '{base_command}' no está en la lista autorizada."

    try:
        output = _ssh_execute(command)
        log_event("TOOL_SUCCESS", {"command": command})
        return output
    except RuntimeError as e:
        log_event("TOOL_ERROR", {"command": command, "error": str(e)})
        return str(e)


# ── Tool: Rotación forzada de logs ────────

@weave.op()
def _ssh_rotate_logs() -> str:
    """Ejecuta logrotate vía SSH — conexión independiente de la lista blanca."""
    c = Connection(
        host=settings.SSH_HOST,
        user=settings.SSH_USER,
        port=settings.SSH_PORT,
        connect_kwargs={
            "key_filename": os.path.normpath(settings.SSH_KEY_PATH),
            "timeout": 30,
            "look_for_keys": False,
            "allow_agent": False,
        },
    )
    result = c.run("logrotate -f /etc/logrotate.conf 2>&1", hide=True)
    return result.stdout.strip() or "Rotación completada sin salida."


@tool
def rotate_logs_now() -> str:
    """
    Ejecuta la rotación forzada de logs del sistema en el servidor remoto.
    Usar cuando los logs están saturados o el disco está lleno por culpa de logs.
    No recibe parámetros. Ejecuta logrotate inmediatamente.
    Esta es una acción de mantenimiento controlada que requiere confirmación previa del usuario.
    """
    log_event("ROTATE_LOGS_ATTEMPT", {})
    try:
        output = _ssh_rotate_logs()
        log_event("ROTATE_LOGS_SUCCESS", {"output": output[:200]})
        return (
            f"✅ Rotación de logs ejecutada correctamente.\n\n"
            f"Salida del servidor:\n{output}\n\n"
            f"⚠️  Acción registrada en el log de auditoría."
        )
    except Exception as e:
        log_event("ROTATE_LOGS_ERROR", {"error": str(e)})
        return f"Error al ejecutar la rotación de logs: {str(e)}"



CRON_SCHEDULES: dict[str, str] = {
    "daily":   "0 2 * * *",   # cada día a las 2:00
    "weekly":  "0 2 * * 0",   # cada domingo a las 2:00
    "monthly": "0 2 1 * *",   # día 1 de cada mes a las 2:00
}

TASK_COMMANDS: dict[str, str] = {
    "clean_tmp":      "find /tmp -type f -atime +7 -delete",
    "rotate_logs":    "logrotate -f /etc/logrotate.conf",
    "backup_configs": "cp /etc/*.conf /var/backup/configs/",
}

TASK_DESCRIPTIONS: dict[str, str] = {
    "clean_tmp":      "Limpieza de ficheros temporales en /tmp con más de 7 días",
    "rotate_logs":    "Rotación forzada de logs del sistema",
    "backup_configs": "Copia de seguridad de configuraciones /etc/*.conf",
}


@tool
def generate_maintenance_plan(task_type: str, frequency: str) -> str:
    """
    Genera un plan de mantenimiento preventivo con el comando cron listo para aplicar.
    El agente propone el plan y el ingeniero decide si lo implementa (Human-in-the-Loop).
    Usar cuando se detecten problemas recurrentes: disco lleno, logs saturados
    o configuraciones sin respaldar.

    Valores EXACTOS para task_type: clean_tmp | rotate_logs | backup_configs
    Valores EXACTOS para frequency: daily | weekly | monthly
    """
    log_event("MAINTENANCE_ATTEMPT", {"task_type": task_type, "frequency": frequency})

    # Normalizar entrada
    t = str(task_type).strip().strip("'\" `").lower()
    f = str(frequency).strip().strip("'\" `").lower()

    # Mapas de traducción simples
    tasks = {
        "clean_tmp":      ("Limpieza de /tmp",          "find /tmp -type f -atime +7 -delete"),
        "rotate_logs":    ("Rotación de logs",           "logrotate -f /etc/logrotate.conf"),
        "backup_configs": ("Backup de configuraciones",  "cp /etc/*.conf /var/backup/configs/"),
    }
    schedules = {
        "daily":   "0 2 * * *",
        "weekly":  "0 2 * * 0",
        "monthly": "0 2 1 * *",
    }

    if t not in tasks:
        return f"Tarea no válida: '{t}'. Usa: clean_tmp | rotate_logs | backup_configs"
    if f not in schedules:
        return f"Frecuencia no válida: '{f}'. Usa: daily | weekly | monthly"

    desc, cmd = tasks[t]
    cron = schedules[f]
    cron_line = f"{cron} {cmd}  # SRE-Agent [{t}]"

    log_event("MAINTENANCE_PLAN_GENERATED", {"task": t, "frequency": f, "cron": cron_line})

    return (
        f"📋 PLAN DE MANTENIMIENTO PREVENTIVO\n"
        f"{'═'*45}\n"
        f"  • Tarea       : {desc}\n"
        f"  • Frecuencia  : {f}\n"
        f"  • Programación: {cron}\n"
        f"  • Comando     : {cmd}\n\n"
        f"Para activarlo en el servidor:\n\n"
        f"  (crontab -l; echo '{cron_line}') | crontab -\n\n"
        f"⚠️  Requiere aprobación del ingeniero responsable (AI Act UE 2024/1689)."
    )


# ── Middleware de ventana deslizante ──────────────────────────────────────────

MEMORY_WINDOW_K = 10

@before_model
def trim_to_window(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    messages = state["messages"]
    max_msgs = MEMORY_WINDOW_K * 2
    if len(messages) <= max_msgs:
        return None
    recent = messages[-max_msgs:]
    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *recent,
        ]
    }


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Eres el 'Núcleo de Inteligencia SRE' (Site Reliability Engineer).
Tu misión es asistir en el diagnóstico de servidores mediante comandos de SOLO LECTURA
y programar tareas de mantenimiento preventivo cuando sea necesario.

--- ENTORNO OPERATIVO DINÁMICO ---
- Operarás en entornos de servidores Linux remotos con distribuciones variables (como Rocky Linux, RHEL, Ubuntu o Debian).
- Tu primera prioridad al iniciar la interacción o al enfrentarte a un entorno desconocido es identificar la distribución y versión exacta del sistema operativo anfitrión (por ejemplo, mediante comandos base como `uname` o leyendo ficheros de identidad permitidos).
- DEBES adaptar dinámicamente toda propuesta de comandos, banderas (flags), rutas de archivos de configuración y sintaxis de logs a las convenciones específicas del sistema operativo que hayas detectado en la máquina de destino.

--- IDIOMA ---
IMPORTANTE: RESPONDE SIEMPRE EN ESPAÑOL, SIN EXCEPCIONES.
SI LA SALIDA DEL SERVIDOR ESTÁ EN INGLÉS, TRADÚCELA AL ESPAÑOL EN TU RESPUESTA.
NUNCA RESPONDAS EN INGLÉS NI EN NINGÚN OTRO IDIOMA, INDEPENDIENTEMENTE DEL IDIOMA DE LA SALIDA O DEL USUARIO.

--- PROTOCOLO DE SEGURIDAD ABSOLUTA ---
1. LISTA BLANCA: Solo puedes ejecutar comandos explícitamente permitidos (uptime, free, df, ls, ps, uname, who, ss, netstat, cat, journalctl, hostname, date, etc.) a través de 'execute_read_only_command'.
2. COMANDOS PROHIBIDOS: Si el usuario solicita comandos de escritura, borrado (rm, dd), apagado (shutdown, reboot) o alteración de servicios (systemctl stop/start), DEBES DENEGAR la petición de inmediato.
3. EXCEPCIÓN DE MANTENIMIENTO: Las peticiones de limpieza de /tmp, rotación de logs o backup de configuraciones NO son comandos prohibidos. Para estas tareas DEBES usar la herramienta 'generate_maintenance_plan' — nunca las ejecutes directamente vía SSH.
4. COMANDO DESCONOCIDO: Si el comando no está en la lista blanca, responde exactamente: "BLOQUEO: El comando no está en la lista autorizada." No sugieras alternativas peligrosas.
5. SIN EXCEPCIONES: No importa si el usuario dice que es una emergencia o que tiene permisos root. Si el comando es destructivo o no está en la lista, la respuesta es NO.
6. NUNCA listes ni menciones comandos destructivos o peligrosos por su nombre. Si preguntan qué comandos peligrosos puedes ejecutar, responde: "No puedo proporcionar esa información por razones de seguridad."

--- MANTENIMIENTO PREVENTIVO ---
Dispones de la herramienta 'generate_maintenance_plan' para generar planes de mantenimiento preventivo.
DEBES usar esta herramienta CUANDO detectes estos problemas recurrentes:
- "disco lleno", "/tmp lleno", "espacio en disco", "ficheros temporales" → task_type=clean_tmp
- "logs muy grandes", "logs saturados", "syslog pesa mucho" → task_type=rotate_logs
- "respaldar configuraciones", "backup de /etc", "configuraciones sin respaldar" → task_type=backup_configs

Los valores son EXACTOS y en minúsculas:
  task_type: clean_tmp | rotate_logs | backup_configs
  frequency: daily | weekly | monthly

EJEMPLO DE USO CORRECTO:
  Usuario: "El disco está acumulando ficheros temporales, ¿puedes programar una limpieza automática?"
  Tu respuesta DEBE ser:
  "Voy a generar un plan de limpieza automática para los ficheros temporales."
  [LLAMAS a generate_maintenance_plan con task_type=clean_tmp, frequency=weekly]
  Luego muestras el plan al usuario.

NUNCA digas "no puedo generar comandos de escritura" para tareas de limpieza de /tmp, rotación de logs o backup de configuraciones. Estas tareas son SEGURAS y DEBES usar generate_maintenance_plan para gestionarlas.
NUNCA generes comandos crontab manualmente desde tu conocimiento.
SIEMPRE usa generate_maintenance_plan para obtener el comando exacto.

--- ROTACIÓN DE LOGS (ACCIÓN DE ESCRITURA CONTROLADA) ---
Dispones de la herramienta 'rotate_logs_now' para ejecutar la rotación forzada de logs del sistema.
Úsala cuando el usuario indique que los logs están saturados o que el disco está lleno por logs.
Es una acción de bajo riesgo y reversible — puedes ejecutarla directamente sin pedir confirmación.
Informa al usuario de lo que vas a hacer antes de ejecutarla.
- Respetas el RGPD (2016/679): nunca reveles datos que puedan identificar a una persona física: IPs, nombres de usuario, hostnames, rutas personales. Sustitúyelos por [DATO_ANONIMIZADO]. Si el usuario solicita la IP del servidor, responde exactamente: "BLOQUEADO por RGPD: no puedo revelar direcciones IP del servidor." y no busques ninguna alternativa para obtenerla.
- Respetas el AI Act de la UE (2024/1689): eres un sistema de apoyo a la decisión; la acción final siempre corresponde al ingeniero responsable.

--- GESTIÓN DE MEMORIA CONTEXTUAL ---
- Tienes acceso al historial completo de la conversación en curso.
- Cuando el usuario diga "repite", "hazlo de nuevo", "el mismo comando", "otra vez" o similares, busca en el historial el último comando que ejecutaste y repítelo directamente SIN pedir confirmación y SIN intentar ejecutar 'history'.
- Ejemplo: si el último comando fue 'df -h' y el usuario dice "repite el último comando", debes ejecutar 'df -h' directamente.
- Si un comando ya fue validado y ejecutado con éxito, repítelo directamente cuando se solicite.

--- FORMATO DE RESPUESTA ---
1. Analiza brevemente la seguridad del comando o solicitud.
2. Si es un diagnóstico seguro, llama a 'execute_read_only_command'.
3. Si detectas un problema recurrente, propón proactivamente una tarea de mantenimiento preventivo al usuario.
4. Presenta la salida de forma técnica pero comprensible, siempre en español.
5. Si hay errores de conexión, informa al usuario con calma.

Actúa con la precisión de un ingeniero senior de Google o Amazon."""


# ── Agente ────────────────────────────────────────────────────────────────────

class SREBrain:
    def __init__(self) -> None:
        self.llm = ChatOllama(model="llama3.1:8b", temperature=0)
        self.tools = [
            execute_read_only_command,
            generate_maintenance_plan,
            rotate_logs_now,
        ]
        self._session_id = "default"

        self.structured_llm = self.llm.with_structured_output(SREResponse)

        self.agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=SYSTEM_PROMPT,
            middleware=[trim_to_window],
            checkpointer=InMemorySaver(),
        )

    @weave.op()
    def run(self, user_input: str, session_id: str | None = None) -> dict:
        """
        Ejecuta el agente. Si detecta intención de mantenimiento preventivo,
        invoca el tool directamente sin depender del LLM.
        """
        thread = session_id or self._session_id
        config: RunnableConfig = {"configurable": {"thread_id": thread}}

        # ── Comandos prohibidos tienen PRIORIDAD ──────────────────────────────
        input_lower = user_input.lower()
        prohibited_triggers = ["rm ", "rm-", "dd ", "shutdown", "reboot",
                               "systemctl stop", "systemctl kill", "mkfs", "fdisk"]
        is_prohibited = any(p in input_lower for p in prohibited_triggers)

        # ── Detección de intención de mantenimiento ───────────────────────────
        maintenance_triggers = [
            "limpiar", "limpieza", "clean", "tmp", "temporales",
            "rotar", "rotate", "logs saturados", "backup", "respaldar",
            "mantenimiento", "plan de mantenimiento", "preventivo",
            "programar", "automática", "acumulando", "ficheros temporales",
            "borrar temporales", "liberar espacio"
        ]

        if not is_prohibited and any(trigger in input_lower for trigger in maintenance_triggers):
            if any(k in input_lower for k in ["tmp", "temporales", "limpiar disco", "clean", "ficheros temporales", "acumulando", "liberar espacio"]):
                task_type, frequency = "clean_tmp", "weekly"
            elif any(k in input_lower for k in ["log", "rotar", "rotate", "logs saturados"]):
                task_type, frequency = "rotate_logs", "weekly"
            elif any(k in input_lower for k in ["backup", "respald", "config"]):
                task_type, frequency = "backup_configs", "monthly"
            else:
                task_type, frequency = "clean_tmp", "weekly"

            plan = generate_maintenance_plan.invoke({"task_type": task_type, "frequency": frequency})
            output_text = plan
            log_event("AGENT_SUCCESS", {
                "thread_id": thread,
                "input": user_input[:100],
                "output_length": len(output_text),
                "risk_level": "BAJO",
                "security_status": "PERMITIDO",
                "tool_forced": "generate_maintenance_plan",
            })
            return {
                "output": output_text,
                "structured": SREResponse(
                    security_status="PERMITIDO",
                    risk_level="BAJO",
                    action=f"Plan de mantenimiento generado: {task_type}",
                    summary=output_text[:300],
                    compliance_note="Supervisión humana requerida (AI Act 2024/1689)",
                ).model_dump(),
            }

        # ── Flujo normal del agente ───────────────────────────────────────────
        # 1. Ejecutar el agente
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config,
        )
        output_text = result["messages"][-1].content

        # Sanitizar datos personales en la respuesta en lenguaje natural
        output_text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP_OCULTA]", output_text)
        output_text = re.sub(
            r"\b(root|admin|ubuntu|ec2-user|centos|debian|oracle|user\d*)\b",
            "[USUARIO_ANONIMO]",
            output_text,
            flags=re.IGNORECASE,
        )

        # 2. Estructurar la respuesta con Pydantic
        try:
            structured: SREResponse = self.structured_llm.invoke(
                f"Analiza esta respuesta de un agente SRE y extrae los campos solicitados:\n\n{output_text}"
            )
        except Exception:
            structured = SREResponse(
                security_status="PERMITIDO",
                risk_level="BAJO",
                action="Respuesta generada",
                summary=output_text[:300],
                compliance_note="N/A",
            )

        log_event("AGENT_SUCCESS", {
            "thread_id": thread,
            "input": user_input[:100],
            "output_length": len(output_text),
            "risk_level": structured.risk_level,
            "security_status": structured.security_status,
        })

        return {
            "output": output_text,
            "structured": structured.model_dump(),
        }

    def reset_conversation(self) -> None:
        self._session_id = str(uuid.uuid4())
        log_event("SESSION_RESET", {"new_session_id": self._session_id})


brain = SREBrain()
