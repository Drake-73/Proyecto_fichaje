# Importamos todas las herramientas del taller. Probablemente usemos la mitad, pero es mejor que sobren.
import streamlit as st
import requests
import os
import pandas as pd
from streamlit_js_eval import get_geolocation, streamlit_js_eval
from datetime import datetime, timedelta
import json
# Configuramos la página. Título, icono... lo típico para que parezca profesional.
st.set_page_config(page_title="ASIR GPS Control", page_icon="🕒", layout="wide")

# ¿Dónde está el backend? Buena pregunta. Si no nos lo dicen, asumimos que está en un lugar mágico.
API_URL = os.getenv("API_URL", "http://backend:8000")
# Y la URL para que el usuario haga clic, porque claro, el navegador no sabe qué es 'backend:8000'.
URL_PUBLICA = "http://localhost:8000" 

# El estado de la sesión, nuestro castillo de naipes digital.
if "logged_in" not in st.session_state:
    # Empezamos asumiendo que nadie ha entrado. Seguridad ante todo.
    st.session_state.logged_in = False
    st.session_state.user_info = {}
if "seccion" not in st.session_state:
    # Por defecto, todo el mundo quiere fichar. O eso nos gusta pensar.
    st.session_state.seccion = "Fichar"

# Intentamos recuperar la sesión del localStorage si no estamos logueados en el estado de Streamlit.
# Esto es un apaño para sobrevivir a los F5 (actualizaciones de página).
if not st.session_state.logged_in:
    try:
        # Pedimos al navegador que nos devuelva lo que guardamos en 'user_session'.
        session_str = streamlit_js_eval(js_expressions="localStorage.getItem('user_session')", key='get_session')
        if session_str:
            session_data = json.loads(session_str)
            expiry_time = datetime.fromisoformat(session_data['expiry'])
            
            # Si la sesión no ha caducado, nos volvemos a loguear mágicamente.
            if datetime.now() < expiry_time:
                st.session_state.logged_in = True
                st.session_state.user_info = session_data['user_info']
            else:
                # La sesión ha caducado, la borramos para no volver a intentarlo.
                streamlit_js_eval(js_expressions="localStorage.removeItem('user_session')", key='remove_session_expired')
    except Exception:
        # Si algo explota (que podría), simplemente lo ignoramos y mostramos el login.
        pass

# El gran muro: si no estás en la lista, no pasas.
if not st.session_state.logged_in:
    st.title("🔐 Identifícate")
    with st.form("login"): # Un formulario para que nos den sus credenciales. Confiamos en que sean las suyas.
        e = st.text_input("Email")
        p = st.text_input("Clave", type="password")
        if st.form_submit_button("Entrar"):
            res = requests.post(f"{API_URL}/login", json={"email": e, "password": p})
            if res.status_code == 200:
                st.session_state.logged_in = True
                user_info = res.json()
                st.session_state.user_info = user_info
                
                # Guardamos la sesión en el navegador del cliente con una caducidad de 10 minutos.
                # Es como escribir una nota en la mano del usuario para que no se nos olvide quién es si se va y vuelve rápido.
                expiry_time = datetime.now() + timedelta(minutes=10)
                session_data = {
                    'user_info': user_info,
                    'expiry': expiry_time.isoformat()
                }
                session_str = json.dumps(session_data)
                # Usamos JS para meterle la sesión en el localStorage. Con comillas ` para que no se rompa.
                streamlit_js_eval(js_expressions=f"localStorage.setItem('user_session', `{session_str}`)", key='set_session')
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# Si has llegado hasta aquí, enhorabuena. Te guardamos los datos para no volver a preguntar.
user = st.session_state.user_info
st.sidebar.success(f"Usuario: {user['nombre']}")

# La barra lateral, el menú de opciones para que el usuario se sienta con el control.
if st.sidebar.button("🚀 Fichar", use_container_width=True): st.session_state.seccion = "Fichar"
if st.sidebar.button("📊 Registros", use_container_width=True): st.session_state.seccion = "Registros"
if user['rol'] == 'admin':
    # Un botón secreto solo para los elegidos. El poder corrompe.
    if st.sidebar.button("🛡️ Administración", use_container_width=True): st.session_state.seccion = "Administración"

# La puerta de salida. No la usarán, ¿verdad?
if st.sidebar.button("🏃‍♂️ Salir", use_container_width=True):
    # Si el usuario se va, borramos la nota de su mano (localStorage).
    streamlit_js_eval(js_expressions="localStorage.removeItem('user_session')", key='remove_session_logout')
    # Y también limpiamos el estado de la sesión de Streamlit.
    st.session_state.logged_in = False
    st.session_state.user_info = {}
    st.rerun()

choice = st.session_state.seccion

# Sección de Fichaje: el corazón de esta humilde aplicación.
if choice == "Fichar":
    st.title("🚀 Fichar")
    # Notificaciones para el proletariado, para que sepan si pueden o no irse de puente.
    try:
        res_mis_preavisos = requests.get(f"{API_URL}/mis_preavisos/{user['user_id']}")
        if res_mis_preavisos.status_code == 200:
            todos_mis_preavisos = res_mis_preavisos.json()
            notificaciones = [p for p in todos_mis_preavisos if p.get('estado') != 'pendiente' and not p.get('visto_usuario')]
            if notificaciones:
                with st.expander("🔔 Tienes notificaciones de preavisos", expanded=True):
                    for p in notificaciones:
                        col1, col2 = st.columns([4,1])
                        fecha_formateada = datetime.strptime(p.get('fecha_ausencia'), '%Y-%m-%d').strftime('%d/%m/%Y')
                        msg = f"Tu solicitud de '{p.get('tipo').capitalize()}' para el {fecha_formateada} ha sido **{p.get('estado')}**."
                        if p.get('estado') == 'aceptado':
                            col1.success(msg)
                        else:
                            col1.error(msg)
                        
                        if col2.button("Marcar como leído", key=f"visto_{p.get('id')}"):
                            requests.post(f"{API_URL}/marcar_preaviso_visto/{p.get('id')}")
                            st.rerun()
            
            # Mostramos también las que están pendientes, para que el trabajador sepa que no han caído en el olvido.
            solicitudes_pendientes = [p for p in todos_mis_preavisos if p.get('estado') == 'pendiente']
            if solicitudes_pendientes:
                with st.expander("⏳ Solicitudes pendientes de sentencia"):
                    for p in solicitudes_pendientes:
                        fecha_formateada = datetime.strptime(p.get('fecha_ausencia'), '%Y-%m-%d').strftime('%d/%m/%Y')
                        st.info(f"Tu solicitud de '{p.get('tipo').capitalize()}' para el {fecha_formateada} está pendiente de revisión.")
    except requests.exceptions.RequestException:
        # Si no hay conexión, pues no hay notificaciones. Tampoco es el fin del mundo.
        pass
    # Primero, recordémosle al usuario los documentos que no ha leído. Presión social.
    res_d = requests.get(f"{API_URL}/mis_documentos/{user['user_id']}")
    if res_d.status_code == 200 and res_d.json():
        for d in res_d.json():
            st.markdown(f"{'✅' if d['leido'] else '🆕'} [{d['titulo']}]({URL_PUBLICA}/leer_documento/{d['id']})")
    
    # A ver, ¿dónde estás? Le preguntamos al navegador con la esperanza de que nos diga la verdad.
    loc = get_geolocation()
    if loc and 'coords' in loc:
        lat = loc['coords'].get('latitude', 36.68)
        lon = loc['coords'].get('longitude', -6.12)
    else:
        # Si falla, diremos que está en Jerez. Un lugar tan bueno como cualquier otro.
        lat, lon = 36.68, -6.12

    opts = {"ENTRADA": "entrada", "DESCANSO": "descanso", "COMIDA": "comida", "SALIDA": "salida"}
    sel = st.selectbox("Estado:", list(opts.keys()))
    if st.button("Confirmar", use_container_width=True):
        # El usuario presiona un botón para jurar que está trabajando. Nosotros solo registramos el evento.
        res_fichar = requests.post(f"{API_URL}/fichar/{user['user_id']}", json={"tipo": opts[sel], "lat": lat, "lon": lon})
        if res_fichar.status_code == 200:
            st.success(f"Fichaje registrado en ({lat}, {lon})")
        else:
            st.error("No se pudo registrar el fichaje.")

    st.subheader("📝 Preaviso")
    # Un pequeño formulario para que supliquen clemencia por sus futuras ausencias.
    with st.form("prev", clear_on_submit=True):
        tp = st.selectbox("Tipo", ["Retraso", "Falta"])
        fp = st.date_input("Día")
        mp = st.text_area("Motivo")
        if st.form_submit_button("Enviar"):
            res_prev = requests.post(f"{API_URL}/preavisos/", json={"usuario_id": user['user_id'], "tipo": tp.lower(), "fecha": str(fp), "motivo": mp})
            if res_prev.status_code == 200:
                st.success("Preaviso enviado correctamente.")
            else:
                st.error("No se pudo enviar el preaviso.")

# Sección de Registros: el pasado siempre vuelve.
elif choice == "Registros":
    st.title("📊 Historial")
    r = requests.get(f"{API_URL}/fichajes/{user['user_id']}")
    if r.status_code == 200 and r.json():
        # Convertimos su historial en un bonito DataFrame. Los datos son poder.
        df = pd.DataFrame(r.json())
        # Y por si quieren una copia para sus propios archivos... o para el abogado.
        csv = df.to_csv(index=False).encode('utf-8')
        file_name = f"historial_fichajes_{user['nombre'].replace(' ', '_')}.csv"
        st.download_button(label="📥 Descargar historial en CSV", data=csv, file_name=file_name, mime="text/csv")
        # Hacemos una copia para maquillar la fecha y que parezca legible por humanos, sin estropear el original.
        df_display = df.copy()
        df_display['timestamp'] = pd.to_datetime(df_display['timestamp']).dt.strftime('%d/%m/%Y %H:%M:%S')
        df_display['tipo'] = df_display['tipo'].str.capitalize()
        st.dataframe(df_display[['tipo', 'timestamp']], use_container_width=True)
        # Un mapa para que vean todos los sitios donde han estado... trabajando, claro.
        m_data = df[['latitud', 'longitud']].rename(columns={'latitud':'lat', 'longitud':'lon'}).dropna()
        if not m_data.empty: st.map(m_data)

# La joya de la corona: el panel del Gran Hermano.
elif choice == "Administración":
    st.title("🛡️ Panel de Control Superior (El Gran Hermano)")
    t1, t2, t3, t4 = st.tabs(["🕵️ Monitor", "🆕 Alta", "⚠️ Alertas", "📂 Gestión Doc/Preavisos"])
    
    with t1:
        # Aquí es donde el admin espía a sus súbditos en "tiempo real".
        st.header("🕵️ Monitor de Tropa en Tiempo Real")
        try:
            r_mon = requests.get(f"{API_URL}/estado_usuarios/")
            if r_mon.status_code == 200:
                for emp in r_mon.json():
                    with st.container(border=True):
                        c_n, c_e, c_h = st.columns([2, 1, 1])
                        c_n.write(f"**{emp.get('nombre')}** ({emp.get('email')})")
                        # Clasificamos su estado con un sistema de colores muy científico.
                        status = emp.get('ultimo_evento')
                        if status == "entrada": c_e.success("🟢 Trabajando")
                        elif status in ["comida", "descanso"]: c_e.warning("🟡 Esquequeado")
                        elif status == "salida": c_e.error("🔴 Fuera")
                        else: c_e.info("⚪ Sin noticias")
                        c_h.write(f"🕒 {emp.get('hora', '--:--')}")
        except:
            st.error("Error de conexión con el monitor.")

    with t2:
        # El mercado de nuevos fichajes.
        st.header("🆕 Registro de Nuevos Súbditos")
        with st.form("nuevo_u_form", clear_on_submit=True):
            n = st.text_input("Nombre completo")
            e = st.text_input("Email corporativo")
            p = st.text_input("Contraseña provisional", type="password")
            r_rol = st.selectbox("Rol en la empresa", ["user", "admin"])
            if st.form_submit_button("Dar de alta"):
                if n and e and p:
                    # Enviamos los datos al matadero digital.
                    res_new = requests.post(f"{API_URL}/usuarios/", json={"nombre": n, "email": e, "password": p, "rol": r_rol})
                    if res_new.status_code == 200:
                        st.success(f"Usuario {n} creado.")
                    else:
                        st.error("Error al crear.")

    with t3:
        # El muro de la vergüenza.
        st.header("⚠️ Historial de Incidencias")
        if st.button("🔄 Actualizar Alertas del Día"):
            requests.get(f"{API_URL}/alertas_fichaje/")
            st.toast("Alertas refrescadas")
        try:
            res_users_alert = requests.get(f"{API_URL}/usuarios/")
            # Busquemos un culpable.
            if res_users_alert.status_code == 200:
                u_list = {f"{u['nombre']} ({u['email']})": u['id'] for u in res_users_alert.json()}
                sospechoso = st.selectbox("Seleccionar sospechoso:", [""] + list(u_list.keys()))
                if sospechoso:
                    if st.button(f"🔍 Ver historial"):
                        r_hist = requests.get(f"{API_URL}/historial_alertas/{u_list[sospechoso]}")
                        if r_hist.status_code == 200 and r_hist.json():
                            st.table(pd.DataFrame(r_hist.json())[['fecha', 'motivo']])
        except:
            st.error("Error al cargar alertas.")

    with t4:
        # Burocracia y sentencias. El verdadero trabajo de un admin.
        st.header("📂 Gestión de Documentos y Sentencias")
        try:
            res_u_doc = requests.get(f"{API_URL}/usuarios/")
            if res_u_doc.status_code == 200:
                u_dict_doc = {f"{u['nombre']} ({u['email']})": u['id'] for u in res_u_doc.json()}
                # Un formulario para enviar archivos que probablemente nadie leerá.
                with st.expander("📤 Enviar nuevo archivo"):
                    with st.form("env_arch_form", clear_on_submit=True):
                        v_dest = st.selectbox("Destinatario:", list(u_dict_doc.keys()))
                        v_tit = st.text_input("Título:")
                        v_file = st.file_uploader("Archivo:", type=['pdf', 'docx', 'jpg', 'png'])
                        if st.form_submit_button("Lanzar Archivo"):
                            if v_file and v_tit and v_dest:
                                res_up = requests.post(f"{API_URL}/subir_documento/", 
                                                       data={"usuario_id": u_dict_doc[v_dest], "titulo": v_tit}, 
                                                       files={"archivo": (v_file.name, v_file.getvalue())})
                                if "error" in res_up.json(): st.error(f"Error: {res_up.json()['error']}")
                                else: st.success("Archivo enviado.")
        except:
            st.error("Error en gestión documental.")

        st.divider()
        # El chivato: ¿quién ha leído qué?
        try:
            r_ctrl = requests.get(f"{API_URL}/admin/documentos/")
            if r_ctrl.status_code == 200 and r_ctrl.json():
                st.table([{"Empleado": d.get("usuario_nombre"), "Doc": d.get("titulo"), "Leído": "✅ SÍ" if d.get("leido") else "❌ NO"} for d in r_ctrl.json()])
        except:
            # Si falla, disimulamos.
            st.write("Cargando chivatazos...")

        st.divider()
        # El tribunal de los preavisos. Aquí se decide el destino de los mortales.
        try:
            res_p_adm = requests.get(f"{API_URL}/admin/preavisos/")
            if res_p_adm.status_code == 200:
                todos_los_preavisos = res_p_adm.json()
                p_pendientes = [p for p in todos_los_preavisos if p.get('estado') == 'pendiente']
                p_procesados = [p for p in todos_los_preavisos if p.get('estado') != 'pendiente']

                st.subheader("Solicitudes Pendientes de Sentencia")
                if not p_pendientes:
                    st.info("No hay solicitudes pendientes. Puede ir a por un café.")

                for p in p_pendientes:
                    # Para cada súplica, un par de botones: el pulgar arriba o el pulgar abajo.
                    id_p = p.get('id')
                    with st.container(border=True):
                        c_inf, c_btns = st.columns([3, 2])
                        fecha_formateada = datetime.strptime(p.get('fecha_ausencia'), '%Y-%m-%d').strftime('%d/%m/%Y')
                        c_inf.write(f"**{p.get('usuario_nombre')}** - {p.get('tipo').capitalize()} ({fecha_formateada})")
                        c_inf.caption(f"Motivo: {p.get('motivo')}")
                        c_inf.info("Estado: Pendiente de sentencia")
                        btn_ok, btn_no = c_btns.columns(2)
                        if btn_ok.button("✅ Aceptar", key=f"ok_{id_p}"):
                            try:
                                res = requests.post(f"{API_URL}/admin/decidir_preaviso/{id_p}", json={"estado": "aceptado"})
                                res.raise_for_status()  # Lanza un error si la petición falla (no es 2xx)
                                st.rerun()
                            except requests.exceptions.RequestException as e_post:
                                st.error(f"Error al procesar la solicitud: {e_post}")
                        if btn_no.button("❌ Rechazar", key=f"no_{id_p}", type="primary"):
                            try:
                                res = requests.post(f"{API_URL}/admin/decidir_preaviso/{id_p}", json={"estado": "rechazado"})
                                res.raise_for_status()
                                st.rerun()
                            except requests.exceptions.RequestException as e_post:
                                st.error(f"Error al procesar la solicitud: {e_post}")
                
                st.divider()
                st.subheader("Historial de Solicitudes Procesadas")
                if p_procesados:
                    df_procesados = pd.DataFrame(p_procesados)
                    df_procesados['fecha_ausencia'] = pd.to_datetime(df_procesados['fecha_ausencia']).dt.strftime('%d/%m/%Y')
                    df_procesados['tipo'] = df_procesados['tipo'].str.capitalize()
                    df_procesados['estado'] = df_procesados['estado'].str.capitalize()
                    st.dataframe(df_procesados[['usuario_nombre', 'tipo', 'fecha_ausencia', 'motivo', 'estado']].rename(columns={
                        'usuario_nombre': 'Empleado',
                        'tipo': 'Tipo',
                        'fecha_ausencia': 'Fecha',
                        'motivo': 'Motivo',
                        'estado': 'Veredicto'
                    }), use_container_width=True)
                else:
                    st.info("Aún no se ha procesado ninguna solicitud.")

        except requests.exceptions.RequestException as e:
            st.error(f"Error de conexión en preavisos: {e}")