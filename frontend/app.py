import streamlit as st
import requests
import os
import pandas as pd
from streamlit_js_eval import get_geolocation
from datetime import datetime

st.set_page_config(page_title="ASIR GPS Control", page_icon="🕒", layout="wide")

API_URL = os.getenv("API_URL", "http://backend:8000")
URL_PUBLICA = "http://localhost:8000" 

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = {}
if "seccion" not in st.session_state:
    st.session_state.seccion = "Fichar"

if not st.session_state.logged_in:
    st.title("🔐 Identifícate")
    with st.form("login"):
        e = st.text_input("Email")
        p = st.text_input("Clave", type="password")
        if st.form_submit_button("Entrar"):
            res = requests.post(f"{API_URL}/login", json={"email": e, "password": p})
            if res.status_code == 200:
                st.session_state.logged_in = True
                st.session_state.user_info = res.json(); st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

user = st.session_state.user_info
st.sidebar.success(f"Usuario: {user['nombre']}")

if st.sidebar.button("🚀 Fichar", use_container_width=True): st.session_state.seccion = "Fichar"
if st.sidebar.button("📊 Registros", use_container_width=True): st.session_state.seccion = "Registros"
if user['rol'] == 'admin':
    if st.sidebar.button("🛡️ Administración", use_container_width=True): st.session_state.seccion = "Administración"

if st.sidebar.button("🏃‍♂️ Salir", use_container_width=True):
    st.session_state.logged_in = False; st.rerun()

choice = st.session_state.seccion

if choice == "Fichar":
    st.title("🚀 Fichar")
    res_d = requests.get(f"{API_URL}/mis_documentos/{user['user_id']}")
    if res_d.status_code == 200 and res_d.json():
        for d in res_d.json():
            st.markdown(f"{'✅' if d['leido'] else '🆕'} [{d['titulo']}]({URL_PUBLICA}/leer_documento/{d['id']})")
    
    loc = get_geolocation()
    opts = {"ENTRADA": "entrada", "DESCANSO": "descanso", "COMIDA": "comida", "SALIDA": "salida"}
    sel = st.selectbox("Estado:", list(opts.keys()))
    if st.button("Confirmar", use_container_width=True):
        lat, lon = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (36.68, -6.12)
        res_fichar = requests.post(f"{API_URL}/fichar/{user['user_id']}", json={"tipo": opts[sel], "lat": lat, "lon": lon})
        if res_fichar.status_code == 200:
            st.success("Fichaje registrado correctamente.")
        else:
            st.error("No se pudo registrar el fichaje.")

    st.subheader("📝 Preaviso")
    with st.form("prev", clear_on_submit=True):
        tp = st.selectbox("Tipo", ["Retraso", "Falta"])
        fp = st.date_input("Día")
        mp = st.text_area("Motivo")
        if st.form_submit_button("Enviar"):
            res_prev = requests.post(f"{API_URL}/preavisos/", json={"usuario_id": user['user_id'], "tipo": tp, "fecha": str(fp), "motivo": mp})
            if res_prev.status_code == 200:
                st.success("Preaviso enviado correctamente.")
            else:
                st.error("No se pudo enviar el preaviso.")

elif choice == "Registros":
    st.title("📊 Historial")
    r = requests.get(f"{API_URL}/fichajes/{user['user_id']}")
    if r.status_code == 200 and r.json():
        df = pd.DataFrame(r.json())
        
        # Botón para exportar el historial a CSV tal como promete el README
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Descargar historial en CSV", data=csv, file_name="historial_fichajes.csv", mime="text/csv")
        
        st.dataframe(df[['tipo', 'timestamp']], use_container_width=True)
        m_data = df[['latitud', 'longitud']].rename(columns={'latitud':'lat', 'longitud':'lon'}).dropna()
        if not m_data.empty: st.map(m_data)

elif choice == "Administración":
    st.title("🛡️ Panel de Control Superior (El Gran Hermano)")
    
    # Creamos las 4 pestañas con iconos Emojis
    t1, t2, t3, t4 = st.tabs(["🕵️ Monitor", "🆕 Alta", "⚠️ Alertas", "📂 Gestión Doc/Preavisos"])
    
    with t1:
        st.header("🕵️ Monitor de Tropa en Tiempo Real")
        try:
            r_mon = requests.get(f"{API_URL}/estado_usuarios/")
            if r_mon.status_code == 200:
                for emp in r_mon.json():
                    with st.container(border=True):
                        c_n, c_e, c_h = st.columns([2, 1, 1])
                        c_n.write(f"**{emp.get('nombre')}** ({emp.get('email')})")
                        
                        status = emp.get('ultimo_evento')
                        if status == "entrada": c_e.success("🟢 Trabajando")
                        elif status in ["comida", "descanso"]: c_e.warning("🟡 Esquequeado")
                        elif status == "salida": c_e.error("🔴 Fuera")
                        else: c_e.info("⚪ Sin noticias")
                        
                        c_h.write(f"🕒 {emp.get('hora', '--:--')}")
            else:
                st.error("No se puede espiar a la tropa ahora mismo.")
        except:
            st.error("Error de conexión con el monitor.")

    with t2:
        st.header("🆕 Registro de Nuevos Súbditos")
        with st.form("nuevo_u_form", clear_on_submit=True):
            n = st.text_input("Nombre completo")
            e = st.text_input("Email corporativo")
            p = st.text_input("Contraseña provisional", type="password")
            r_rol = st.selectbox("Rol en la empresa", ["user", "admin"])
            if st.form_submit_button("Dar de alta"):
                if n and e and p:
                    res_new = requests.post(f"{API_URL}/usuarios/", json={"nombre": n, "email": e, "password": p, "rol": r_rol})
                    if res_new.status_code == 200:
                        st.success(f"Usuario {n} creado. Que empiece a producir.")
                    else:
                        st.error("Error al crear. ¿Ya existe ese email?")
                else:
                    st.warning("Rellena todos los campos, Amado.")

    with t3:
        st.header("⚠️ Historial de Incidencias de Fichaje")
        if st.button("🔄 Actualizar Alertas del Día"):
            requests.get(f"{API_URL}/alertas_fichaje/")
            st.toast("Alertas refrescadas")
            
        try:
            res_users_alert = requests.get(f"{API_URL}/usuarios/")
            if res_users_alert.status_code == 200:
                u_list = {f"{u['nombre']} ({u['email']})": u['id'] for u in res_users_alert.json()}
                sospechoso = st.selectbox("Seleccionar sospechoso:", [""] + list(u_list.keys()))
                
                if sospechoso:
                    if st.button(f"🔍 Ver historial de {sospechoso.split(' (')[0]}"):
                        uid = u_list[sospechoso]
                        r_hist = requests.get(f"{API_URL}/historial_alertas/{uid}")
                        if r_hist.status_code == 200 and r_hist.json():
                            # Limpiamos el JSON para la tabla
                            df_alertas = pd.DataFrame(r_hist.json())[['fecha', 'motivo']]
                            st.table(df_alertas)
                        else:
                            st.success("Expediente limpio... de momento.")
        except:
            st.error("Error al cargar la sección de alertas.")

    with t4:
        st.header("📂 Gestión de Documentos y Sentencias")
        
        # 1. Envío de archivos (FTPS Túnel)
        try:
            res_u_doc = requests.get(f"{API_URL}/usuarios/")
            if res_u_doc.status_code == 200:
                u_dict_doc = {f"{u['nombre']} ({u['email']})": u['id'] for u in res_u_doc.json()}
                
                with st.expander("📤 Enviar nuevo archivo físico (Nóminas, Sanciones...)"):
                    with st.form("env_arch_form", clear_on_submit=True):
                        v_dest = st.selectbox("Destinatario:", list(u_dict_doc.keys()))
                        v_tit = st.text_input("Título del documento (ej: Nómina Marzo):")
                        v_file = st.file_uploader("Archivo:", type=['pdf', 'docx', 'jpg', 'png'])
                        
                        if st.form_submit_button("Lanzar Archivo"):
                            if v_file and v_tit and v_dest:
                                # Usamos el endpoint de subida real que va al FTPS
                                try:
                                    res_up = requests.post(f"{API_URL}/subir_documento/", 
                                                           data={"usuario_id": u_dict_doc[v_dest], "titulo": v_tit}, 
                                                           files={"archivo": (v_file.name, v_file.getvalue())})
                                    if "error" in res_up.json():
                                        st.error(f"Error FTP: {res_up.json()['error']}")
                                    else:
                                        st.success("Enviado al túnel FTPS cifrado.")
                                except:
                                    st.error("Fallo al conectar con el túnel de subida.")
                            else:
                                st.warning("Faltan datos para el envío.")
        except:
            st.error("No se pueden cargar usuarios para el envío.")

        # 2. Control de lectura
        st.divider()
        st.subheader("📊 Chivatazo de Lectura")
        try:
            r_ctrl = requests.get(f"{API_URL}/admin/documentos/")
            if r_ctrl.status_code == 200 and r_ctrl.json():
                d_list = []
                for d in r_ctrl.json():
                    d_list.append({
                        "Empleado": d.get("usuario_nombre"),
                        "Doc": d.get("titulo"),
                        "Leído": "✅ SÍ" if d.get("leido") else "❌ NO"
                    })
                st.table(d_list)
            else:
                st.info("Nadie ha leído nada aún.")
        except:
            st.write("Cargando chivatazos...")

        # 3. Juez de Preavisos (EL MAZO)
        st.divider()
        st.subheader("📬 Juez de Preavisos (Pendientes de Sentencia)")
        
        try:
            res_p_adm = requests.get(f"{API_URL}/admin/preavisos/")
            if res_p_adm.status_code == 200:
                # Filtramos con seguridad usando .get()
                p_pendientes = [p for p in res_p_adm.json() if p.get('estado', 'pendiente') == 'pendiente']
                
                if p_pendientes:
                    for p in p_pendientes:
                        # Claves únicas para los botones
                        id_p = p.get('id')
                        with st.container(border=True):
                            c_inf, c_btns = st.columns([3, 2])
                            
                            c_inf.write(f"**{p.get('usuario_nombre', 'Desconocido')}** - {p.get('tipo')} ({p.get('fecha')})")
                            c_inf.caption(f"Motivo: {p.get('motivo', 'Sin motivo')}")
                            
                            btn_ok, btn_no = c_btns.columns(2)
                            
                            if btn_ok.button("✅ Aceptar", key=f"ok_{id_p}", use_container_width=True):
                                res_dec = requests.post(f"{API_URL}/admin/decidir_preaviso/{id_p}", json={"estado": "aceptado"})
                                if res_dec.status_code == 200:
                                    st.rerun()
                                
                            if btn_no.button("❌ Rechazar", key=f"no_{id_p}", use_container_width=True, type="primary"):
                                res_dec = requests.post(f"{API_URL}/admin/decidir_preaviso/{id_p}", json={"estado": "rechazado"})
                                if res_dec.status_code == 200:
                                    st.rerun()
                else:
                    st.info("No hay sentencias pendientes. La tropa se porta bien.")
            else:
                st.error("Error al conectar con el buzón de preavisos.")
        except:
            st.error("Cargando mazo de juez...")