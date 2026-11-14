"""InmobiSV: servidor local para demostración académica (Python estándar)."""
import os, sqlite3, secrets, hashlib, hmac, json, re, time, math, base64
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from http.cookies import SimpleCookie
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('INMOBI_DB', ROOT / 'data' / 'inmobisv.sqlite3'))
ROLES = ('comprador','vendedor','administrador')
STATES = ('activa','pausada','vendida','rentada','pendiente','rechazada')
DEMO_PASSWORD = 'Inmobi2026!'
DEPARTMENTS = ['Ahuachapán','Santa Ana','Sonsonate','Chalatenango','La Libertad','San Salvador','Cuscatlán','La Paz','Cabañas','San Vicente','Usulután','San Miguel','Morazán','La Unión']

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()

def check_password(password, stored):
    return hmac.compare_digest(hash_password(password, stored.split(':')[0]), stored)

@contextmanager
def db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=10); c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys = ON')
    try:
        with c: yield c
    finally: c.close()

def init_db(demo=False):
    with db() as c:
        c.executescript((ROOT/'schema.sql').read_text(encoding='utf-8'))
        if not demo: return
        for role,name in zip(ROLES,['Comprador Demo','Vendedor Demo','Administrador Demo']):
            c.execute('INSERT OR IGNORE INTO users(name,email,password,role,phone) VALUES(?,?,?,?,?)',(name,role+'@inmobi.test',hash_password(DEMO_PASSWORD),role,''))
        seller=c.execute("SELECT id FROM users WHERE email='vendedor@inmobi.test'").fetchone()[0]
        samples=[('Terreno con vista al volcán','San Miguel','San Miguel',24500,600,20,30,'Residencial','Terreno amplio y de topografía regular, ideal para proyectar una vivienda.','volcan',13.478,-88.177),('Lote cerca de la costa','La Libertad','La Libertad',38000,450,15,30,'Residencial','Espacio para diseñar una casa de descanso cerca de la costa.','costa',13.49,-89.32),('Terreno entre montañas','Morazán','Perquín',18500,1200,30,40,'Rural','Entorno natural, espacio abierto y vistas a las montañas.','montana',13.96,-88.16),('Lote para tu próximo hogar','Santa Ana','Santa Ana',29500,400,16,25,'Residencial','Lote de dimensiones prácticas para un proyecto familiar.','campo',13.99,-89.55),('Parcela de campo','Usulután','Santiago de María',22000,900,30,30,'Agrícola','Parcela de ejemplo con vegetación y acceso rural.','campo',13.48,-88.47),('Terreno con paisaje de montaña','La Unión','Conchagua',32000,800,20,40,'Rural','Terreno de ejemplo para explorar distintas opciones de inversión.','costa',13.30,-87.87)]
        for i,(title,dep,city,price,area,width,length,kind,desc,art,lat,lon) in enumerate(samples,1):
            c.execute('''INSERT OR IGNORE INTO properties(id,seller_id,title,department,city,price,area,width,length,kind,description,photos,lat,lon,status,demo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)''',(i,seller,title,dep,city,price,area,width,length,kind,desc,json.dumps([f'/static/{art}.svg']),lat,lon,'activa'))

class APIError(Exception):
    def __init__(self,status,message): self.status=status; self.message=message

def fail(status,message): raise APIError(status,message)
def public_user(u): return {k:u[k] for k in ('id','name','email','role','phone','active')}
def prop(p):
    d=dict(p); d['photos']=json.loads(d['photos']); return d

def number(v,key,minval=0,maxval=1e9,optional=False):
    if optional and (v is None or v==''): return None
    try: n=float(v)
    except (ValueError,TypeError): fail(400,'Valor inválido: '+key)
    if not math.isfinite(n) or not minval<=n<=maxval: fail(400,'Valor fuera de rango: '+key)
    return n

def string(data,key,minlen=1,maxlen=300):
    v=data.get(key,''); v=v.strip() if isinstance(v,str) else ''
    if not minlen<=len(v)<=maxlen: fail(400,'Revisa el campo '+key)
    return v

def phone_ok(v): return bool(re.fullmatch(r'[67][0-9]{7}',v))

def property_data(d):
    department=string(d,'department'); kind=string(d,'kind')
    if department not in DEPARTMENTS or kind not in ('Residencial','Rural','Agrícola','Comercial'): fail(400,'Departamento o tipo inválido')
    photos=d.get('photos',[])
    if not isinstance(photos,list) or not 1<=len(photos)<=4: fail(400,'Agrega entre 1 y 4 fotos')
    for p in photos:
        if not isinstance(p,str): fail(400,'Foto inválida')
        if p in ['/static/'+x+'.svg' for x in ('volcan','costa','montana','campo')]: continue
        if not re.fullmatch(r'data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+',p) or len(p)>1400000: fail(400,'Foto inválida o demasiado grande (máx. 1 MB)')
        try:
            raw=base64.b64decode(p.split(',')[1],validate=True)
            fmt=p.split('/')[1].split(';')[0]
            if not (fmt=='jpeg' and raw.startswith(b'\xff\xd8\xff') or fmt=='png' and raw.startswith(b'\x89PNG\r\n\x1a\n') or fmt=='webp' and raw[:4]==b'RIFF' and raw[8:12]==b'WEBP'): fail(400,'Archivo de imagen inválido')
        except ValueError: fail(400,'Foto inválida')
    lat=number(d.get('lat'),'latitud',-90,90,True); lon=number(d.get('lon'),'longitud',-180,180,True)
    if (lat is None)!=(lon is None): fail(400,'Completa ambas coordenadas o déjalas vacías')
    return (string(d,'title',5,100),department,string(d,'city',2,100),number(d.get('price'),'precio',1),number(d.get('area'),'área',1),number(d.get('width'),'ancho',0.1),number(d.get('length'),'largo',0.1),kind,string(d,'description',10,2000),json.dumps(photos),lat,lon)

class Handler(BaseHTTPRequestHandler):
    def send_json(self,data,status=200,cookie=None):
        raw=json.dumps(data,ensure_ascii=False,allow_nan=False).encode(); self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Length',str(len(raw)))
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers(); self.wfile.write(raw)
    def body(self):
        try: length=int(self.headers.get('Content-Length','0'))
        except ValueError: fail(400,'Solicitud inválida')
        if not 0<=length<=6500000: fail(413,'Solicitud demasiado grande')
        try: data=json.loads(self.rfile.read(length) or b'{}')
        except (ValueError,UnicodeError): fail(400,'JSON inválido')
        if not isinstance(data,dict): fail(400,'Se esperaba un objeto JSON')
        return data
    def token(self):
        try:
            cookie=SimpleCookie(self.headers.get('Cookie','')); return cookie['inmobi'].value if 'inmobi' in cookie else ''
        except Exception: return ''
    def session(self,c):
        return c.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>? AND u.active=1',(hashlib.sha256(self.token().encode()).hexdigest(),time.time())).fetchone()
    def require(self,u,*roles):
        if u is None: fail(401,'Inicia sesión para continuar')
        if roles and u['role'] not in roles: fail(403,'No tienes permiso para esta acción')
    def new_session(self,c,u):
        token=secrets.token_urlsafe(32); c.execute('DELETE FROM sessions WHERE expires<=? OR token=?',(time.time(),hashlib.sha256(self.token().encode()).hexdigest()))
        c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],time.time()+86400))
        c.commit(); self.send_json({'user':public_user(u)},cookie='inmobi='+token+'; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400'+('; Secure' if os.getenv('INMOBI_SECURE_COOKIE')=='1' else ''))
    def route(self,method):
        path=urlparse(self.path).path; q=parse_qs(urlparse(self.path).query)
        if not path.startswith('/api/'):
            if method!='GET': fail(405,'Método no permitido')
            filename='index.html' if path=='/' else path.removeprefix('/static/') if path.startswith('/static/') else ''
            if not filename or '/' in filename or '\\' in filename or filename.startswith('.'): fail(404,'Página no encontrada')
            f=ROOT/'static'/filename
            if not f.is_file(): fail(404,'Página no encontrada')
            mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml'}.get(f.suffix)
            if not mime: fail(404,'Página no encontrada')
            raw=f.read_bytes(); self.send_response(200); self.send_header('Content-Type',mime); self.send_header('Content-Length',str(len(raw))); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; frame-src https://www.openstreetmap.org; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"); self.end_headers(); self.wfile.write(raw); return
        if method!='GET':
            if self.headers.get('X-Inmobi-Request')!='1' or not self.headers.get('Content-Type','').startswith('application/json'): fail(403,'Solicitud no autorizada')
            # No CORS; el encabezado personalizado impide envíos desde otros orígenes.
        with db() as c:
            u=self.session(c); d=self.body() if method!='GET' else {}; out=None
            if path=='/api/me' and method=='GET': out={'user':public_user(u) if u else None}
            elif path=='/api/login' and method=='POST':
                email=string(d,'email',3,200).lower(); password=string(d,'password',1,200)
                user=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                if not user or not user['active'] or not check_password(password,user['password']): fail(401,'Credenciales incorrectas o cuenta deshabilitada')
                return self.new_session(c,user)
            elif path=='/api/register' and method=='POST':
                name=string(d,'name',2,100); email=string(d,'email',3,200).lower(); password=string(d,'password',8,200); role=d.get('role'); phone=string(d,'phone',0,8)
                if role not in ROLES[:2] or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or (role=='vendedor' and not phone_ok(phone)) or (phone and not phone_ok(phone)): fail(400,'Revisa el correo, rol y teléfono salvadoreño de 8 dígitos')
                try: uid=c.execute('INSERT INTO users(name,email,password,role,phone) VALUES(?,?,?,?,?)',(name,email,hash_password(password),role,phone)).lastrowid
                except sqlite3.IntegrityError: fail(409,'Ese correo ya está registrado')
                return self.new_session(c,c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())
            elif path=='/api/logout' and method=='POST':
                c.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(self.token().encode()).hexdigest(),)); c.commit(); return self.send_json({'ok':True},cookie='inmobi=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0')
            elif path=='/api/properties' and method=='GET':
                rows=c.execute("SELECT p.*,u.name seller_name,u.phone seller_phone FROM properties p JOIN users u ON u.id=p.seller_id WHERE p.status='activa' AND u.active=1 ORDER BY p.id DESC").fetchall(); out=[prop(p) for p in rows]
            elif path=='/api/my-properties' and method=='GET':
                self.require(u,'vendedor'); out=[prop(p) for p in c.execute('SELECT * FROM properties WHERE seller_id=? ORDER BY id DESC',(u['id'],))]
            elif path=='/api/properties' and method=='POST':
                self.require(u,'vendedor'); vals=property_data(d); pid=c.execute('INSERT INTO properties(seller_id,title,department,city,price,area,width,length,kind,description,photos,lat,lon,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(u['id'],*vals,'activa')).lastrowid; out={'id':pid}
            elif re.fullmatch(r'/api/properties/\d+',path) and method in ('PUT','PATCH'):
                self.require(u,'vendedor','administrador'); pid=int(path.split('/')[-1]); p=c.execute('SELECT * FROM properties WHERE id=?',(pid,)).fetchone()
                if not p: fail(404,'Publicación no encontrada')
                if u['role']=='vendedor' and p['seller_id']!=u['id']: fail(403,'No eres propietario de esta publicación')
                if method=='PATCH':
                    status=d.get('status'); allowed=STATES if u['role']=='administrador' else STATES[:4]
                    if status not in allowed or (u['role']=='vendedor' and p['status'] in ('rechazada','pendiente')): fail(403,'Cambio de estado no permitido')
                    c.execute('UPDATE properties SET status=? WHERE id=?',(status,pid))
                else:
                    self.require(u,'vendedor'); vals=property_data(d)
                    c.execute('UPDATE properties SET title=?,department=?,city=?,price=?,area=?,width=?,length=?,kind=?,description=?,photos=?,lat=?,lon=? WHERE id=?',(*vals,pid))
                    if p['price']!=vals[3]:
                        c.execute('INSERT INTO price_history(property_id,old_price,new_price) VALUES(?,?,?)',(pid,p['price'],vals[3]))
                        if vals[3]<p['price']: c.execute('INSERT INTO notifications(user_id,property_id,message) SELECT user_id,property_id,? FROM favorites WHERE property_id=?',(f"Bajó de precio: {vals[0]} (${p['price']:,.0f} → ${vals[3]:,.0f})",pid))
                out={'ok':True}
            elif path=='/api/favorites' and method=='GET':
                self.require(u,'comprador'); out=[prop(p) for p in c.execute('SELECT p.*, f.saved_price FROM favorites f JOIN properties p ON p.id=f.property_id WHERE f.user_id=?',(u['id'],))]
            elif re.fullmatch(r'/api/favorites/\d+',path) and method in ('POST','DELETE'):
                self.require(u,'comprador'); pid=int(path.split('/')[-1]); p=c.execute("SELECT p.* FROM properties p JOIN users u ON p.seller_id=u.id WHERE p.id=? AND p.status='activa' AND u.active=1",(pid,)).fetchone()
                if method=='POST':
                    if not p: fail(404,'Terreno no disponible')
                    c.execute('INSERT OR IGNORE INTO favorites(user_id,property_id,saved_price) VALUES(?,?,?)',(u['id'],pid,p['price']))
                else: c.execute('DELETE FROM favorites WHERE user_id=? AND property_id=?',(u['id'],pid))
                out={'ok':True}
            elif path=='/api/notifications' and method=='GET':
                self.require(u,'comprador'); out=[dict(n) for n in c.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC',(u['id'],))]
            elif path=='/api/notifications/read' and method=='POST':
                self.require(u,'comprador'); c.execute('UPDATE notifications SET is_read=1 WHERE user_id=?',(u['id'],)); out={'ok':True}
            elif path=='/api/profile' and method=='PATCH':
                self.require(u,'comprador','vendedor'); phone=string(d,'phone',0,8)
                if (u['role']=='vendedor' or phone) and not phone_ok(phone): fail(400,'Teléfono salvadoreño inválido')
                c.execute('UPDATE users SET phone=? WHERE id=?',(phone,u['id'])); out={'ok':True}
            elif path=='/api/role-request' and method=='POST':
                self.require(u,'comprador'); phone=string(d,'phone',8,8)
                if not phone_ok(phone): fail(400,'Teléfono inválido')
                c.execute('UPDATE users SET phone=? WHERE id=?',(phone,u['id'])); c.execute('INSERT INTO role_requests(user_id,status) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET status=\'pendiente\'',(u['id'],'pendiente')); out={'ok':True}
            elif path=='/api/admin' and method=='GET':
                self.require(u,'administrador'); out={'users':[public_user(x) for x in c.execute('SELECT * FROM users ORDER BY id')],'properties':[prop(x) for x in c.execute('SELECT p.*,u.name seller_name FROM properties p JOIN users u ON p.seller_id=u.id ORDER BY p.id DESC')],'requests':[dict(x) for x in c.execute('SELECT r.*,u.name,u.email,u.phone FROM role_requests r JOIN users u ON u.id=r.user_id WHERE r.status=\'pendiente\'')]}
            elif re.fullmatch(r'/api/admin/users/\d+',path) and method=='PATCH':
                self.require(u,'administrador'); uid=int(path.split('/')[-1]); target=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
                if not target: fail(404,'Usuario no encontrado')
                if target['role']=='administrador' or type(d.get('active')) is not bool: fail(403,'Cambio no permitido')
                c.execute('UPDATE users SET active=? WHERE id=?',(int(d['active']),uid))
                if not d['active']: c.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
                out={'ok':True}
            elif re.fullmatch(r'/api/admin/requests/\d+',path) and method=='PATCH':
                self.require(u,'administrador'); uid=int(path.split('/')[-1]); status=d.get('status'); r=c.execute("SELECT * FROM role_requests WHERE user_id=? AND status='pendiente'",(uid,)).fetchone()
                if not r or status not in ('aprobada','rechazada'): fail(400,'Solicitud inválida')
                if status=='aprobada':
                    target=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
                    if not target['active'] or target['role']!='comprador' or not phone_ok(target['phone']): fail(400,'El usuario no cumple los requisitos')
                    c.execute("UPDATE users SET role='vendedor' WHERE id=?",(uid,))
                c.execute('UPDATE role_requests SET status=? WHERE user_id=?',(status,uid)); out={'ok':True}
            else: fail(404,'Ruta no encontrada')
            c.commit(); self.send_json(out)
    def dispatch(self,method):
        try: self.route(method)
        except APIError as e: self.send_json({'error':e.message},e.status)
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception as e:
            print('Error interno:',repr(e)); self.send_json({'error':'Error interno del servidor'},500)
    def do_GET(self): self.dispatch('GET')
    def do_POST(self): self.dispatch('POST')
    def do_PUT(self): self.dispatch('PUT')
    def do_PATCH(self): self.dispatch('PATCH')
    def do_DELETE(self): self.dispatch('DELETE')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--demo',action='store_true',help='Crear usuarios y anuncios ficticios'); parser.add_argument('--port',type=int,default=8000); parser.add_argument('--host',default='127.0.0.1'); args=parser.parse_args()
    init_db(args.demo); print(f'InmobiSV: http://{args.host}:{args.port} | SQLite: {DB}',flush=True)
    ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
