"""Phase 10A canonical written-content, mail, board, and readable foundations."""
from __future__ import annotations
import hashlib, json, re, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFE_ID_RE=re.compile(r"^[A-Za-z0-9_.:-]+$")
DOCUMENT_TYPES={"letter","note","book","journal","notice","board_post","board_reply","newspaper_placeholder","sign","plaque","scroll","ledger","record","contract_placeholder","system_message","custom"}
DOCUMENT_STATUSES={"draft","sealed","sent","in_transit_placeholder","delivered","published","archived","deleted","expired","retracted","moderated","custom"}
MAIL_STATUSES={"queued","sent","delivered","read","archived","deleted","failed","returned","expired"}
ATTACHMENT_STATUSES={"reserved","attached","delivered","claimed","returned","failed","cancelled"}
BOARD_STATUSES={"published","hidden","removed","locked","archived","expired"}
WRITTEN_COLLECTIONS=["written_document_definitions","written_content_profiles","written_content_pages","written_access_profiles","written_retention_profiles","written_render_profiles","written_sanitization_profiles","mail_service_profiles","bulletin_board_definitions","bulletin_posting_profiles","written_moderation_profiles","written_message_profiles","readable_item_profiles","journal_profiles","book_profiles"]

def utc_now(): return datetime.now(timezone.utc).isoformat()
def jdump(v): return json.dumps(v if v is not None else {}, sort_keys=True, ensure_ascii=False)
def jload(v,d=None):
    try: return json.loads(v) if v else ({} if d is None else d)
    except Exception: return {} if d is None else d
def stable_id(prefix,*parts):
    raw="|".join(json.dumps(p,sort_keys=True,default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:32]}"
def content_hash(title,subject,body,pages=None): return hashlib.sha256(jdump({"title":title,"subject":subject,"body":body,"pages":pages or []}).encode()).hexdigest()

SCHEMA_SQL="""
CREATE TABLE IF NOT EXISTS written_document_instances(document_instance_id TEXT PRIMARY KEY,world_id TEXT,definition_id TEXT,document_type TEXT,title TEXT,subject TEXT,author_type TEXT,author_id TEXT,author_display_snapshot TEXT,owner_type TEXT,owner_id TEXT,parent_document_id TEXT,thread_root_id TEXT,content_version_id TEXT,status TEXT,created_world_time INTEGER,updated_world_time INTEGER,published_world_time INTEGER,expires_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS written_document_versions(content_version_id TEXT PRIMARY KEY,document_instance_id TEXT,version_number INTEGER,title TEXT,subject TEXT,body_text TEXT,page_data_json TEXT,editor_actor_id TEXT,edit_reason TEXT,created_world_time INTEGER,created_at TEXT,content_hash TEXT,metadata_json TEXT,UNIQUE(document_instance_id,version_number));
CREATE TABLE IF NOT EXISTS mailboxes(mailbox_id TEXT PRIMARY KEY,world_id TEXT,owner_type TEXT,owner_id TEXT,mailbox_type TEXT,name TEXT,status TEXT,capacity INTEGER,unread_count_cache INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(world_id,owner_type,owner_id,mailbox_type));
CREATE TABLE IF NOT EXISTS mail_deliveries(mail_delivery_id TEXT PRIMARY KEY,world_id TEXT,document_instance_id TEXT,sender_type TEXT,sender_id TEXT,recipient_type TEXT,recipient_id TEXT,recipient_mailbox_id TEXT,status TEXT,delivery_attempt INTEGER,sent_world_time INTEGER,delivered_world_time INTEGER,read_world_time INTEGER,archived_world_time INTEGER,deleted_world_time INTEGER,failure_reason TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(world_id,document_instance_id,recipient_type,recipient_id));
CREATE TABLE IF NOT EXISTS written_document_attachments(attachment_id TEXT PRIMARY KEY,document_instance_id TEXT,attachment_type TEXT,item_instance_id TEXT,currency_id_placeholder TEXT,amount_placeholder INTEGER,status TEXT,original_owner_type TEXT,original_owner_id TEXT,recipient_delivery_id TEXT,claimed_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(document_instance_id,item_instance_id));
CREATE TABLE IF NOT EXISTS bulletin_board_publications(publication_id TEXT PRIMARY KEY,board_id TEXT,document_instance_id TEXT,thread_root_id TEXT,parent_document_id TEXT,sequence_number INTEGER,pinned INTEGER,locked INTEGER,status TEXT,published_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(board_id,document_instance_id));
CREATE TABLE IF NOT EXISTS written_moderation_events(moderation_event_id TEXT PRIMARY KEY,document_instance_id TEXT,board_id TEXT,moderator_actor_id TEXT,operation TEXT,reason TEXT,old_status TEXT,new_status TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS written_document_read_state(read_state_id TEXT PRIMARY KEY,actor_id TEXT,document_instance_id TEXT,delivery_id TEXT,board_id TEXT,first_read_world_time INTEGER,last_read_world_time INTEGER,read_count INTEGER,last_page_read INTEGER,completed INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS written_content_audit_events(audit_event_id TEXT PRIMARY KEY,document_instance_id TEXT,actor_id TEXT,operation TEXT,target_type TEXT,target_id TEXT,old_value_json TEXT,new_value_json TEXT,reason TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_written_read_state_unique ON written_document_read_state(actor_id,document_instance_id,delivery_id,board_id);
CREATE TABLE IF NOT EXISTS written_composition_sessions(composition_session_id TEXT PRIMARY KEY,actor_id TEXT,document_instance_id TEXT,mode TEXT,status TEXT,started_world_time INTEGER,last_updated_world_time INTEGER,expires_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
"""

def init_written_content_schema(db_path):
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(db_path) as con: con.executescript(SCHEMA_SQL)

class WrittenContentData:
    collections=WRITTEN_COLLECTIONS
    def __init__(self, world_root="worlds/shattered_realms"):
        self.world_root=Path(world_root); self.data={c:self._load(c) for c in self.collections}
    def _load(self,c):
        for p in (self.world_root/c/f"{c}.json", self.world_root/"builder"/f"{c}.json"):
            if p.exists():
                raw=json.loads(p.read_text()); items=raw.get(c,raw) if isinstance(raw,dict) else raw
                if isinstance(items,list): return {str(x.get("id")):x for x in items if isinstance(x,dict) and x.get("id")}
                if isinstance(items,dict): return {str(k):(v|{"id":v.get("id",k)} if isinstance(v,dict) else {"id":k}) for k,v in items.items()}
        return {}
    def get(self,c,i): return self.data.get(c,{}).get(str(i or ""))
    def validate(self):
        errors=[]; warnings=[]
        for did,d in self.data["written_document_definitions"].items():
            if not SAFE_ID_RE.fullmatch(did): errors.append(f"document {did} unsafe id")
            if d.get("document_type","custom") not in DOCUMENT_TYPES: errors.append(f"document {did} unsupported type")
            if d.get("content_profile_id") and d["content_profile_id"] not in self.data["written_content_profiles"]: errors.append(f"document {did} missing content profile")
            if d.get("immutable") and d.get("editable"): warnings.append(f"immutable document {did} allows editing")
        for pid,p in self.data["written_content_profiles"].items():
            if p.get("format","plain_text") not in {"plain_text","mud_markup","restricted_markdown_placeholder","custom"}: errors.append(f"content {pid} unsafe format")
        return {"errors":errors,"warnings":warnings}

class WrittenContentService:
    def __init__(self, db_path, world_id="shattered_realms", world_root=None, event_bus=None, economy_service=None, organization_service=None, faction_service=None, runtime=None):
        self.db_path=Path(db_path); self.world_id=world_id; self.event_bus=event_bus; self.economy_service=economy_service; self.organization_service=organization_service; self.faction_service=faction_service; self.runtime=runtime; init_written_content_schema(self.db_path); self.content=WrittenContentData(world_root or f"worlds/{world_id}")
    def publish(self,event,payload):
        if self.event_bus and hasattr(self.event_bus,"publish"):
            try: self.event_bus.publish(event,payload,source_system="written_content")
            except TypeError: self.event_bus.publish(event,payload)
    def sanitize_text(self,text,maximum_characters=8000,maximum_lines=200):
        text=str(text or "").replace("\r\n","\n").replace("\r","\n")
        if "\x1b" in text or any((ord(ch)<32 and ch not in "\n\t") for ch in text): raise ValueError("unsafe control sequence")
        lines=text.split("\n")
        if len(lines)>maximum_lines: raise ValueError("too many lines")
        if len(text)>maximum_characters: raise ValueError("content too long")
        return text
    def _audit(self,con,doc,actor,op,target_type="document",target_id="",old=None,new=None,reason="",world_time=0):
        con.execute("INSERT INTO written_content_audit_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(stable_id("waudit",doc,actor,op,target_id,utc_now(),uuid.uuid4().hex),doc,actor,op,target_type,target_id,jdump(old),jdump(new),reason,world_time,utc_now(),jdump({})))
    def create_document(self, author_actor_id, title="", subject="", body="", document_type="note", definition_id="", owner_type="actor", owner_id="", status="draft", pages=None, immutable=False, metadata=None, world_time=0):
        if document_type not in DOCUMENT_TYPES: raise ValueError("unsupported document type")
        body=self.sanitize_text(body); title=self.sanitize_text(title,512,4); subject=self.sanitize_text(subject,512,4); now=utc_now(); doc=stable_id("doc",self.world_id,author_actor_id,title,subject,body,uuid.uuid4().hex); ver=stable_id("dver",doc,1,content_hash(title,subject,body,pages))
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT INTO written_document_instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(doc,self.world_id,definition_id,document_type,title,subject,"actor",author_actor_id,author_actor_id,owner_type,owner_id or author_actor_id,"","",ver,status,world_time,world_time,world_time if status=="published" else None,None,now,now,jdump({**(metadata or {}),"immutable":bool(immutable)})))
            con.execute("INSERT INTO written_document_versions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(ver,doc,1,title,subject,body,jdump(pages or []),author_actor_id,"initial",world_time,now,content_hash(title,subject,body,pages),jdump({})))
            self._audit(con,doc,author_actor_id,"document_created",new={"status":status},world_time=world_time)
        self.publish("document_created",{"document_instance_id":doc,"actor_id":author_actor_id}); return doc
    def edit_document(self, actor_id, document_instance_id, title=None, subject=None, body=None, pages=None, reason="edit", world_time=0):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; inst=con.execute("SELECT * FROM written_document_instances WHERE document_instance_id=?",(document_instance_id,)).fetchone()
            if not inst: raise ValueError("unknown document")
            meta=jload(inst["metadata_json"]); 
            if meta.get("immutable") or inst["status"] in {"sent","sealed","delivered"}: raise ValueError("document is immutable")
            last=con.execute("SELECT * FROM written_document_versions WHERE document_instance_id=? ORDER BY version_number DESC LIMIT 1",(document_instance_id,)).fetchone(); n=int(last["version_number"])+1
            t=self.sanitize_text(title if title is not None else last["title"],512,4); s=self.sanitize_text(subject if subject is not None else last["subject"],512,4); b=self.sanitize_text(body if body is not None else last["body_text"]); pg=pages if pages is not None else jload(last["page_data_json"],[]); ver=stable_id("dver",document_instance_id,n,content_hash(t,s,b,pg))
            con.execute("INSERT INTO written_document_versions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(ver,document_instance_id,n,t,s,b,jdump(pg),actor_id,reason,world_time,utc_now(),content_hash(t,s,b,pg),jdump({})))
            con.execute("UPDATE written_document_instances SET title=?,subject=?,content_version_id=?,updated_world_time=?,updated_at=? WHERE document_instance_id=?",(t,s,ver,world_time,utc_now(),document_instance_id))
            self._audit(con,document_instance_id,actor_id,"document_edited",old=dict(last),new={"version":n},reason=reason,world_time=world_time)
        self.publish("document_edited",{"document_instance_id":document_instance_id,"version_number":n}); return ver
    def copy_document(self, actor_id, document_instance_id, owner_type="actor", owner_id="", world_time=0):
        d=self.get_document(document_instance_id); return self.create_document(actor_id,d["title"],d["subject"],d["body_text"],d["document_type"],d.get("definition_id",""),owner_type,owner_id or actor_id,"draft",jload(d.get("page_data_json"),[]),False,{"provenance_document_id":document_instance_id},world_time)
    def get_document(self, document_instance_id):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; r=con.execute("SELECT i.*,v.body_text,v.page_data_json,v.version_number,v.content_hash FROM written_document_instances i LEFT JOIN written_document_versions v ON i.content_version_id=v.content_version_id WHERE i.document_instance_id=?",(document_instance_id,)).fetchone(); return dict(r) if r else None
    def get_or_create_mailbox(self, owner_type, owner_id, mailbox_type="personal", name=""):
        mid=stable_id("mailbox",self.world_id,owner_type,owner_id,mailbox_type); now=utc_now()
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO mailboxes VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(mid,self.world_id,owner_type,owner_id,mailbox_type,name or f"{owner_id} mailbox","active",1000,0,now,now,jdump({})))
        return mid
    def get_mailbox(self,owner_type,owner_id,mailbox_type="personal"):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM mailboxes WHERE world_id=? AND owner_type=? AND owner_id=? AND mailbox_type=?",(self.world_id,owner_type,owner_id,mailbox_type)).fetchone(); return dict(r) if r else None
    def compose_mail(self, author_actor_id, recipients, subject, body): return self.create_document(author_actor_id,subject,subject,body,"letter",owner_type="actor",owner_id=author_actor_id,status="draft",metadata={"recipients":recipients})
    def send_mail(self, author_actor_id, document_instance_id, recipients=None, service_profile_id="guildlands_post", world_time=0):
        recips=recipients or jload(self.get_document(document_instance_id)["metadata_json"]).get("recipients",[]); now=utc_now(); out=[]
        if isinstance(recips,(str,bytes)): recips=[{"type":"actor","id":str(recips)}]
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; inst=con.execute("SELECT * FROM written_document_instances WHERE document_instance_id=?",(document_instance_id,)).fetchone()
            if not inst: raise ValueError("unknown document")
            if inst["status"]=="draft": con.execute("UPDATE written_document_instances SET status='sent',updated_world_time=?,updated_at=? WHERE document_instance_id=?",(world_time,now,document_instance_id)); self._audit(con,document_instance_id,author_actor_id,"mail_sent",world_time=world_time)
            for r in recips:
                rt=(r.get("type") or r.get("recipient_type") or "actor") if isinstance(r,dict) else "actor"; rid=(r.get("id") or r.get("recipient_id")) if isinstance(r,dict) else str(r)
                mb=stable_id("mailbox",self.world_id,rt,rid,"personal")
                con.execute("INSERT OR IGNORE INTO mailboxes VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(mb,self.world_id,rt,rid,"personal",f"{rid} mailbox","active",1000,0,now,now,jdump({})))
                did=stable_id("mdel",self.world_id,document_instance_id,rt,rid)
                con.execute("INSERT OR IGNORE INTO mail_deliveries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(did,self.world_id,document_instance_id,"actor",author_actor_id,rt,rid,mb,"delivered",1,world_time,world_time,None,None,None,"",now,now,jdump({"service_profile_id":service_profile_id})))
                out.append(did)
            con.execute("UPDATE mailboxes SET unread_count_cache=(SELECT COUNT(*) FROM mail_deliveries WHERE recipient_mailbox_id=mailboxes.mailbox_id AND status='delivered')")
        self.publish("mail_sent",{"document_instance_id":document_instance_id,"deliveries":out}); self.publish("mail_delivered",{"document_instance_id":document_instance_id}); return out
    def list_mail(self, mailbox_id, status=None, limit=None):
        q="SELECT * FROM mail_deliveries WHERE recipient_mailbox_id=?"; p=[mailbox_id]
        if status: q+=" AND status=?"; p.append(status)
        q+=" ORDER BY created_at DESC" + (" LIMIT ?" if limit else "");
        if limit: p.append(int(limit))
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute(q,p)]
    def mark_mail_read(self, actor_id, mail_delivery_id, page=0, completed=True, world_time=0):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; d=con.execute("SELECT * FROM mail_deliveries WHERE mail_delivery_id=?",(mail_delivery_id,)).fetchone();
            if not d: raise ValueError("unknown delivery")
            if d["recipient_id"]!=actor_id and d["recipient_type"]=="actor": raise PermissionError("not recipient")
            first=d["status"]!="read"; con.execute("UPDATE mail_deliveries SET status='read',read_world_time=COALESCE(read_world_time,?),updated_at=? WHERE mail_delivery_id=?",(world_time,utc_now(),mail_delivery_id))
            rs=stable_id("rs",actor_id,d["document_instance_id"],mail_delivery_id,""); now=utc_now()
            con.execute("INSERT INTO written_document_read_state VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(actor_id,document_instance_id,delivery_id,board_id) DO UPDATE SET last_read_world_time=excluded.last_read_world_time,read_count=read_count+1,last_page_read=MAX(last_page_read,excluded.last_page_read),completed=MAX(completed,excluded.completed),updated_at=excluded.updated_at",(rs,actor_id,d["document_instance_id"],mail_delivery_id,"",world_time,world_time,1,int(page or 0),1 if completed else 0,now,now,jdump({})))
            con.execute("UPDATE mailboxes SET unread_count_cache=(SELECT COUNT(*) FROM mail_deliveries WHERE recipient_mailbox_id=? AND status='delivered') WHERE mailbox_id=?",(d["recipient_mailbox_id"],d["recipient_mailbox_id"]))
            if first: self._audit(con,d["document_instance_id"],actor_id,"mail_read","delivery",mail_delivery_id,world_time=world_time)
        if first: self.publish("mail_read",{"mail_delivery_id":mail_delivery_id,"actor_id":actor_id})
        return True
    def record_read(self, actor_id, document_instance_id, delivery_id="", board_id="", page=0, completed=False, world_time=0):
        rs=stable_id("rs",actor_id,document_instance_id,delivery_id or "",board_id or ""); now=utc_now()
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT INTO written_document_read_state VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(actor_id,document_instance_id,delivery_id,board_id) DO UPDATE SET last_read_world_time=excluded.last_read_world_time,read_count=read_count+1,last_page_read=MAX(last_page_read,excluded.last_page_read),completed=MAX(completed,excluded.completed),updated_at=excluded.updated_at",(rs,actor_id,document_instance_id,delivery_id,board_id,world_time,world_time,1,int(page or 0),1 if completed else 0,now,now,jdump({})))
        self.publish("document_read",{"actor_id":actor_id,"document_instance_id":document_instance_id});
        if completed: self.publish("document_read_completed",{"actor_id":actor_id,"document_instance_id":document_instance_id})
        return rs
    def archive_mail(self,actor_id,mail_delivery_id): return self._delivery_status(actor_id,mail_delivery_id,"archived","mail_archived")
    def delete_mail(self,actor_id,mail_delivery_id): return self._delivery_status(actor_id,mail_delivery_id,"deleted","mail_deleted")
    def restore_mail(self,actor_id,mail_delivery_id): return self._delivery_status(actor_id,mail_delivery_id,"delivered","mail_restored")
    def _delivery_status(self,actor_id,did,status,event):
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE mail_deliveries SET status=?,updated_at=? WHERE mail_delivery_id=?",(status,utc_now(),did))
        self.publish(event,{"mail_delivery_id":did,"actor_id":actor_id}); return True
    def reply_to_mail(self,author_actor_id,mail_delivery_id,body):
        m=self.trace_mail(mail_delivery_id); return self.compose_mail(author_actor_id,[{"type":m["delivery"]["sender_type"],"id":m["delivery"]["sender_id"]}],"Re: "+m["document"].get("subject",""),body)
    def forward_mail(self,author_actor_id,mail_delivery_id,recipients,note=None):
        m=self.trace_mail(mail_delivery_id); return self.compose_mail(author_actor_id,recipients,"Fwd: "+m["document"].get("subject",""),(note or "")+"\n"+m["document"].get("body_text",""))
    def trace_mail(self,mail_delivery_id):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; d=con.execute("SELECT * FROM mail_deliveries WHERE mail_delivery_id=?",(mail_delivery_id,)).fetchone(); return {"delivery":dict(d) if d else None,"document":self.get_document(d["document_instance_id"]) if d else None}
    def add_item_attachment(self, actor_id, document_instance_id, item_instance_id):
        aid=stable_id("att",document_instance_id,item_instance_id); now=utc_now()
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO written_document_attachments VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,document_instance_id,"item",item_instance_id,"",0,"attached","actor",actor_id,"",None,now,now,jdump({"reserved":True}))); self._audit(con,document_instance_id,actor_id,"attachment_added","item_instance",item_instance_id)
        self.publish("mail_attachment_added",{"attachment_id":aid}); return aid
    def claim_attachment(self, actor_id, attachment_id, delivery_id):
        with sqlite3.connect(self.db_path) as con:
            r=con.execute("SELECT status,document_instance_id FROM written_document_attachments WHERE attachment_id=?",(attachment_id,)).fetchone()
            if not r: raise ValueError("unknown attachment")
            if r[0]=="claimed": return False
            con.execute("UPDATE written_document_attachments SET status='claimed',recipient_delivery_id=?,claimed_world_time=COALESCE(claimed_world_time,0),updated_at=? WHERE attachment_id=? AND status!='claimed'",(delivery_id,utc_now(),attachment_id)); self._audit(con,r[1],actor_id,"attachment_claimed","attachment",attachment_id)
        self.publish("mail_attachment_claimed",{"attachment_id":attachment_id,"actor_id":actor_id}); return True
    def post_board_message(self, actor_id, board_id, subject, body, parent_document_id="", world_time=0):
        dtype="board_reply" if parent_document_id else "board_post"; doc=self.create_document(actor_id,subject,subject,body,dtype,owner_type="board",owner_id=board_id,status="published",world_time=world_time)
        with sqlite3.connect(self.db_path) as con:
            root=parent_document_id or doc
            if parent_document_id:
                rr=con.execute("SELECT thread_root_id FROM bulletin_board_publications WHERE document_instance_id=?",(parent_document_id,)).fetchone(); root=rr[0] if rr else parent_document_id
            seq=(con.execute("SELECT COALESCE(MAX(sequence_number),0)+1 FROM bulletin_board_publications WHERE board_id=? AND thread_root_id=?",(board_id,root)).fetchone()[0]); pub=stable_id("bpub",board_id,doc)
            con.execute("INSERT INTO bulletin_board_publications VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(pub,board_id,doc,root,parent_document_id,int(seq),0,0,"published",world_time,utc_now(),utc_now(),jdump({})))
            con.execute("UPDATE written_document_instances SET thread_root_id=?,parent_document_id=? WHERE document_instance_id=?",(root,parent_document_id,doc))
        self.publish("board_reply_created" if parent_document_id else "board_post_created",{"board_id":board_id,"document_instance_id":doc}); return doc
    def list_board(self,board_id):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM bulletin_board_publications WHERE board_id=? ORDER BY pinned DESC,thread_root_id,sequence_number",(board_id,))]
    def moderate_board_post(self,moderator_actor_id,document_instance_id,operation,reason="",board_id="",new_status="hidden",world_time=0):
        with sqlite3.connect(self.db_path) as con:
            old=con.execute("SELECT status,board_id FROM bulletin_board_publications WHERE document_instance_id=?",(document_instance_id,)).fetchone(); old_status=old[0] if old else ""; board_id=board_id or (old[1] if old else "")
            con.execute("UPDATE bulletin_board_publications SET status=?,updated_at=? WHERE document_instance_id=?",(new_status,utc_now(),document_instance_id)); mid=stable_id("mod",document_instance_id,operation,utc_now(),uuid.uuid4().hex); con.execute("INSERT INTO written_moderation_events VALUES(?,?,?,?,?,?,?,?,?,?,?)",(mid,document_instance_id,board_id,moderator_actor_id,operation,reason,old_status,new_status,world_time,utc_now(),jdump({})))
        self.publish("board_post_hidden" if new_status=="hidden" else "board_post_restored",{"document_instance_id":document_instance_id}); return True
    def trace_document(self,doc):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; return {"document":self.get_document(doc),"versions":[dict(r) for r in con.execute("SELECT * FROM written_document_versions WHERE document_instance_id=? ORDER BY version_number",(doc,))],"audit":[dict(r) for r in con.execute("SELECT * FROM written_content_audit_events WHERE document_instance_id=? ORDER BY created_at",(doc,))]}
