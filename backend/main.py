from fastapi import FastAPI, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Date, cast, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime, date, time as dt_time
import os
import time
import ssl
import io
from ftplib import FTP
from sqlalchemy.exc import OperationalError, IntegrityError
from passlib.context import CryptContext

app = FastAPI()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin_fichaje:password_muy_segura@db:5432/gestion_fichajes")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    email = Column(String, unique=True)
    password_hash = Column(String)
    rol = Column(String, default="user")

class Fichaje(Base):
    __tablename__ = "fichajes"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    tipo = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    latitud = Column(Float)
    longitud = Column(Float)

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

class Alerta(Base):
    __tablename__ = "alertas"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    motivo = Column(String)
    fecha = Column(Date, default=date.today)

class LoginData(BaseModel): email: str; password: str
class FichajeData(BaseModel): tipo: str; lat: float; lon: float
class UsuarioData(BaseModel): nombre: str; email: str; password: str; rol: str = "user"
class PreavisoData(BaseModel): usuario_id: int; tipo: str; fecha: date; motivo: str
class DecisionData(BaseModel): estado: str

for i in range(5):
    try:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        if not db.query(Usuario).filter(Usuario.email == "admin@asir.com").first():
            admin_pass = get_password_hash("1234")
            db.add(Usuario(nombre="ASIR Admin", email="admin@asir.com", password_hash=admin_pass, rol="admin"))
            db.commit()
        db.close()
        break
    except OperationalError: time.sleep(5)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@app.post("/login")
def login(data: LoginData, db: Session = Depends(get_db)):
    u = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not u or not verify_password(data.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"user_id": u.id, "nombre": u.nombre, "rol": u.rol}

@app.post("/usuarios/")
def crear_usuario(data: UsuarioData, db: Session = Depends(get_db)):
    try:
        hashed_pw = get_password_hash(data.password)
        db.add(Usuario(nombre=data.nombre, email=data.email, password_hash=hashed_pw, rol=data.rol))
        db.commit()
        return {"status": "ok"}
    except IntegrityError: raise HTTPException(status_code=400, detail="Email ya existe")

@app.post("/fichar/{user_id}")
def fichar(user_id: int, data: FichajeData, db: Session = Depends(get_db)):
    db.add(Fichaje(usuario_id=user_id, tipo=data.tipo, latitud=data.lat, longitud=data.lon))
    db.commit(); return {"status": "ok"}

@app.get("/fichajes/{user_id}")
def ver_fichajes(user_id: int, db: Session = Depends(get_db)):
    return db.query(Fichaje).filter(Fichaje.usuario_id == user_id).all()

@app.get("/usuarios/")
def listar_usuarios(db: Session = Depends(get_db)): return db.query(Usuario).all()

@app.get("/estado_usuarios/")
def estado_usuarios(db: Session = Depends(get_db)):
    usuarios = db.query(Usuario).all()
    res = []
    for u in usuarios:
        ult = db.query(Fichaje).filter(Fichaje.usuario_id == u.id).order_by(Fichaje.timestamp.desc()).first()
        res.append({"nombre": u.nombre, "email": u.email, "ultimo_evento": ult.tipo if ult else "NADA", "hora": ult.timestamp.strftime("%H:%M") if ult else "--:--"})
    return res

@app.get("/alertas_fichaje/")
def obtener_alertas(db: Session = Depends(get_db)):
    hoy = date.today(); users = db.query(Usuario).all()
    for u in users:
        f = db.query(Fichaje).filter(Fichaje.usuario_id == u.id, cast(Fichaje.timestamp, Date) == hoy).all()
        if not f and hoy.weekday() < 5:
            if not db.query(Alerta).filter(Alerta.usuario_id == u.id, Alerta.fecha == hoy).first():
                db.add(Alerta(usuario_id=u.id, motivo="Falta", fecha=hoy))
    db.commit(); return db.query(Alerta).filter(Alerta.fecha == hoy).all()

@app.get("/historial_alertas/{uid}")
def historial(uid: int, db: Session = Depends(get_db)):
    return db.query(Alerta).filter(Alerta.usuario_id == uid).order_by(Alerta.fecha.desc()).all()

@app.post("/subir_documento/")
async def subir(usuario_id: int = Form(...), titulo: str = Form(...), archivo: UploadFile = File(...), db: Session = Depends(get_db)):
    name = f"{usuario_id}_{archivo.filename}"
    try:
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
    if not d: raise HTTPException(status_code=404)
    d.leido = True
    db.commit()
    try:
        ftp = FTP('asir_ftps')
        ftp.login('amado', 'jerez2026')
        buf = io.BytesIO()
        ftp.retrbinary(f"RETR {d.url_destino}", buf.write)
        ftp.quit()
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename={d.url_destino}"})
    except Exception as e: return {"error": str(e)}
    
@app.get("/mis_documentos/{uid}")
def mis_docs(uid: int, db: Session = Depends(get_db)):
    return db.query(Documento).filter(Documento.usuario_id == uid).all()

@app.get("/admin/documentos/")
def admin_docs(db: Session = Depends(get_db)):
    res = db.query(Documento, Usuario.nombre).join(Usuario).all()
    return [{"id": d.id, "titulo": d.titulo, "leido": d.leido, "usuario_nombre": n} for d, n in res]

@app.post("/preavisos/")
def preaviso(p: PreavisoData, db: Session = Depends(get_db)):
    db.add(Preaviso(usuario_id=p.usuario_id, tipo=p.tipo, fecha_ausencia=p.fecha, motivo=p.motivo))
    db.commit(); return {"status": "ok"}

@app.get("/admin/preavisos/")
def admin_preavisos(db: Session = Depends(get_db)):
    res = db.query(Preaviso, Usuario.nombre).join(Usuario).all()
    return [{"id": p.id, "usuario_nombre": n, "tipo": p.tipo, "fecha": p.fecha_ausencia.isoformat(), "motivo": p.motivo, "estado": p.estado} for p, n in res]

@app.post("/admin/decidir_preaviso/{pid}")
def decidir(pid: int, d: DecisionData, db: Session = Depends(get_db)):
    p = db.query(Preaviso).filter(Preaviso.id == pid).first()
    if p: p.estado = d.estado; p.visto_admin = True; db.commit(); return {"status": "ok"}
    raise HTTPException(status_code=404)