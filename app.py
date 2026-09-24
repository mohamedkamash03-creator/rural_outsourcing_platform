import os, sqlite3, hashlib, secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import jwt

BASE=os.path.dirname(__file__)
DB=os.path.join(BASE,'database.db')
SECRET=os.getenv('APP_SECRET','change-this-secret-in-production')

app=FastAPI(title='Rural Workforce OS', version='1.0.0')
app.mount('/static', StaticFiles(directory=os.path.join(BASE,'static')), name='static')

def db():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    return c

def init_db():
    c=db(); cur=c.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL, active INTEGER DEFAULT 1, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS villages(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, governorate TEXT NOT NULL, district TEXT, eligible INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS offices(id INTEGER PRIMARY KEY AUTOINCREMENT, village_id INTEGER NOT NULL, name TEXT NOT NULL, capacity INTEGER DEFAULT 50, workstations INTEGER DEFAULT 50, internet_status TEXT DEFAULT 'Good', power_backup INTEGER DEFAULT 1, address TEXT, FOREIGN KEY(village_id) REFERENCES villages(id));
    CREATE TABLE IF NOT EXISTS workers(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE NOT NULL, national_id TEXT, dob TEXT, village_id INTEGER, education TEXT, university TEXT, graduation_year INTEGER, phone TEXT, cv TEXT, employment_type TEXT, availability TEXT, status TEXT DEFAULT 'Pending', id_status TEXT DEFAULT 'Pending', overall_score REAL DEFAULT 0, FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(village_id) REFERENCES villages(id));
    CREATE TABLE IF NOT EXISTS skills(id INTEGER PRIMARY KEY AUTOINCREMENT, worker_id INTEGER NOT NULL, name TEXT NOT NULL, score REAL DEFAULT 0, FOREIGN KEY(worker_id) REFERENCES workers(id));
    CREATE TABLE IF NOT EXISTS assessments(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, category TEXT NOT NULL, passing_score REAL DEFAULT 70, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS questions(id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id INTEGER NOT NULL, question TEXT NOT NULL, options TEXT NOT NULL, answer TEXT NOT NULL, points INTEGER DEFAULT 1, FOREIGN KEY(assessment_id) REFERENCES assessments(id));
    CREATE TABLE IF NOT EXISTS assessment_attempts(id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id INTEGER NOT NULL, worker_id INTEGER NOT NULL, score REAL, passed INTEGER, completed_at TEXT, FOREIGN KEY(assessment_id) REFERENCES assessments(id), FOREIGN KEY(worker_id) REFERENCES workers(id));
    CREATE TABLE IF NOT EXISTS courses(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, service TEXT NOT NULL, description TEXT, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS lessons(id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER NOT NULL, title TEXT NOT NULL, content TEXT, sort_order INTEGER DEFAULT 1, FOREIGN KEY(course_id) REFERENCES courses(id));
    CREATE TABLE IF NOT EXISTS enrollments(id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER NOT NULL, worker_id INTEGER NOT NULL, progress REAL DEFAULT 0, completed INTEGER DEFAULT 0, FOREIGN KEY(course_id) REFERENCES courses(id), FOREIGN KEY(worker_id) REFERENCES workers(id));
    CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT NOT NULL, industry TEXT, contact_name TEXT, email TEXT, phone TEXT, status TEXT DEFAULT 'Active', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS service_requests(id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER NOT NULL, service TEXT NOT NULL, title TEXT NOT NULL, description TEXT, workers_required INTEGER DEFAULT 1, employment_type TEXT, duration TEXT, language TEXT, start_date TEXT, budget REAL, status TEXT DEFAULT 'New', created_at TEXT NOT NULL, FOREIGN KEY(client_id) REFERENCES clients(id));
    CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER NOT NULL, request_id INTEGER, name TEXT NOT NULL, service TEXT NOT NULL, description TEXT, workers_required INTEGER DEFAULT 1, start_date TEXT, end_date TEXT, budget REAL, status TEXT DEFAULT 'Active', FOREIGN KEY(client_id) REFERENCES clients(id));
    CREATE TABLE IF NOT EXISTS assignments(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, worker_id INTEGER NOT NULL, role TEXT, shift TEXT, office_id INTEGER, status TEXT DEFAULT 'Assigned', assigned_at TEXT NOT NULL, FOREIGN KEY(project_id) REFERENCES projects(id), FOREIGN KEY(worker_id) REFERENCES workers(id), FOREIGN KEY(office_id) REFERENCES offices(id));
    CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, name TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, capacity INTEGER DEFAULT 10, FOREIGN KEY(project_id) REFERENCES projects(id));
    CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY AUTOINCREMENT, worker_id INTEGER NOT NULL, project_id INTEGER, office_id INTEGER, date TEXT NOT NULL, clock_in TEXT, clock_out TEXT, status TEXT DEFAULT 'Present', FOREIGN KEY(worker_id) REFERENCES workers(id));
    CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, worker_id INTEGER, title TEXT NOT NULL, description TEXT, priority TEXT DEFAULT 'Medium', deadline TEXT, status TEXT DEFAULT 'Pending', quality_score REAL, created_at TEXT NOT NULL, FOREIGN KEY(project_id) REFERENCES projects(id), FOREIGN KEY(worker_id) REFERENCES workers(id));
    CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT NOT NULL, body TEXT, read INTEGER DEFAULT 0, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT NOT NULL, entity TEXT, entity_id INTEGER, created_at TEXT NOT NULL);
    ''')
    c.commit()
    seed(c)
    c.close()

def ph(p): return hashlib.sha256(p.encode()).hexdigest()
def seed(c):
    cur=c.cursor()
    if cur.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0:
        now=datetime.utcnow().isoformat()
        users=[('System Admin','admin@ruralos.local','Admin123!','admin'),('HR Manager','hr@ruralos.local','HR123!','hr'),('Operations Manager','ops@ruralos.local','Ops123!','operations'),('Village Coordinator','coord@ruralos.local','Coord123!','coordinator'),('Demo Worker','worker@ruralos.local','Worker123!','worker'),('Demo Client','client@ruralos.local','Client123!','client')]
        for n,e,p,r in users: cur.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',(n,e,ph(p),r,now))
    if cur.execute('SELECT COUNT(*) FROM villages').fetchone()[0]==0:
        cur.execute("INSERT INTO villages(name,governorate,district) VALUES('Al Village','Menoufia','Shibin El Kom')")
        vid=cur.lastrowid
        cur.execute("INSERT INTO offices(village_id,name,capacity,workstations,address) VALUES(?,?,?,?,?)",(vid,'Rural Work Center #01',50,50,'Village main center'))
    if cur.execute('SELECT COUNT(*) FROM workers').fetchone()[0]==0:
        uid=cur.execute("SELECT id FROM users WHERE email='worker@ruralos.local'").fetchone()[0]
        vid=cur.execute('SELECT id FROM villages LIMIT 1').fetchone()[0]
        cur.execute("INSERT INTO workers(user_id,national_id,dob,village_id,education,university,graduation_year,phone,employment_type,availability,status,id_status,overall_score) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(uid,'29901011234567','1999-01-01',vid,'Bachelor','Example University',2021,'01000000000','Full-time','Sun-Thu 09:00-17:00','Available','Verified',88))
        wid=cur.lastrowid
        for s,v in [('English',86),('Communication',91),('Excel',82),('Typing',94)]: cur.execute('INSERT INTO skills(worker_id,name,score) VALUES(?,?,?)',(wid,s,v))
    if cur.execute('SELECT COUNT(*) FROM clients').fetchone()[0]==0:
        cur.execute("INSERT INTO clients(company_name,industry,contact_name,email,phone) VALUES(?,?,?,?,?)",('Demo Client Co.','E-commerce','Client Manager','client@demo.local','01000000001'))
    if cur.execute('SELECT COUNT(*) FROM assessments').fetchone()[0]==0:
        cur.execute("INSERT INTO assessments(title,category,passing_score) VALUES(?,?,?)",('General Digital Skills','General',70)); aid=cur.lastrowid
        qs=[('Which tool is commonly used for spreadsheets?','Excel|Photoshop|Git|Figma','Excel'),('What does KPI stand for?','Key Performance Indicator|Knowledge Process Index|Key Project Input|None','Key Performance Indicator'),('Which is a strong password?','12345678|password|Mango#47River!|qwerty','Mango#47River!')]
        for q,o,a in qs: cur.execute('INSERT INTO questions(assessment_id,question,options,answer) VALUES(?,?,?,?)',(aid,q,o,a))
    if cur.execute('SELECT COUNT(*) FROM courses').fetchone()[0]==0:
        cur.execute("INSERT INTO courses(title,service,description) VALUES(?,?,?)",('Workplace Digital Skills','General','Core digital skills for remote outsourcing work.')); cid=cur.lastrowid
        for i,t in enumerate(['Remote Work Basics','Communication & Professionalism','Quality and Data Security'],1): cur.execute('INSERT INTO lessons(course_id,title,content,sort_order) VALUES(?,?,?,?)',(cid,t,'Training lesson content and practical exercises.',i))
    c.commit()

init_db()

class Login(BaseModel): email:str; password:str
class WorkerCreate(BaseModel): name:str; email:str; password:str; national_id:str; dob:str; village_id:int; education:str; university:str; graduation_year:int; phone:str; employment_type:str='Full-time'; availability:str=''
class ClientCreate(BaseModel): company_name:str; industry:str=''; contact_name:str=''; email:str=''; phone:str=''
class RequestCreate(BaseModel): client_id:int; service:str; title:str; description:str=''; workers_required:int=1; employment_type:str='Full-time'; duration:str=''; language:str=''; start_date:str=''; budget:float=0
class ProjectCreate(BaseModel): client_id:int; request_id:Optional[int]=None; name:str; service:str; description:str=''; workers_required:int=1; start_date:str=''; end_date:str=''; budget:float=0
class AssignCreate(BaseModel): project_id:int; worker_id:int; role:str=''; shift:str=''; office_id:Optional[int]=None
class TaskCreate(BaseModel): project_id:int; worker_id:Optional[int]=None; title:str; description:str=''; priority:str='Medium'; deadline:str=''
class StatusUpdate(BaseModel): status:str
class AttendanceAction(BaseModel): project_id:Optional[int]=None; office_id:Optional[int]=None
class AssessmentSubmit(BaseModel): answers:dict
class CourseEnroll(BaseModel): course_id:int


def token_for(u):
    return jwt.encode({'sub':u['id'],'role':u['role'],'exp':datetime.utcnow()+timedelta(hours=12)},SECRET,algorithm='HS256')

def current(request:Request):
    h=request.headers.get('Authorization','')
    if not h.startswith('Bearer '): raise HTTPException(401,'Authentication required')
    try: data=jwt.decode(h[7:],SECRET,algorithms=['HS256'])
    except Exception: raise HTTPException(401,'Invalid or expired token')
    c=db(); u=c.execute('SELECT * FROM users WHERE id=? AND active=1',(data['sub'],)).fetchone(); c.close()
    if not u: raise HTTPException(401,'User not found')
    return dict(u)

def role(*roles):
    def dep(u=Depends(current)):
        if u['role'] not in roles and u['role']!='admin': raise HTTPException(403,'Insufficient permissions')
        return u
    return dep

def log(c,u,action,entity=None,eid=None): c.execute('INSERT INTO audit_logs(user_id,action,entity,entity_id,created_at) VALUES(?,?,?,?,?)',(u['id'],action,entity,eid,datetime.utcnow().isoformat()))

@app.get('/')
def home(): return FileResponse(os.path.join(BASE,'static','index.html'))

@app.post('/api/login')
def login(x:Login):
    c=db(); u=c.execute('SELECT * FROM users WHERE email=? AND password_hash=? AND active=1',(x.email,ph(x.password))).fetchone(); c.close()
    if not u: raise HTTPException(401,'Invalid email or password')
    return {'token':token_for(u),'user':dict(u)}

@app.get('/api/me')
def me(u=Depends(current)):
    c=db(); w=c.execute('SELECT w.*,v.name village_name FROM workers w LEFT JOIN villages v ON v.id=w.village_id WHERE w.user_id=?',(u['id'],)).fetchone(); c.close()
    return {'user':u,'worker':dict(w) if w else None}

@app.get('/api/dashboard')
def dashboard(u=Depends(current)):
    c=db()
    data={
      'workers':c.execute("SELECT COUNT(*) n FROM workers").fetchone()['n'],
      'available_workers':c.execute("SELECT COUNT(*) n FROM workers WHERE status='Available'").fetchone()['n'],
      'clients':c.execute('SELECT COUNT(*) n FROM clients').fetchone()['n'],
      'projects':c.execute("SELECT COUNT(*) n FROM projects WHERE status='Active'").fetchone()['n'],
      'requests':c.execute("SELECT COUNT(*) n FROM service_requests WHERE status IN ('New','In Review')").fetchone()['n'],
      'offices':c.execute('SELECT COUNT(*) n FROM offices').fetchone()['n'],
      'tasks':c.execute("SELECT COUNT(*) n FROM tasks WHERE status NOT IN ('Completed','Approved')").fetchone()['n'],
      'training':c.execute('SELECT COUNT(*) n FROM enrollments WHERE completed=1').fetchone()['n']}
    c.close(); return data

@app.get('/api/villages')
def villages(u=Depends(current)):
    c=db(); rows=c.execute('SELECT v.*,COUNT(w.id) workers FROM villages v LEFT JOIN workers w ON w.village_id=v.id GROUP BY v.id').fetchall(); c.close(); return [dict(r) for r in rows]

@app.get('/api/offices')
def offices(u=Depends(current)):
    c=db(); rows=c.execute('SELECT o.*,v.name village_name,COUNT(a.id) assigned FROM offices o JOIN villages v ON v.id=o.village_id LEFT JOIN assignments a ON a.office_id=o.id AND a.status="Assigned" GROUP BY o.id').fetchall(); c.close(); return [dict(r) for r in rows]

@app.get('/api/workers')
def workers(u=Depends(current)):
    c=db(); rows=c.execute('SELECT w.*,u.name,u.email,v.name village_name FROM workers w JOIN users u ON u.id=w.user_id LEFT JOIN villages v ON v.id=w.village_id ORDER BY w.id DESC').fetchall(); c.close(); return [dict(r) for r in rows]

@app.post('/api/workers')
def create_worker(x:WorkerCreate,u=Depends(role('admin','hr'))):
    c=db(); now=datetime.utcnow().isoformat()
    try:
        cur=c.cursor(); cur.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',(x.name,x.email,ph(x.password),'worker',now)); uid=cur.lastrowid
        cur.execute('INSERT INTO workers(user_id,national_id,dob,village_id,education,university,graduation_year,phone,employment_type,availability) VALUES(?,?,?,?,?,?,?,?,?,?)',(uid,x.national_id,x.dob,x.village_id,x.education,x.university,x.graduation_year,x.phone,x.employment_type,x.availability)); wid=cur.lastrowid
        log(c,u,'CREATE','worker',wid); c.commit(); return {'id':wid}
    except sqlite3.IntegrityError: c.rollback(); raise HTTPException(400,'Email already exists')
    finally: c.close()

@app.post('/api/workers/{wid}/verify')
def verify_worker(wid:int,u=Depends(role('admin','hr'))):
    c=db(); c.execute("UPDATE workers SET id_status='Verified',status='Available' WHERE id=?",(wid,)); log(c,u,'VERIFY','worker',wid); c.commit(); c.close(); return {'ok':True}

@app.get('/api/assessments')
def assessments(u=Depends(current)):
    c=db(); rows=c.execute('SELECT * FROM assessments WHERE active=1').fetchall(); c.close(); return [dict(r) for r in rows]

@app.get('/api/assessments/{aid}')
def assessment(aid:int,u=Depends(current)):
    c=db(); a=c.execute('SELECT * FROM assessments WHERE id=?',(aid,)).fetchone(); qs=c.execute('SELECT id,question,options,points FROM questions WHERE assessment_id=?',(aid,)).fetchall(); c.close();
    if not a: raise HTTPException(404,'Assessment not found')
    return {'assessment':dict(a),'questions':[dict(q) for q in qs]}

@app.post('/api/assessments/{aid}/submit')
def submit_assessment(aid:int,x:AssessmentSubmit,u=Depends(current)):
    c=db(); w=c.execute('SELECT * FROM workers WHERE user_id=?',(u['id'],)).fetchone()
    if not w: raise HTTPException(400,'Worker profile required')
    qs=c.execute('SELECT * FROM questions WHERE assessment_id=?',(aid,)).fetchall(); total=sum(q['points'] for q in qs) or 1; got=0
    for q in qs:
        if str(x.answers.get(str(q['id']),''))==q['answer']: got+=q['points']
    score=round(got*100/total,2); a=c.execute('SELECT passing_score FROM assessments WHERE id=?',(aid,)).fetchone(); passed=1 if score>=a['passing_score'] else 0
    c.execute('INSERT INTO assessment_attempts(assessment_id,worker_id,score,passed,completed_at) VALUES(?,?,?,?,?)',(aid,w['id'],score,passed,datetime.utcnow().isoformat()))
    c.execute('UPDATE workers SET overall_score=? WHERE id=?',(score,w['id'])); c.commit(); c.close(); return {'score':score,'passed':bool(passed)}

@app.get('/api/courses')
def courses(u=Depends(current)):
    c=db(); rows=c.execute('SELECT c.*,COUNT(l.id) lessons FROM courses c LEFT JOIN lessons l ON l.course_id=c.id GROUP BY c.id').fetchall(); c.close(); return [dict(r) for r in rows]

@app.post('/api/courses/enroll')
def enroll(x:CourseEnroll,u=Depends(current)):
    c=db(); w=c.execute('SELECT id FROM workers WHERE user_id=?',(u['id'],)).fetchone()
    if not w: raise HTTPException(400,'Worker profile required')
    try: c.execute('INSERT INTO enrollments(course_id,worker_id) VALUES(?,?)',(x.course_id,w['id'])); c.commit()
    except sqlite3.IntegrityError: pass
    c.close(); return {'ok':True}

@app.get('/api/clients')
def clients(u=Depends(current)):
    c=db(); rows=c.execute('SELECT * FROM clients ORDER BY id DESC').fetchall(); c.close(); return [dict(r) for r in rows]

@app.post('/api/clients')
def create_client(x:ClientCreate,u=Depends(role('admin','operations'))):
    c=db(); cur=c.cursor(); cur.execute('INSERT INTO clients(company_name,industry,contact_name,email,phone,created_at) VALUES(?,?,?,?,?,?)',(x.company_name,x.industry,x.contact_name,x.email,x.phone,datetime.utcnow().isoformat())); cid=cur.lastrowid; log(c,u,'CREATE','client',cid); c.commit(); c.close(); return {'id':cid}

@app.get('/api/requests')
def requests(u=Depends(current)):
    c=db(); rows=c.execute('SELECT r.*,c.company_name FROM service_requests r JOIN clients c ON c.id=r.client_id ORDER BY r.id DESC').fetchall(); c.close(); return [dict(r) for r in rows]

@app.post('/api/requests')
def create_request(x:RequestCreate,u=Depends(current)):
    c=db(); cur=c.cursor(); cur.execute('INSERT INTO service_requests(client_id,service,title,description,workers_required,employment_type,duration,language,start_date,budget,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(x.client_id,x.service,x.title,x.description,x.workers_required,x.employment_type,x.duration,x.language,x.start_date,x.budget,datetime.utcnow().isoformat())); rid=cur.lastrowid; log(c,u,'CREATE','service_request',rid); c.commit(); c.close(); return {'id':rid}

@app.get('/api/projects')
def projects(u=Depends(current)):
    c=db(); rows=c.execute('SELECT p.*,c.company_name,(SELECT COUNT(*) FROM assignments a WHERE a.project_id=p.id AND a.status="Assigned") assigned FROM projects p JOIN clients c ON c.id=p.client_id ORDER BY p.id DESC').fetchall(); c.close(); return [dict(r) for r in rows]

@app.post('/api/projects')
def create_project(x:ProjectCreate,u=Depends(role('admin','operations'))):
    c=db(); cur=c.cursor(); cur.execute('INSERT INTO projects(client_id,request_id,name,service,description,workers_required,start_date,end_date,budget) VALUES(?,?,?,?,?,?,?,?,?)',(x.client_id,x.request_id,x.name,x.service,x.description,x.workers_required,x.start_date,x.end_date,x.budget)); pid=cur.lastrowid; log(c,u,'CREATE','project',pid); c.commit(); c.close(); return {'id':pid}

@app.post('/api/assignments')
def assign(x:AssignCreate,u=Depends(role('admin','operations','coordinator'))):
    c=db(); conflict=c.execute("SELECT COUNT(*) n FROM assignments WHERE worker_id=? AND status='Assigned' AND project_id<>?",(x.worker_id,x.project_id)).fetchone()['n']
    if conflict and x.shift: pass
    c.execute('INSERT INTO assignments(project_id,worker_id,role,shift,office_id,assigned_at) VALUES(?,?,?,?,?,?)',(x.project_id,x.worker_id,x.role,x.shift,x.office_id,datetime.utcnow().isoformat()))
    c.execute("UPDATE workers SET status='Working' WHERE id=?",(x.worker_id,)); aid=c.execute('SELECT last_insert_rowid() id').fetchone()['id']; log(c,u,'ASSIGN','assignment',aid); c.commit(); c.close(); return {'id':aid}

@app.get('/api/assignments')
def assignments(u=Depends(current)):
    c=db(); rows=c.execute('SELECT a.*,p.name project_name,w.id worker_id,u.name worker_name,o.name office_name FROM assignments a JOIN projects p ON p.id=a.project_id JOIN workers w ON w.id=a.worker_id JOIN users u ON u.id=w.user_id LEFT JOIN offices o ON o.id=a.office_id ORDER BY a.id DESC').fetchall(); c.close(); return [dict(r) for r in rows]

@app.get('/api/tasks')
def tasks(u=Depends(current)):
    c=db(); rows=c.execute('SELECT t.*,p.name project_name,u.name worker_name FROM tasks t JOIN projects p ON p.id=t.project_id LEFT JOIN workers w ON w.id=t.worker_id LEFT JOIN users u ON u.id=w.user_id ORDER BY t.id DESC').fetchall(); c.close(); return [dict(r) for r in rows]

@app.post('/api/tasks')
def create_task(x:TaskCreate,u=Depends(role('admin','operations','coordinator','worker'))):
    c=db(); cur=c.cursor(); cur.execute('INSERT INTO tasks(project_id,worker_id,title,description,priority,deadline,created_at) VALUES(?,?,?,?,?,?,?)',(x.project_id,x.worker_id,x.title,x.description,x.priority,x.deadline,datetime.utcnow().isoformat())); tid=cur.lastrowid; c.commit(); c.close(); return {'id':tid}

@app.patch('/api/tasks/{tid}')
def update_task(tid:int,x:StatusUpdate,u=Depends(current)):
    allowed={'Pending','Assigned','In Progress','Submitted','Under Review','Approved','Rejected','Completed'}
    if x.status not in allowed: raise HTTPException(400,'Invalid status')
    c=db(); c.execute('UPDATE tasks SET status=? WHERE id=?',(x.status,tid)); c.commit(); c.close(); return {'ok':True}

@app.get('/api/attendance')
def attendance(u=Depends(current)):
    c=db(); rows=c.execute('SELECT a.*,u.name worker_name,p.name project_name,o.name office_name FROM attendance a JOIN workers w ON w.id=a.worker_id JOIN users u ON u.id=w.user_id LEFT JOIN projects p ON p.id=a.project_id LEFT JOIN offices o ON o.id=a.office_id ORDER BY a.id DESC LIMIT 100').fetchall(); c.close(); return [dict(r) for r in rows]

@app.post('/api/attendance/clock-in')
def clock_in(x:AttendanceAction,u=Depends(current)):
    c=db(); w=c.execute('SELECT id FROM workers WHERE user_id=?',(u['id'],)).fetchone();
    if not w: raise HTTPException(400,'Worker profile required')
    now=datetime.utcnow(); date=now.date().isoformat(); existing=c.execute('SELECT * FROM attendance WHERE worker_id=? AND date=?',(w['id'],date)).fetchone()
    if existing and existing['clock_in']: raise HTTPException(400,'Already clocked in')
    if existing: c.execute('UPDATE attendance SET clock_in=?,status="Present" WHERE id=?',(now.isoformat(),existing['id']))
    else: c.execute('INSERT INTO attendance(worker_id,project_id,office_id,date,clock_in,status) VALUES(?,?,?,?,?,?)',(w['id'],x.project_id,x.office_id,date,now.isoformat(),'Present'))
    c.commit(); c.close(); return {'ok':True,'time':now.isoformat()}

@app.post('/api/attendance/clock-out')
def clock_out(u=Depends(current)):
    c=db(); w=c.execute('SELECT id FROM workers WHERE user_id=?',(u['id'],)).fetchone(); now=datetime.utcnow(); a=c.execute('SELECT * FROM attendance WHERE worker_id=? AND date=?',(w['id'],now.date().isoformat())).fetchone()
    if not a or not a['clock_in']: raise HTTPException(400,'No clock-in found')
    c.execute('UPDATE attendance SET clock_out=? WHERE id=?',(now.isoformat(),a['id'])); c.commit(); c.close(); return {'ok':True,'time':now.isoformat()}

@app.get('/api/matching/{project_id}')
def matching(project_id:int,u=Depends(role('admin','operations','coordinator'))):
    c=db(); p=c.execute('SELECT * FROM projects WHERE id=?',(project_id,)).fetchone()
    if not p: raise HTTPException(404,'Project not found')
    rows=c.execute("SELECT w.*,u.name,v.name village_name FROM workers w JOIN users u ON u.id=w.user_id LEFT JOIN villages v ON v.id=w.village_id WHERE w.status IN ('Available','Working') ORDER BY w.overall_score DESC").fetchall(); result=[]
    for r in rows:
        score=r['overall_score'] or 0
        if p['service'] in ('AI Data Labeling','AI Training/Data Annotation'): score=score*0.95
        result.append({**dict(r),'match_score':round(score,2)})
    c.close(); return result[:20]

@app.get('/api/notifications')
def notifications(u=Depends(current)):
    c=db(); rows=c.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50',(u['id'],)).fetchall(); c.close(); return [dict(r) for r in rows]
