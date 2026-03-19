import streamlit as st
import requests
import pandas as pd
from streamlit_js_eval import get_geolocation
from datetime import datetime

# Configuramos la web para que parezca que esto lo ha hecho un profesional
st.set_page_config(page_title="ASIR GPS Control", page_icon="🕒")

# La dirección del que hace el trabajo sucio (el Backend)
API_URL = "http://backend:8000"

# Memoria de pez de Streamlit: si no guardamos esto, olvida quién eres cada 2 segundos
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = {}

# --- BLOQUE DE SEGURIDAD (O "EL MURO DE TRUMP") ---
if not st.session_state.logged_in:
    st.title("🔐 Identifícate o vete")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Clave", type="password")
        if st.form_submit_button("Entrar"):
            try:
                res = requests.post(f"{API_URL}/login?email={email}&password={password}")
                if res.status_code == 200:
                    st.session_state.logged_in = True
                    st.session_state.user_info = res.json()
                    st.rerun()
                else:
                    st.error("¿Ni tu email sabes poner? Reinténtalo.")
            except:
                st.error("Servidor KO. Seguramente has roto algo en el Docker.")
    st.stop()

# --- INTERFAZ PARA USUARIOS QUE SÍ SABEN SU CLAVE ---
user = st.session_state.user_info
st.sidebar.success(f"Usuario: {user['nombre']}")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logged_in = False
    st.rerun()

# Menú lateral: los 'admin' tienen pase VIP
menu = ["Fichar", "Mis Registros"]
if user['rol'] == 'admin':
    menu.append("Administración")
choice = st.sidebar.selectbox("¿Qué quieres hacer?", menu)

# --- SECCIÓN: FICHAR (EL ESPIONAJE GPS) ---
if choice == "Fichar":
    st.title("🚀 Registro de Jornada")
    loc = get_geolocation() 
    
    opciones = {
        "0000 - ENTRADA": "entrada", 
        "0001 - DESCANSO": "descanso", 
        "0005 - COMIDA": "comida", 
        "0007 - SALIDA": "salida"
    }
    seleccion = st.selectbox("Estado actual:", list(opciones.keys()))

    if loc:
        # Extraemos las coordenadas o nos inventamos unas si el GPS es vago
        c = loc.get('coords', loc)
        lat, lon = c.get('latitude', 36.68), c.get('longitude', -6.12)
        if st.button("Confirmar Fichaje"):
            requests.post(f"{API_URL}/fichar/{user['user_id']}?tipo={opciones[seleccion]}&lat={lat}&lon={lon}")
            st.success(f"Registrado: {seleccion}. ¡Venga, a producir!")
    else:
        st.warning("Buscando satélites... o esperando a que des permiso al navegador.")

# --- SECCIÓN: MIS REGISTROS (MATEMÁTICAS PARA ADULTOS) ---
elif choice == "Mis Registros":
    st.title("📊 Tu historial y Horas Extra")
    res = requests.get(f"{API_URL}/fichajes/{user['user_id']}")
    if res.status_code == 200 and res.json():
        df = pd.DataFrame(res.json())
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Calculamos el drama del día de hoy
        hoy = datetime.now().date()
        df_hoy = df[df['timestamp'].dt.date == hoy].sort_values('timestamp')
        
        if len(df_hoy) >= 2:
            h_in = df_hoy[df_hoy['tipo'] == 'entrada']['timestamp'].min()
            h_out = df_hoy[df_hoy['tipo'] == 'salida']['timestamp'].max()
            if h_in and h_out:
                total = (h_out - h_in).total_seconds() / 3600
                # Neto: Restamos la hora de comer. Si sale negativo, ponemos 0 (no debes vida)
                neto = max(0, total - 1) 
                extra = max(0, neto - 8)
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Horas Totales", f"{total:.2f}h")
                c2.metric("Trabajo Neto", f"{neto:.2f}h")
                c3.metric("Extras 🔥", f"{extra:.2f}h")

        st.dataframe(df[['tipo', 'timestamp', 'latitud', 'longitud']])
        
        # Mapa para ver si has fichado desde la oficina o desde el bar
        m_data = df[['latitud', 'longitud']].rename(columns={'latitud':'lat', 'longitud':'lon'}).dropna()
        st.map(m_data)

# --- SECCIÓN: ADMINISTRACIÓN (EL OJO DE SAURON) ---
elif choice == "Administración":
    st.title("🛡️ Panel de Control")
    t1, t2 = st.tabs(["🕵️ Monitor de Tropa", "🆕 Alta de Esclavos"])
    
    with t1:
        st.subheader("Estado actual de la plantilla")
        r = requests.get(f"{API_URL}/estado_usuarios/")
        if r.status_code == 200:
            for emp in r.json():
                col_n, col_e, col_h = st.columns([2, 1, 1])
                col_n.write(f"**{emp['nombre']}**")
                
                status = emp['ultimo_evento']
                if status == "entrada":
                    col_e.success("🟢 Trabajando")
                elif status in ["comida", "descanso"]:
                    col_e.warning("🟡 Esquequeado")
                elif status == "salida":
                    col_e.error("🔴 Fuera")
                else:
                    col_e.info("⚪ Sin noticias")
                
                col_h.write(f"🕒 {emp['hora']}")
                st.divider()

    with t2:
        st.subheader("Registrar nuevo usuario")
        with st.form("nuevo_u"):
            n = st.text_input("Nombre completo")
            e = st.text_input("Email corporativo")
            p = st.text_input("Contraseña temporal")
            r_rol = st.selectbox("Rol", ["user", "admin"])
            if st.form_submit_button("Crear"):
                requests.post(f"{API_URL}/usuarios/?nombre={n}&email={e}&password={p}&rol={r_rol}")
                st.success(f"Usuario {n} creado. Ya puede empezar a sufrir.")
