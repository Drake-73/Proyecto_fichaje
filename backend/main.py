# Importamos un montón de cosas que con suerte sabemos para qué sirven.
from fastapi import FastAPI, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Date, cast, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime, date, time as dt_time, timedelta
import os
import time
import ssl
import io
from ftplib import FTP
from sqlalchemy.exc import OperationalError, IntegrityError
from passlib.context import CryptContext
import random

# Creamos la aplicación. El nombre es lo de menos, lo importante es que funcione (a veces).
app = FastAPI()

# Para las contraseñas, que no se diga que las guardamos en texto plano. Eso sería de novatos.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Una función para convertir una contraseña en un galimatías ilegible. Mágico.
def get_password_hash(password):
    return pwd_context.hash(password)

# Y otra para ver si el galimatías coincide con la contraseña original. Más magia.
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# La URL de la base de datos. Si no está en las variables de entorno, usamos una de juguete.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin_fichaje:password_muy_segura@db:5432/gestion_fichajes")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# A continuación, definimos cómo se ven nuestros datos. Como si fueran cromos de una colección.
class Usuario(Base):
    # El usuario, la pieza clave. Sin él, no hay negocio.
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    email = Column(String, unique=True)
    password_hash = Column(String)
    rol = Column(String, default="user")

class Fichaje(Base):
    # El fichaje, la prueba del delito. Aquí se registra todo.
    __tablename__ = "fichajes"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    tipo = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    latitud = Column(Float)
    longitud = Column(Float)

class Documento(Base):
    # Documentos que el admin envía y que el usuario supuestamente lee.
    __tablename__ = "documentos"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    titulo = Column(String)
    url_destino = Column(String)
    leido = Column(Boolean, default=False)
    fecha_envio = Column(DateTime, default=datetime.now)

class Preaviso(Base):
    # Las excusas del usuario para ausentarse, debidamente registradas.
    __tablename__ = "preavisos"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    tipo = Column(String)
    fecha_ausencia = Column(Date)
    motivo = Column(String)
    visto_admin = Column(Boolean, default=False)
    estado = Column(String, default="pendiente")
    visto_usuario = Column(Boolean, default=False)

class Alerta(Base):
    # Las alertas, porque siempre hay alguien que no cumple.
    __tablename__ = "alertas"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    motivo = Column(String)
    fecha = Column(Date, default=date.today)

class LoginData(BaseModel): email: str; password: str
# Pydantic, para asegurarnos de que los datos que nos llegan tienen la forma que queremos. O eso intentamos.
class FichajeData(BaseModel): tipo: str; lat: float; lon: float
class UsuarioData(BaseModel): nombre: str; email: str; password: str; rol: str = "user"
class PreavisoData(BaseModel): usuario_id: int; tipo: str; fecha: date; motivo: str
class DecisionData(BaseModel): estado: str

for i in range(5):
    # Intentamos crear las tablas y el superusuario. Si la base de datos no está lista, esperamos y lo intentamos de nuevo. Paciencia, joven padawan.
    try:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        if not db.query(Usuario).filter(Usuario.email == "admin@asir.com").first():
            admin_pass = get_password_hash("1234")
            db.add(Usuario(nombre="ASIR Admin", email="admin@asir.com", password_hash=admin_pass, rol="admin"))
            db.commit()

        # --- INICIO DE LA CREACIÓN DE DATOS DE PRUEBA ---
        # Porque una base de datos vacía es como un jardín sin malas hierbas, demasiado perfecto para ser real.
        if not db.query(Usuario).filter(Usuario.email == "juan.perez@asir.com").first():
            print("Creando datos de prueba, porque alguien tiene que hacer el trabajo sucio...")
            
            # Antes de crear a los buenos, limpiemos la basura que pudimos haber creado antes.
            # Adiós, @empresa.com, nadie os echará de menos.
            print("Buscando y eliminando usuarios obsoletos de @empresa.com...")
            usuarios_obsoletos = db.query(Usuario).filter(Usuario.email.like('%@empresa.com')).all()
            if usuarios_obsoletos:
                for u in usuarios_obsoletos:
                    # Hay que borrar todo lo relacionado con el usuario, no solo el usuario.
                    # O podríamos tener una base de datos llena de fantasmas con relaciones rotas.
                    db.query(Fichaje).filter(Fichaje.usuario_id == u.id).delete()
                    db.query(Documento).filter(Documento.usuario_id == u.id).delete()
                    db.query(Preaviso).filter(Preaviso.usuario_id == u.id).delete()
                    db.query(Alerta).filter(Alerta.usuario_id == u.id).delete()
                    db.delete(u)
                db.commit()
                print(f"{len(usuarios_obsoletos)} usuarios de @empresa.com eliminados. No se volverá a hablar de ellos.")
            else:
                print("No se encontraron usuarios de @empresa.com. Todo en orden.")
            
            usuarios_prueba = [
                {"nombre": "Juan Pérez", "email": "juan.perez@asir.com"},
                {"nombre": "María García", "email": "maria.garcia@asir.com"},
                {"nombre": "Carlos Sánchez", "email": "carlos.sanchez@asir.com"},
                {"nombre": "Laura Rodríguez", "email": "laura.rodriguez@asir.com"},
            ]
            
            password_hash = get_password_hash("1234")
            hoy = date.today()
            jerez_lat, jerez_lon = 36.68, -6.12

            for user_data in usuarios_prueba:
                # Dando de alta a los nuevos reclutas
                nuevo_usuario = Usuario(nombre=user_data["nombre"], email=user_data["email"], password_hash=password_hash, rol="user")
                db.add(nuevo_usuario)
                db.flush()

                # Ahora, a fabricarles un pasado laboral de 30 días.
                for i in range(30):
                    dia_actual = hoy - timedelta(days=i)
                    
                    if dia_actual.weekday() >= 5: continue

                    if random.random() < 0.05:
                        db.add(Alerta(usuario_id=nuevo_usuario.id, motivo="Falta injustificada", fecha=dia_actual))
                        if random.random() < 0.5:
                            db.add(Preaviso(usuario_id=nuevo_usuario.id, tipo="Falta", fecha_ausencia=dia_actual, motivo="Asuntos personales (la excusa universal)", estado=random.choice(["aceptado", "rechazado"])))
                        continue

                    hora_entrada = datetime.combine(dia_actual, dt_time(9, 0)) + timedelta(minutes=random.randint(-15, 30))
                    db.add(Fichaje(usuario_id=nuevo_usuario.id, tipo="entrada", timestamp=hora_entrada, latitud=jerez_lat + random.uniform(-0.01, 0.01), longitud=jerez_lon + random.uniform(-0.01, 0.01)))
                    
                    if hora_entrada.minute > 15 and hora_entrada.hour == 9:
                         db.add(Alerta(usuario_id=nuevo_usuario.id, motivo="Retraso", fecha=dia_actual))
                         if random.random() < 0.3:
                            db.add(Preaviso(usuario_id=nuevo_usuario.id, tipo="Retraso", fecha_ausencia=dia_actual, motivo="Atasco, el perro se comió los deberes, etc.", estado="pendiente"))

                    hora_salida = datetime.combine(dia_actual, dt_time(18, 0)) + timedelta(minutes=random.randint(-30, 30))
                    db.add(Fichaje(usuario_id=nuevo_usuario.id, tipo="salida", timestamp=hora_salida, latitud=jerez_lat + random.uniform(-0.01, 0.01), longitud=jerez_lon + random.uniform(-0.01, 0.01)))

                    if random.random() < 0.7:
                        hora_descanso_ini = datetime.combine(dia_actual, dt_time(11, 0)) + timedelta(minutes=random.randint(0, 30))
                        hora_descanso_fin = hora_descanso_ini + timedelta(minutes=random.randint(15, 25))
                        db.add(Fichaje(usuario_id=nuevo_usuario.id, tipo="descanso", timestamp=hora_descanso_ini, latitud=jerez_lat, longitud=jerez_lon))
                        db.add(Fichaje(usuario_id=nuevo_usuario.id, tipo="entrada", timestamp=hora_descanso_fin, latitud=jerez_lat, longitud=jerez_lon))
                    
                    hora_comida_ini = datetime.combine(dia_actual, dt_time(14, 0)) + timedelta(minutes=random.randint(-15, 15))
                    hora_comida_fin = hora_comida_ini + timedelta(hours=1, minutes=random.randint(-5, 15))
                    db.add(Fichaje(usuario_id=nuevo_usuario.id, tipo="comida", timestamp=hora_comida_ini, latitud=jerez_lat, longitud=jerez_lon))
                    db.add(Fichaje(usuario_id=nuevo_usuario.id, tipo="entrada", timestamp=hora_comida_fin, latitud=jerez_lat, longitud=jerez_lon))

            # --- AÑADIR PREAVISOS PENDIENTES PARA PRUEBAS ---
            # Ahora, vamos a generar unas cuantas súplicas pendientes para que el admin tenga algo que hacer.
            print("Generando solicitudes de preaviso pendientes para la bandeja del admin...")
            usuarios_creados = db.query(Usuario).filter(Usuario.email.in_([u['email'] for u in usuarios_prueba])).all()
            if len(usuarios_creados) >= 3:
                # Un clásico: la cita médica.
                db.add(Preaviso(usuario_id=usuarios_creados[0].id, tipo="Retraso", fecha_ausencia=date.today() + timedelta(days=2), motivo="Cita médica a primera hora. Llegaré en cuanto pueda.", estado="pendiente"))
                # El día de asuntos propios, un derecho casi divino.
                db.add(Preaviso(usuario_id=usuarios_creados[1].id, tipo="Falta", fecha_ausencia=date.today() + timedelta(days=10), motivo="Día de asuntos propios. No es negociable.", estado="pendiente"))
                # Y la excusa vaga que podría ser cualquier cosa.
                db.add(Preaviso(usuario_id=usuarios_creados[2].id, tipo="Falta", fecha_ausencia=date.today() + timedelta(days=5), motivo="Gestiones personales que no puedo posponer.", estado="pendiente"))

            db.commit()
            print("Datos de prueba creados. La simulación de una oficina real ha comenzado.")
        # --- FIN DE LA CREACIÓN DE DATOS DE PRUEBA ---

        db.close()
        break
    except OperationalError: time.sleep(5)

# Una función para obtener una sesión de la base de datos. Y para cerrarla después, que no se nos olvide.
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@app.post("/login")
# El endpoint de login. Si las credenciales son correctas, te dejamos pasar. Si no, pues no.
def login(data: LoginData, db: Session = Depends(get_db)):
    u = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not u or not verify_password(data.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"user_id": u.id, "nombre": u.nombre, "rol": u.rol}

@app.post("/usuarios/")
# Para crear nuevos usuarios. Con su nombre, email y contraseña. Y un rol, para que sepan cuál es su lugar.
def crear_usuario(data: UsuarioData, db: Session = Depends(get_db)):
    try:
        # Hasheamos la contraseña, no vaya a ser que alguien la vea.
        hashed_pw = get_password_hash(data.password)
        db.add(Usuario(nombre=data.nombre, email=data.email, password_hash=hashed_pw, rol=data.rol))
        db.commit()
        return {"status": "ok"}
    except IntegrityError: raise HTTPException(status_code=400, detail="Email ya existe")

@app.post("/fichar/{user_id}")
# El endpoint para fichar. Guardamos el tipo de fichaje, la hora y la ubicación. El Gran Hermano te vigila.
def fichar(user_id: int, data: FichajeData, db: Session = Depends(get_db)):
    db.add(Fichaje(usuario_id=user_id, tipo=data.tipo, latitud=data.lat, longitud=data.lon))
    db.commit(); return {"status": "ok"}

@app.get("/fichajes/{user_id}")
# Para ver el historial de fichajes de un usuario. Porque el pasado siempre vuelve.
def ver_fichajes(user_id: int, db: Session = Depends(get_db)):
    return db.query(Fichaje).filter(Fichaje.usuario_id == user_id).all()

@app.get("/usuarios/")
# Una lista de todos los usuarios. Para que el admin pueda controlar a su rebaño.
def listar_usuarios(db: Session = Depends(get_db)): return db.query(Usuario).all()

@app.get("/estado_usuarios/")
# El estado actual de todos los usuarios. ¿Quién está trabajando y quién está de descanso? El chismoso definitivo.
def estado_usuarios(db: Session = Depends(get_db)):
    usuarios = db.query(Usuario).all()
    res = []
    for u in usuarios:
        # Buscamos el último fichaje de cada uno. Una consulta por usuario, porque la eficiencia es para los débiles.
        ult = db.query(Fichaje).filter(Fichaje.usuario_id == u.id).order_by(Fichaje.timestamp.desc()).first()
        res.append({"nombre": u.nombre, "email": u.email, "ultimo_evento": ult.tipo if ult else "NADA", "hora": ult.timestamp.strftime("%H:%M") if ult else "--:--"})
    return res

@app.get("/alertas_fichaje/")
# Generamos alertas para los que no han fichado hoy. Porque la impuntualidad es un pecado capital.
def obtener_alertas(db: Session = Depends(get_db)):
    hoy = date.today(); users = db.query(Usuario).all()
    for u in users:
        # Comprobamos si el usuario ha fichado hoy.
        f = db.query(Fichaje).filter(Fichaje.usuario_id == u.id, cast(Fichaje.timestamp, Date) == hoy).all()
        if not f and hoy.weekday() < 5:
            # Si no ha fichado y es un día laborable, le ponemos una falta.
            if not db.query(Alerta).filter(Alerta.usuario_id == u.id, Alerta.fecha == hoy).first():
                db.add(Alerta(usuario_id=u.id, motivo="Falta", fecha=hoy))
    db.commit(); return db.query(Alerta).filter(Alerta.fecha == hoy).all()

@app.get("/historial_alertas/{uid}")
# El historial de alertas de un usuario. Para que no se le olvide ninguna de sus fechorías.
def historial(uid: int, db: Session = Depends(get_db)):
    return db.query(Alerta).filter(Alerta.usuario_id == uid).order_by(Alerta.fecha.desc()).all()

@app.post("/subir_documento/")
async def subir(usuario_id: int = Form(...), titulo: str = Form(...), archivo: UploadFile = File(...), db: Session = Depends(get_db)):
    name = f"{usuario_id}_{archivo.filename}"
    try:
        # Subimos el archivo a un servidor FTP. Porque es 2024 y el FTP sigue siendo una buena idea, ¿verdad?
        ftp = FTP('asir_ftps')
        ftp.login('amado', 'jerez2026')
        ftp.storbinary(f"STOR {name}", archivo.file)
        ftp.quit()
        db.add(Documento(usuario_id=usuario_id, titulo=titulo, url_destino=name))
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}
    
@app.get("/leer_documento/{doc_id}")
def leer(doc_id: int, db: Session = Depends(get_db)):
    d = db.query(Documento).filter(Documento.id == doc_id).first()
    # Marcamos el documento como leído. Aunque solo lo haya descargado. La intención es lo que cuenta.
    if not d: raise HTTPException(status_code=404)
    d.leido = True
    db.commit()
    try:
        ftp = FTP('asir_ftps')
        # Descargamos el archivo del FTP y se lo enviamos al usuario.
        ftp.login('amado', 'jerez2026')
        buf = io.BytesIO()
        ftp.retrbinary(f"RETR {d.url_destino}", buf.write)
        ftp.quit()
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename={d.url_destino}"})
    except Exception as e: return {"error": str(e)}
    
@app.get("/mis_documentos/{uid}")
def mis_docs(uid: int, db: Session = Depends(get_db)):
    # El usuario quiere ver los documentos que le han enviado. Qué curioso.
    return db.query(Documento).filter(Documento.usuario_id == uid).all()

@app.get("/mis_preavisos/{user_id}")
def mis_preavisos(user_id: int, db: Session = Depends(get_db)):
    # Devuelve los preavisos de un usuario para que sepa si le han aceptado las vacaciones o no.
    return db.query(Preaviso).filter(Preaviso.usuario_id == user_id).order_by(Preaviso.fecha_ausencia.desc()).all()

@app.post("/marcar_preaviso_visto/{preaviso_id}")
def marcar_visto(preaviso_id: int, db: Session = Depends(get_db)):
    # Para que el usuario pueda decir "vale, ya me he enterado", y no le volvamos a molestar.
    p = db.query(Preaviso).filter(Preaviso.id == preaviso_id).first()
    if p:
        p.visto_usuario = True
        db.commit()
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Preaviso no encontrado")

@app.get("/admin/documentos/")
def admin_docs(db: Session = Depends(get_db)):
    # El admin quiere ver quién ha leído qué. El chivato definitivo.
    res = db.query(Documento, Usuario.nombre).join(Usuario).all()
    return [{"id": d.id, "titulo": d.titulo, "leido": d.leido, "usuario_nombre": n} for d, n in res]

@app.post("/preavisos/")
def preaviso(p: PreavisoData, db: Session = Depends(get_db)):
    # El usuario envía un preaviso. A ver qué excusa nos pone esta vez.
    db.add(Preaviso(usuario_id=p.usuario_id, tipo=p.tipo, fecha_ausencia=p.fecha, motivo=p.motivo))
    db.commit(); return {"status": "ok"}

@app.get("/admin/preavisos/")
def admin_preavisos(db: Session = Depends(get_db)):
    # El admin revisa los preavisos. El poder de aceptar o rechazar. Qué subidón.
    res = db.query(Preaviso, Usuario.nombre).join(Usuario).all()
    return [{"id": p.id, "usuario_nombre": n, "tipo": p.tipo, "fecha_ausencia": p.fecha_ausencia.isoformat(), "motivo": p.motivo, "estado": p.estado} for p, n in res]

@app.post("/admin/decidir_preaviso/{pid}")
def decidir(pid: int, d: DecisionData, db: Session = Depends(get_db)):
    # El admin toma una decisión sobre el preaviso. El destino del usuario está en sus manos.
    p = db.query(Preaviso).filter(Preaviso.id == pid).first()
    if p: p.estado = d.estado; p.visto_admin = True; db.commit(); return {"status": "ok"}
    raise HTTPException(status_code=404)