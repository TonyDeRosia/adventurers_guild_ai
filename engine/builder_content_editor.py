from __future__ import annotations
import json, os, tempfile, copy
from pathlib import Path
from typing import Any

class BuilderContentEditor:
    """Draft-only JSON content editor for builder mutation commands."""
    def __init__(self, world_root: Path, relative_path: str, collection_key: str, id_key: str):
        self.world_root=Path(world_root); self.path=self.world_root/'builder'/relative_path; self.collection_key=collection_key; self.id_key=id_key
    def load(self)->dict[str,Any]:
        if not self.path.exists(): return {self.collection_key: []}
        return json.loads(self.path.read_text(encoding='utf-8') or '{}')
    def save(self, data:dict[str,Any])->None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd,tmp=tempfile.mkstemp(dir=str(self.path.parent), prefix=self.path.name+'.', suffix='.tmp')
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(data,f,indent=2,sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,self.path)
    def records(self,data=None):
        data=data or self.load(); val=data.setdefault(self.collection_key, [])
        if isinstance(val, dict): return val
        return val
    def find(self, rid:str, data=None):
        recs=self.records(data)
        if isinstance(recs, dict): return recs.get(rid)
        return next((r for r in recs if str(r.get(self.id_key) or r.get('id'))==rid), None)
    def create(self,rid:str, template:dict[str,Any]|None=None):
        data=self.load(); recs=self.records(data)
        if self.find(rid,data): raise ValueError(f'{rid} already exists')
        rec=copy.deepcopy(template or {self.id_key:rid,'id':rid,'name':rid.replace('_',' ').title(),'enabled':True,'tags':[]})
        rec[self.id_key]=rid
        if isinstance(recs, dict): recs[rid]=rec
        else: recs.append(rec)
        self.save(data); return rec
    def clone(self,src,new):
        data=self.load(); old=self.find(src,data)
        if not old: raise ValueError(f'{src} not found')
        if self.find(new,data): raise ValueError(f'{new} already exists')
        rec=copy.deepcopy(old); rec[self.id_key]=new; rec['id']=new
        recs=self.records(data); recs[new]=rec if isinstance(recs,dict) else recs.append(rec)
        self.save(data); return rec
    def set_field(self,rid,field,value):
        data=self.load(); rec=self.find(rid,data)
        if not rec: raise ValueError(f'{rid} not found')
        rec[field]=value; self.save(data); return rec
    def list_value(self,rid,field,value,add=True):
        data=self.load(); rec=self.find(rid,data)
        if not rec: raise ValueError(f'{rid} not found')
        vals=list(rec.setdefault(field,[]))
        if add and value not in vals: vals.append(value)
        if not add: vals=[v for v in vals if v!=value]
        rec[field]=vals; self.save(data); return rec
    def delete(self,rid):
        data=self.load(); recs=self.records(data)
        if isinstance(recs,dict): recs.pop(rid,None)
        else: data[self.collection_key]=[r for r in recs if str(r.get(self.id_key) or r.get('id'))!=rid]
        self.save(data)
    def validate(self,rid:str|None=None):
        data=self.load(); recs=self.records(data); vals=list(recs.values()) if isinstance(recs,dict) else list(recs)
        ids=[str(r.get(self.id_key) or r.get('id')) for r in vals]
        errs=[]
        if len(ids)!=len(set(ids)): errs.append('duplicate IDs')
        if rid and rid not in ids: errs.append(f'{rid} not found')
        return {'ok':not errs,'errors':errs,'count':len(vals)}
