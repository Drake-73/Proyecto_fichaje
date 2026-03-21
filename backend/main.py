from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Date, cast, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime, date, time as dt_time
import os
import time
from sqlalchemy.exc import OperationalError, IntegrityError
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Crea la carpeta si no existe (por si las moscas)
if not os.path.exists("uploads"):
    os.makedirs("uploads")

# MONTAR LA CARPETA PARA QUE SEA ACCESIBLE POR URL
app.mount("/descargas", StaticFiles(directory="uploads"), name="descargas")

# La URL de la base de datos. Si has tocado el compose y no coinciden, llorarás.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin_fichaje:password_muy_segura@db:5432/gestion_fichajes")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- NUEVOS MODELOS (Añadir junto a Usuario y Fichaje) ---
class Documento(Base):
    __tablename__ = "documentos"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    titulo = Column(String)
    url_destino = Column(String)
    leido = Column(Boolean, default=False)
    fecha_envio = Column(DateTime, default=datetime.now)

class Preaviso(Base):
    __tablename__ = "preavisos"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    tipo = Column(String)
    fecha_ausencia = Column(Date)
    motivo = Column(String)
    visto_admin = Column(Boolean, default=False)
    estado = Column(String, default="pendiente")

# Definimos al "rebaño" (los usuarios)
class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    email = Column(String, unique=True)
    password_hash = Column(String)
    rol = Column(String, default="user") # 'admin' para los elegidos, 'user' para el resto

# Donde anotamos quién ha movido un dedo y dónde estaba (GPS)
class Fichaje(Base):
    __tablename__ = "fichajes"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    tipo = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    latitud = Column(Float)
    longitud = Column(Float)

# --- Modelos Pydantic para evitar parámetros de URL (Query) ---
class LoginData(BaseModel):
    email: str
    password: str

class FichajeData(BaseModel):
    tipo: str
    lat: float
    lon: float

class UsuarioData(BaseModel):
    nombre: str
    email: str
    password: str
    rol: str = "user"

class DocumentoData(BaseModel):
    usuario_id: int
    titulo: str
    url: str

class PreavisoData(BaseModel):
    usuario_id: int
    tipo: str
    fecha: date
    motivo: str

class DecisionData(BaseModel):
    estado: str

class Alerta(Base):
    __tablename__ = "alertas"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    motivo = Column(String)
    fecha = Column(Date, default=date.today)

# Intentamos despertar a la base de datos. Es lenta, como un lunes por la mañana.
for i in range(5):
    try:
        Base.metadata.create_all(bind=engine)
        # Creamos un usuario Administrador inicial para evitar bloqueo del sistema
        db = SessionLocal()
        if not db.query(Usuario).first():
            admin = Usuario(nombre="Admin Dios", email="admin@fichaje.local", password_hash="admin123", rol="admin")
            db.add(admin)
            db.commit()
        db.close()
        break
    except OperationalError:
        time.sleep(5)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# Comprobamos si el usuario sabe escribir su propia clave
@app.post("/login")
def login(data: LoginData, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not user or user.password_hash != data.password:
        raise HTTPException(status_code=401, detail="Credenciales de chiste. Prueba otra vez.")
    return {"user_id": user.id, "nombre": user.nombre, "rol": user.rol}

# Guardamos el fichaje. El Gran Hermano te vigila.
@app.post("/fichar/{user_id}")
def fichar(user_id: int, data: FichajeData, db: Session = Depends(get_db)):
    nuevo = Fichaje(usuario_id=user_id, tipo=data.tipo, latitud=data.lat, longitud=data.lon)
    db.add(nuevo)
    db.commit()
    return {"status": "Fichado. Vuelve al tajo."}

@app.get("/fichajes/{user_id}")
def ver_fichajes(user_id: int, db: Session = Depends(get_db)):
    return db.query(Fichaje).filter(Fichaje.usuario_id == user_id).all()

@app.get("/usuarios/")
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(Usuario).all()

@app.post("/usuarios/")
def crear_usuario(data: UsuarioData, db: Session = Depends(get_db)):
    try:
        nuevo = Usuario(nombre=data.nombre, email=data.email, password_hash=data.password, rol=data.rol)
        db.add(nuevo)
        db.commit()
        return {"status": "Súbdito creado con éxito."}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="El email ya está registrado.")

@app.get("/estado_usuarios/")
def estado_usuarios(db: Session = Depends(get_db)):
    usuarios = db.query(Usuario).all()
    resumen = []
    for u in usuarios:
        ultimo = db.query(Fichaje).filter(Fichaje.usuario_id == u.id).order_by(Fichaje.timestamp.desc()).first()
        resumen.append({
            "nombre": u.nombre,
            "email": u.email,
            "ultimo_evento": ultimo.tipo if ultimo else "SIN ACTIVIDAD",
            "hora": ultimo.timestamp.strftime("%H:%M:%S") if ultimo else "--:--:--"
        })
    return resumen

@app.get("/alertas_fichaje/")
def obtener_alertas(db: Session = Depends(get_db)):
    hoy = date.today()
    usuarios = db.query(Usuario).all()
    # No devolvemos solo una lista, ahora grabamos
    
    HORA_ENTRADA_MAX = dt_time(8, 0)
    HORA_SALIDA_MIN = dt_time(17, 0)

    for u in usuarios:
        fichajes_hoy = db.query(Fichaje).filter(
            Fichaje.usuario_id == u.id,
            cast(Fichaje.timestamp, Date) == hoy
        ).order_by(Fichaje.timestamp.asc()).all()

        # Si no ha venido y es laboral
        if not fichajes_hoy and hoy.weekday() < 5:
            motivo = "Falta injustificada (No ha venido)"
            # Evitamos duplicar alertas para el mismo día
            existe = db.query(Alerta).filter(Alerta.usuario_id == u.id, Alerta.fecha == hoy, Alerta.motivo == motivo).first()
            if not existe:
                db.add(Alerta(usuario_id=u.id, motivo=motivo, fecha=hoy))
            continue

        if fichajes_hoy:
            # 1. Entrada tarde
            if fichajes_hoy[0].tipo == "entrada" and fichajes_hoy[0].timestamp.time() > HORA_ENTRADA_MAX:
                m = f"Llegada tarde: {fichajes_hoy[0].timestamp.strftime('%H:%M')}"
                if not db.query(Alerta).filter(Alerta.usuario_id == u.id, Alerta.fecha == hoy, Alerta.motivo == m).first():
                    db.add(Alerta(usuario_id=u.id, motivo=m, fecha=hoy))

            # 2. Salida antes
            ultimo = fichajes_hoy[-1]
            if ultimo.tipo == "salida" and ultimo.timestamp.time() < HORA_SALIDA_MIN:
                m = f"Salida anticipada: {ultimo.timestamp.strftime('%H:%M')}"
                if not db.query(Alerta).filter(Alerta.usuario_id == u.id, Alerta.fecha == hoy, Alerta.motivo == m).first():
                    db.add(Alerta(usuario_id=u.id, motivo=m, fecha=hoy))

    db.commit()
    # Ahora devolvemos todas las alertas guardadas para hoy
    return db.query(Alerta).filter(Alerta.fecha == hoy).all()

@app.get("/historial_alertas/{usuario_id}")
def historial_alertas(usuario_id: int, db: Session = Depends(get_db)):
    return db.query(Alerta).filter(Alerta.usuario_id == usuario_id).order_by(Alerta.fecha.desc()).all()

# --- NUEVOS ENDPOINTS (Añadir al final del archivo) ---
@app.post("/documentos/")
def enviar_doc(doc: DocumentoData, db: Session = Depends(get_db)):
    nuevo = Documento(usuario_id=doc.usuario_id, titulo=doc.titulo, url_destino=doc.url)
    db.add(nuevo); db.commit(); return {"status": "ok"}

@app.get("/leer_documento/{doc_id}")
def leer_documento(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Documento).filter(Documento.id == doc_id).first()
    if doc:
        # 1. Marcamos como leído
        doc.leido = True
        db.commit()
        
        # 2. REDIRIGIMOS AL ARCHIVO REAL
        # El doc.url_destino debería ser solo el nombre del archivo (ej: "nomina.pdf")
        nombre_archivo = doc.url_destino.split("/")[-1] 
        return RedirectResponse(url=f"/descargas/{nombre_archivo}")
    
    return {"error": "Documento no encontrado"}

@app.get("/mis_documentos/{uid}")
def mis_docs(uid: int, db: Session = Depends(get_db)):
    return db.query(Documento).filter(Documento.usuario_id == uid).all()

@app.post("/preavisos/")
def crear_preaviso(p: PreavisoData, db: Session = Depends(get_db)):
    nuevo = Preaviso(usuario_id=p.usuario_id, tipo=p.tipo, fecha_ausencia=p.fecha, motivo=p.motivo)
    db.add(nuevo); db.commit(); return {"status": "ok"}

@app.get("/admin/documentos/")
def admin_docs(db: Session = Depends(get_db)):
    # Hacemos la consulta uniendo Documento y Usuario
    resultados = db.query(Documento, Usuario.nombre).join(Usuario, Documento.usuario_id == Usuario.id).all()
    
    # Formateamos manualmente para que sea un JSON válido
    return [
        {
            "id": d.id,
            "titulo": d.titulo,
            "leido": d.leido,
            "usuario_nombre": nombre,
            "fecha_envio": d.fecha_envio.strftime("%Y-%m-%d %H:%M:%S")
        } 
        for d, nombre in resultados
    ]

@app.get("/admin/preavisos/")
def admin_preavisos(db: Session = Depends(get_db)):
    resultados = db.query(Preaviso, Usuario.nombre).join(Usuario).all()
    return [
        {
            "id": p.id,
            "usuario_nombre": nombre,
            "tipo": p.tipo,
            "fecha": p.fecha_ausencia.isoformat() if p.fecha_ausencia else None,
            "motivo": p.motivo,
            "visto_admin": p.visto_admin,
            "estado": p.estado
        }
        for p, nombre in resultados
    ]

import shutil
from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/subir_documento/")
async def subir_doc(usuario_id: int = Form(...), titulo: str = Form(...), archivo: UploadFile = File(...), db: Session = Depends(get_db)):
    # Creamos la ruta y guardamos el archivo físico
    file_path = os.path.join(UPLOAD_DIR, archivo.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)
    
    # Guardamos en la DB la ruta local en lugar de una URL externa
    nuevo_doc = Documento(
        usuario_id=usuario_id, 
        titulo=titulo, 
        url_destino=f"/descargar/{archivo.filename}" 
    )
    db.add(nuevo_doc)
    db.commit()
    return {"status": "Archivo a buen recaudo"}

@app.get("/descargar/{nombre_archivo}")
def descargar_archivo(nombre_archivo: str):
    file_path = os.path.join(UPLOAD_DIR, nombre_archivo)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="El archivo no existe o fue destruido")

@app.post("/admin/decidir_preaviso/{preaviso_id}")
def decidir_preaviso(preaviso_id: int, decision: dict, db: Session = Depends(get_db)):
    p = db.query(Preaviso).filter(Preaviso.id == preaviso_id).first()
    if p:
        # Aquí guardamos lo que venga: 'aceptado' o 'rechazado'
        p.estado = decision.get('estado') 
        p.visto_admin = True
        db.commit()
        return {"status": f"Sentencia: {p.estado}"}
    return {"error": "Preaviso no encontrado"}