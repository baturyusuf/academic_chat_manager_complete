"""Persistent local storage for chats, collections, message jobs and preferences."""
from __future__ import annotations
import json, os, sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

APP_NAME = "AcademicChatManager"
def app_data_dir() -> Path:
    if os.name == "nt": base=Path(os.environ.get("APPDATA",Path.home()/"AppData"/"Roaming"))
    elif os.name == "posix" and os.environ.get("XDG_DATA_HOME"): base=Path(os.environ["XDG_DATA_HOME"])
    else: base=Path.home()/".local"/"share"
    p=base/APP_NAME; p.mkdir(parents=True,exist_ok=True); return p

class Store:
    def __init__(self, path: str|Path|None=None):
        self.path=Path(path) if path else app_data_dir()/"academic_chat_manager.sqlite3"
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self._initialize()
    @contextmanager
    def db(self) -> Iterator[sqlite3.Connection]:
        c=sqlite3.connect(self.path,timeout=30); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA busy_timeout=30000")
        try:
            yield c; c.commit()
        except Exception: c.rollback(); raise
        finally:c.close()
    def _initialize(self):
        with self.db() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript('''
            CREATE TABLE IF NOT EXISTS chats(peer_id INTEGER PRIMARY KEY, access_hash INTEGER, title TEXT NOT NULL, kind TEXT NOT NULL, username TEXT, can_send INTEGER NOT NULL DEFAULT 0, unread_count INTEGER NOT NULL DEFAULT 0, last_message TEXT, last_message_at TEXT, hidden INTEGER NOT NULL DEFAULT 0, available INTEGER NOT NULL DEFAULT 1, synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS collections(id INTEGER PRIMARY KEY AUTOINCREMENT, parent_id INTEGER REFERENCES collections(id) ON DELETE CASCADE, name TEXT NOT NULL, color TEXT NOT NULL DEFAULT '#A90025', icon TEXT NOT NULL DEFAULT '📁', sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS collection_chats(collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE, peer_id INTEGER NOT NULL REFERENCES chats(peer_id) ON DELETE CASCADE, sort_order INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(collection_id,peer_id));
            CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS send_jobs(id TEXT PRIMARY KEY, collection_id INTEGER, message TEXT NOT NULL, files_json TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT);
            CREATE TABLE IF NOT EXISTS send_job_collections(job_id TEXT NOT NULL REFERENCES send_jobs(id) ON DELETE CASCADE, collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE, PRIMARY KEY(job_id,collection_id));
            CREATE TABLE IF NOT EXISTS send_targets(id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES send_jobs(id) ON DELETE CASCADE, peer_id INTEGER NOT NULL, peer_title TEXT NOT NULL, status TEXT NOT NULL, error TEXT, telegram_message_id INTEGER, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(job_id,peer_id));
            CREATE TABLE IF NOT EXISTS cached_messages(peer_id INTEGER NOT NULL, message_id INTEGER NOT NULL, sender_id INTEGER, sender_name TEXT, text TEXT NOT NULL DEFAULT '', date TEXT, outgoing INTEGER NOT NULL DEFAULT 0, media_json TEXT, reactions_json TEXT, reply_json TEXT, PRIMARY KEY(peer_id,message_id));
            CREATE INDEX IF NOT EXISTS idx_messages_peer_date ON cached_messages(peer_id,date DESC);
            ''')
            columns={r[1] for r in c.execute("PRAGMA table_info(chats)")}
            if "available" not in columns:c.execute("ALTER TABLE chats ADD COLUMN available INTEGER NOT NULL DEFAULT 1")
            message_columns={r[1] for r in c.execute("PRAGMA table_info(cached_messages)")}
            if "reactions_json" not in message_columns:c.execute("ALTER TABLE cached_messages ADD COLUMN reactions_json TEXT")
            if "reply_json" not in message_columns:c.execute("ALTER TABLE cached_messages ADD COLUMN reply_json TEXT")
            # Older databases may retain send jobs after their collection was deleted.
            # Only backfill memberships whose collection still exists, otherwise the
            # foreign key on send_job_collections prevents the app from starting.
            c.execute("""INSERT OR IGNORE INTO send_job_collections(job_id,collection_id)
                         SELECT j.id,j.collection_id FROM send_jobs j
                         JOIN collections col ON col.id=j.collection_id
                         WHERE j.collection_id IS NOT NULL""")
    # Chat cache
    def upsert_chats(self, rows, complete_sync=False):
        with self.db() as c:
            if complete_sync:c.execute("UPDATE chats SET available=0")
            c.executemany('''INSERT INTO chats(peer_id,access_hash,title,kind,username,can_send,unread_count,last_message,last_message_at,available,synced_at) VALUES(:peer_id,:access_hash,:title,:kind,:username,:can_send,:unread_count,:last_message,:last_message_at,1,CURRENT_TIMESTAMP) ON CONFLICT(peer_id) DO UPDATE SET access_hash=excluded.access_hash,title=excluded.title,kind=excluded.kind,username=excluded.username,can_send=excluded.can_send,unread_count=excluded.unread_count,last_message=excluded.last_message,last_message_at=excluded.last_message_at,available=1,synced_at=CURRENT_TIMESTAMP''',rows)
    def chats(self, query="", kind=None, include_hidden=False):
        sql="SELECT * FROM chats WHERE available=1 AND (? OR hidden=0) AND (? IS NULL OR kind=?) AND (title LIKE ? OR COALESCE(last_message,'') LIKE ?) ORDER BY COALESCE(last_message_at,'') DESC,title COLLATE NOCASE"
        with self.db() as c:return [dict(r) for r in c.execute(sql,(include_hidden,kind,kind,f"%{query}%",f"%{query}%"))]
    def chat(self,peer_id):
        with self.db() as c:r=c.execute("SELECT * FROM chats WHERE peer_id=?",(peer_id,)).fetchone(); return dict(r) if r else None
    def update_last_message(self,peer_id,text,date,incoming=False):
        with self.db() as c:c.execute("UPDATE chats SET last_message=?,last_message_at=?,unread_count=unread_count+? WHERE peer_id=?",(text,date,int(bool(incoming)),peer_id))
    def clear_unread(self,peer_id):
        with self.db() as c:c.execute("UPDATE chats SET unread_count=0 WHERE peer_id=?",(peer_id,))
    def is_in_any_collection(self,peer_id):
        with self.db() as c:return bool(c.execute("SELECT 1 FROM collection_chats WHERE peer_id=? LIMIT 1",(peer_id,)).fetchone())
    def clear_telegram_data(self):
        """Clear account-bound dialogs/messages and memberships, keeping empty folders and audit history."""
        with self.db() as c:c.execute("DELETE FROM cached_messages");c.execute("DELETE FROM chats")
    def set_hidden(self, peer_ids, hidden=True):
        with self.db() as c:c.executemany("UPDATE chats SET hidden=? WHERE peer_id=?",[(int(hidden),int(x)) for x in peer_ids])
    # Collections and cycle-safe tree mutations
    def collections(self):
        with self.db() as c:return [dict(r) for r in c.execute("SELECT c.*, (SELECT COUNT(*) FROM collection_chats cc WHERE cc.collection_id=c.id) chat_count FROM collections c ORDER BY COALESCE(parent_id,0),sort_order,name COLLATE NOCASE")]
    def create_collection(self,name,parent_id=None,color="#A90025",icon="📁"):
        name=name.strip()
        if not name: raise ValueError("Klasör adı boş olamaz")
        with self.db() as c:
            cur=c.execute("INSERT INTO collections(parent_id,name,color,icon) VALUES(?,?,?,?)",(parent_id,name,color,icon));return cur.lastrowid
    def rename_collection(self,cid,name):
        name=name.strip()
        if not name:raise ValueError("Klasör adı boş olamaz")
        with self.db() as c:c.execute("UPDATE collections SET name=? WHERE id=?",(name,cid))
    def move_collection(self,cid,parent_id):
        if parent_id==cid: raise ValueError("Klasör kendisinin altına taşınamaz")
        with self.db() as c:
            if not c.execute("SELECT 1 FROM collections WHERE id=?",(cid,)).fetchone():raise KeyError(cid)
            if parent_id is not None and not c.execute("SELECT 1 FROM collections WHERE id=?",(parent_id,)).fetchone():raise KeyError(parent_id)
            if parent_id is not None:
                q="""WITH RECURSIVE descendants(id) AS (SELECT id FROM collections WHERE parent_id=? UNION ALL SELECT c.id FROM collections c JOIN descendants d ON c.parent_id=d.id) SELECT 1 FROM descendants WHERE id=?"""
                if c.execute(q,(cid,parent_id)).fetchone():raise ValueError("Döngüsel klasör yapısına izin verilmiyor")
            c.execute("UPDATE collections SET parent_id=? WHERE id=?",(parent_id,cid))
    def reorder_collection(self,cid,direction):
        if direction not in (-1,1):raise ValueError("Direction must be -1 or 1")
        with self.db() as c:
            row=c.execute("SELECT id,parent_id,sort_order FROM collections WHERE id=?",(cid,)).fetchone()
            if not row:raise KeyError(cid)
            siblings=list(c.execute("SELECT id,sort_order FROM collections WHERE parent_id IS ? ORDER BY sort_order,id",(row['parent_id'],)))
            index=next(i for i,x in enumerate(siblings) if x['id']==cid);other=index+direction
            if not 0<=other<len(siblings):return False
            for position,sibling in enumerate(siblings):c.execute("UPDATE collections SET sort_order=? WHERE id=?",(position,sibling['id']))
            c.execute("UPDATE collections SET sort_order=? WHERE id=?",(other,cid));c.execute("UPDATE collections SET sort_order=? WHERE id=?",(index,siblings[other]['id']));return True
    def delete_collection(self,cid):
        with self.db() as c:c.execute("DELETE FROM collections WHERE id=?",(cid,))
    def add_chats_to_collection(self,cid,peer_ids):
        with self.db() as c:
            c.executemany("INSERT OR IGNORE INTO collection_chats(collection_id,peer_id) VALUES(?,?)",[(cid,int(p)) for p in peer_ids])
    def remove_chat_from_collection(self,cid,peer_id):
        with self.db() as c:c.execute("DELETE FROM collection_chats WHERE collection_id=? AND peer_id=?",(cid,peer_id))
    def collection_chats(self,cid,include_descendants=True):
        with self.db() as c:
            if include_descendants:
                q="""WITH RECURSIVE tree(id) AS (SELECT id FROM collections WHERE id=? UNION ALL SELECT c.id FROM collections c JOIN tree t ON c.parent_id=t.id) SELECT DISTINCT ch.* FROM chats ch JOIN collection_chats cc ON cc.peer_id=ch.peer_id JOIN tree t ON t.id=cc.collection_id WHERE ch.hidden=0 AND ch.available=1 ORDER BY ch.title COLLATE NOCASE"""
                return [dict(r) for r in c.execute(q,(cid,))]
            return [dict(r) for r in c.execute("SELECT ch.* FROM chats ch JOIN collection_chats cc ON cc.peer_id=ch.peer_id WHERE cc.collection_id=? AND ch.hidden=0 AND ch.available=1 ORDER BY ch.title COLLATE NOCASE",(cid,))]
    def collection_path(self,cid):
        allc={r['id']:r for r in self.collections()}; out=[]; cur=allc.get(cid)
        while cur:out.append(cur['name']);cur=allc.get(cur['parent_id'])
        return list(reversed(out))
    def collection_path_ids(self,cid):
        allc={int(r['id']):r for r in self.collections()};out=[];cur=allc.get(int(cid))
        while cur:out.append(int(cur['id']));cur=allc.get(cur['parent_id'])
        return list(reversed(out))
    def chat_collection_ids(self,peer_id):
        with self.db() as c:return [int(r[0]) for r in c.execute("SELECT collection_id FROM collection_chats WHERE peer_id=? ORDER BY collection_id",(int(peer_id),))]
    def chat_collection_paths(self,peer_id):
        ids=self.chat_collection_ids(peer_id)
        paths=[" › ".join(self.collection_path(cid)) for cid in ids]
        return [p for p in paths if p]
    # Preferences and message cache
    def preference(self,key,default=None):
        with self.db() as c:r=c.execute("SELECT value FROM preferences WHERE key=?",(key,)).fetchone(); return json.loads(r[0]) if r else default
    def set_preference(self,key,value):
        with self.db() as c:c.execute("INSERT INTO preferences(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,json.dumps(value,ensure_ascii=False)))
    def cache_messages(self,rows):
        normalized=[{**row,"reactions_json":row.get("reactions_json"),"reply_json":row.get("reply_json")} for row in rows]
        with self.db() as c:c.executemany("INSERT OR REPLACE INTO cached_messages(peer_id,message_id,sender_id,sender_name,text,date,outgoing,media_json,reactions_json,reply_json) VALUES(:peer_id,:message_id,:sender_id,:sender_name,:text,:date,:outgoing,:media_json,:reactions_json,:reply_json)",normalized)
    def messages(self,peer_id,limit=100,before_id=None):
        with self.db() as c:
            if before_id is None: rows=c.execute("SELECT * FROM cached_messages WHERE peer_id=? ORDER BY message_id DESC LIMIT ?",(peer_id,limit)).fetchall()
            else: rows=c.execute("SELECT * FROM cached_messages WHERE peer_id=? AND message_id<? ORDER BY message_id DESC LIMIT ?",(peer_id,before_id,limit)).fetchall()
            return [dict(r) for r in reversed(rows)]
    # Durable bulk send queue
    def create_job(self,job_id,collection_id,message,files,targets,collection_ids=None):
        with self.db() as c:
            c.execute("INSERT INTO send_jobs(id,collection_id,message,files_json,status) VALUES(?,?,?,?,?)",(job_id,collection_id,message,json.dumps(files),"queued"))
            linked=sorted({int(x) for x in (collection_ids if collection_ids is not None else ([collection_id] if collection_id is not None else []))})
            c.executemany("INSERT OR IGNORE INTO send_job_collections(job_id,collection_id) VALUES(?,?)",[(job_id,cid) for cid in linked])
            c.executemany("INSERT INTO send_targets(job_id,peer_id,peer_title,status) VALUES(?,?,?,?)",[(job_id,t['peer_id'],t['title'],"pending") for t in targets])
    def update_target(self,job_id,peer_id,status,error=None,message_id=None):
        with self.db() as c:c.execute("UPDATE send_targets SET status=?,error=?,telegram_message_id=?,updated_at=CURRENT_TIMESTAMP WHERE job_id=? AND peer_id=?",(status,error,message_id,job_id,peer_id))
    def cancel_job(self,job_id):
        with self.db() as c:
            cur=c.execute("UPDATE send_targets SET status='cancelled',error='Kullanıcı tarafından iptal edildi',updated_at=CURRENT_TIMESTAMP WHERE job_id=? AND status='pending'",(job_id,));cancelled=cur.rowcount
            sending=c.execute("SELECT 1 FROM send_targets WHERE job_id=? AND status='sending' LIMIT 1",(job_id,)).fetchone()
            c.execute("UPDATE send_jobs SET status=?,finished_at=CASE WHEN ?=0 THEN CURRENT_TIMESTAMP ELSE finished_at END WHERE id=?",("cancelling" if sending else "cancelled",int(bool(sending)),job_id))
            return cancelled>0
    def cancel_target(self,job_id,peer_id):
        with self.db() as c:
            cur=c.execute("UPDATE send_targets SET status='cancelled',error='Kullanıcı tarafından iptal edildi',updated_at=CURRENT_TIMESTAMP WHERE job_id=? AND peer_id=? AND status='pending'",(job_id,int(peer_id)))
            if cur.rowcount:c.execute("UPDATE send_jobs SET status='partial' WHERE id=? AND status='queued'",(job_id,))
            return cur.rowcount>0
    def set_job_status(self,job_id,status):
        with self.db() as c:c.execute("UPDATE send_jobs SET status=?,finished_at=CASE WHEN ? IN ('queued','running','cancelling') THEN NULL ELSE COALESCE(finished_at,CURRENT_TIMESTAMP) END WHERE id=?",(status,status,job_id))
    def finish_job(self,job_id,status="finished"):
        with self.db() as c:c.execute("UPDATE send_jobs SET status=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",(status,job_id))
    def jobs(self):
        with self.db() as c:return [dict(r) for r in c.execute("SELECT j.*,COUNT(t.id) total,SUM(t.status='sent') sent,SUM(t.status='failed') failed FROM send_jobs j LEFT JOIN send_targets t ON t.job_id=j.id GROUP BY j.id ORDER BY j.created_at DESC")]
    def job_collection_ids(self,job_id):
        with self.db() as c:return [int(r[0]) for r in c.execute("SELECT collection_id FROM send_job_collections WHERE job_id=? ORDER BY collection_id",(job_id,))]
    def collection_messages(self,collection_ids,limit=100):
        ids=sorted({int(x) for x in collection_ids})
        if not ids:return []
        marks=','.join('?' for _ in ids)
        with self.db() as c:
            q=f"""SELECT DISTINCT j.*,COALESCE(t.total,0) AS total,COALESCE(t.sent,0) AS sent,COALESCE(t.failed,0) AS failed
                  FROM send_jobs j JOIN send_job_collections jc ON jc.job_id=j.id
                  LEFT JOIN (SELECT job_id,COUNT(*) total,SUM(status='sent') sent,SUM(status IN ('failed','flood_wait')) failed FROM send_targets GROUP BY job_id) t ON t.job_id=j.id
                  WHERE jc.collection_id IN ({marks}) ORDER BY j.created_at DESC,j.id DESC LIMIT ?"""
            return [dict(r) for r in c.execute(q,(*ids,int(limit)))]
    def job_targets(self,job_id):
        with self.db() as c:return [dict(r) for r in c.execute("SELECT * FROM send_targets WHERE job_id=? ORDER BY id",(job_id,))]
