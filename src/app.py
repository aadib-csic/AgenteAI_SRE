import re
import streamlit as st
from brain_wandb import brain, SREBrain
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="SRE Agent Audit-Ready", layout="centered")

# Inicializar brain una sola vez por sesión
if "brain" not in st.session_state:
    st.session_state.brain = SREBrain()

st.title("🛡️ SRE Agent: Diagnóstico Autónomo")
st.info("Seguridad: Lista Blanca + Sanitización + Logs de Auditoría activos.")

# Historial de mensajes en pantalla
if "messages" not in st.session_state:
    st.session_state.messages = []

# Dibujar mensajes previos
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


def clean_output(text: str) -> str:
    """Elimina tool calls JSON que el modelo filtra a veces en su respuesta."""
    # Eliminar solo bloques JSON que contengan execute_read_only_command
    text = re.sub(
        r'\{"name"\s*:\s*"execute_read_only_command"[^}]*\}',
        "", text, flags=re.DOTALL
    )
    return text.strip() or text  # si queda vacío devuelve el original


# Input de usuario
if prompt := st.chat_input("¿Qué diagnóstico necesitas?"):

    # Forzar español en el mensaje enviado al agente
    prompt_for_agent = f"{prompt}\n\n[IMPORTANTE: responde en español]"

    # Mostrar pregunta original al usuario (sin el añadido)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generar y mostrar respuesta
    with st.chat_message("assistant"):
        with st.spinner("Consultando servidor..."):
            try:
                response = st.session_state.brain.run(prompt_for_agent)
                final_text = clean_output(response["output"])
            except Exception as e:
                final_text = f"⚠️ Error: {str(e)}"
            st.markdown(final_text)
            st.session_state.messages.append({"role": "assistant", "content": final_text})