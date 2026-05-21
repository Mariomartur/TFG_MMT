import streamlit as st
import time
from chatLocal import procesar_consulta


st.set_page_config(page_title="MMT Chat", page_icon="🎬", layout="centered")

css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap');

html, body, [class*="css"]  {
    font-family: 'Outfit', sans-serif !important;
}

/* Animated Gradient Background adapting to Streamlit Theme */
.stApp {
    background: linear-gradient(-45deg, var(--background-color), var(--secondary-background-color), var(--primary-color), var(--secondary-background-color));
    background-size: 400% 400%;
    animation: gradientBG 15s ease infinite;
}

@keyframes gradientBG {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* Glassmorphism Main Container */
.main .block-container {
    background: var(--background-color);
    opacity: 0.95;
    border-radius: 20px;
    border: 1px solid var(--secondary-background-color);
    padding: 3rem !important;
    margin-top: 2rem;
    margin-bottom: 2rem;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.15);
    max-width: 900px !important;
}


h1 {
    text-align: center;
    color: var(--text-color) !important;
    font-weight: 700 !important;
    font-size: 3.5rem !important;
    margin-bottom: 0 !important;
    padding-bottom: 0.5rem;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
}

div[data-testid="stCaptionContainer"] {
    text-align: center;
    color: var(--text-color) !important;
    opacity: 0.7;
    font-size: 1.2rem !important;
    margin-bottom: 2rem !important;
}

/* Chat Input Glassmorphism */
div[data-testid="stChatInput"] {
    background: var(--background-color) !important;
    border: 1px solid var(--secondary-background-color) !important;
    border-radius: 15px !important;
    padding: 5px !important;
}

div[data-testid="stChatInput"] textarea {
    color: var(--text-color) !important;
}

/* Chat Bubbles */
.stChatMessage {
    background: var(--secondary-background-color) !important;
    border: 1px solid rgba(128, 128, 128, 0.4) !important;
    border-radius: 15px;
    padding: 10px 15px;
    margin-bottom: 15px;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.25);
    backdrop-filter: blur(5px);
    animation: fadeIn 0.4s ease-out;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Top Padding Remover */
header[data-testid="stHeader"] {
    background: transparent !important;
}
</style>
"""
st.markdown(css, unsafe_allow_html=True)

st.title("MMT Chat")


if "mensajes" not in st.session_state:
    st.session_state.mensajes = [{"rol": "assistant", "contenido": "¡Bienvenido a MMT Chat! Pregúntame sobre tus películas o actores favoritos."}]


for mensaje in st.session_state.mensajes:
    with st.chat_message(mensaje["rol"]):
        st.markdown(mensaje["contenido"])


if pregunta := st.chat_input("Ej: ¿Quién dirigió Harry Potter y la piedra filosofal?"):
    
    with st.chat_message("user"):
        st.markdown(pregunta)
    st.session_state.mensajes.append({"rol": "user", "contenido": pregunta})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        start_time = time.time()
        with st.status("🧠 Pensando...", expanded=True) as status:
            def update_status(texto):
                status.write(texto)
                
            historial = st.session_state.mensajes[:-1]
            generador = procesar_consulta(pregunta, historial, st_callback=update_status)
            
            try:
                first_chunk = next(generador)
                tiempo_t = time.time() - start_time
                if not first_chunk.startswith("No he ") and not first_chunk.startswith("❌") and "La consulta se generó" not in first_chunk:
                    status.update(label=f"✅ Consulta resuelta en {tiempo_t:.2f}s", state="complete", expanded=False)
                else:
                    status.update(label=f"❌ Consulta fallida en {tiempo_t:.2f}s", state="error", expanded=True)
                
                full_response += first_chunk
                message_placeholder.markdown(full_response + "▌")
            except StopIteration:
                tiempo_t = time.time() - start_time
                status.update(label=f"✅ Consulta resuelta en {tiempo_t:.2f}s", state="complete", expanded=False)
                
        for chunk in generador:
            full_response += chunk
            message_placeholder.markdown(full_response + "▌")
            
        message_placeholder.markdown(full_response)
            
    st.session_state.mensajes.append({"rol": "assistant", "contenido": full_response})