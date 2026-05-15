import streamlit as st
from chatLocal import procesar_consulta

# Configuración básica de la página
st.set_page_config(page_title="MMT Chat", page_icon="🎬", layout="centered")

css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap');

html, body, [class*="css"]  {
    font-family: 'Outfit', sans-serif !important;
}

/* Animated Gradient Background */
.stApp {
    background: linear-gradient(-45deg, #0f172a, #1e1b4b, #312e81, #1e1b4b);
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
    background: rgba(15, 23, 42, 0.4);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 3rem !important;
    margin-top: 2rem;
    margin-bottom: 2rem;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
    max-width: 900px !important;
}

/* Headers styling */
h1 {
    text-align: center;
    background: linear-gradient(to right, #60a5fa, #c084fc, #f472b6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 600 !important;
    font-size: 3.5rem !important;
    margin-bottom: 0 !important;
    padding-bottom: 0.5rem;
}

div[data-testid="stCaptionContainer"] {
    text-align: center;
    color: #94a3b8 !important;
    font-size: 1.2rem !important;
    margin-bottom: 2rem !important;
}

/* Chat Input Glassmorphism */
div[data-testid="stChatInput"] {
    background: rgba(30, 41, 59, 0.6) !important;
    backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 15px !important;
    padding: 5px !important;
}

div[data-testid="stChatInput"] textarea {
    color: white !important;
}

/* Chat Bubbles */
.stChatMessage {
    background: rgba(30, 41, 59, 0.4) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    border-radius: 15px;
    padding: 10px 15px;
    margin-bottom: 15px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.2);
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
st.caption("Trabajo Fin de Grado — Mario Martínez Turpín")


if "mensajes" not in st.session_state:
    st.session_state.mensajes = [{"rol": "assistant", "contenido": "¡Bienvenido a MMT Chat! Pregúntame sobre tus películas o actores favoritos."}]


for mensaje in st.session_state.mensajes:
    with st.chat_message(mensaje["rol"]):
        st.markdown(mensaje["contenido"])


if pregunta := st.chat_input("Ej: ¿Quién protagonizó El Club de la Lucha?"):
    
    with st.chat_message("user"):
        st.markdown(pregunta)
    st.session_state.mensajes.append({"rol": "user", "contenido": pregunta})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        with st.status("🧠 Pensando...", expanded=True) as status:
            def update_status(texto):
                status.write(texto)
                
            historial = st.session_state.mensajes[:-1]
            generador = procesar_consulta(pregunta, historial, st_callback=update_status)
            
            try:
                first_chunk = next(generador)
                # Contraer el panel de estado una vez resuelto si no es error
                if not first_chunk.startswith("No he ") and not first_chunk.startswith("❌") and "La consulta se generó" not in first_chunk:
                    status.update(label="✅ Consulta resuelta", state="complete", expanded=False)
                else:
                    status.update(label="❌ Consulta fallida", state="error", expanded=True)
                
                full_response += first_chunk
                message_placeholder.markdown(full_response + "▌")
            except StopIteration:
                status.update(label="✅ Consulta resuelta", state="complete", expanded=False)
                
        for chunk in generador:
            full_response += chunk
            message_placeholder.markdown(full_response + "▌")
            
        message_placeholder.markdown(full_response)
            
    st.session_state.mensajes.append({"rol": "assistant", "contenido": full_response})