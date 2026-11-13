"""Optional remote embeddings + Qdrant adapter; local SQL remains authorization authority."""
import os,math
import httpx
from typing import Protocol
class VectorStore(Protocol):
    def index(self,chunks:list): ...
    def search(self,query:str,allowed_ids:list[int],k:int)->list[int]: ...
def enabled():return bool(os.getenv('QDRANT_URL') and os.getenv('EMBEDDING_API_KEY') and os.getenv('EMBEDDING_MODEL'))
class CompatibleEmbeddings:
    def embed(self,texts):
        base=os.getenv('EMBEDDING_BASE_URL','').rstrip('/')
        if not base.startswith('https://'):raise ValueError('Embedding provider requires HTTPS.')
        r=httpx.post(base+'/embeddings',headers={'Authorization':'Bearer '+os.environ['EMBEDDING_API_KEY']},json={'model':os.environ['EMBEDDING_MODEL'],'input':texts},timeout=30)
        r.raise_for_status();items=sorted(r.json()['data'],key=lambda x:x['index'])
        if [x['index'] for x in items]!=list(range(len(texts))):raise ValueError('Embedding count/index mismatch.')
        vectors=[x['embedding'] for x in items]
        if not vectors or not vectors[0] or any(len(v)!=len(vectors[0]) or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in v) for v in vectors):raise ValueError('Invalid embedding vectors.')
        return vectors
class QdrantStore:
    def __init__(self):
        self.base=os.environ['QDRANT_URL'].rstrip('/')
        self.collection=os.getenv('QDRANT_COLLECTION','campuspath')
        if not self.collection.replace('_','').replace('-','').isalnum():raise ValueError('Invalid collection name.')
        self.headers={'api-key':os.environ['QDRANT_API_KEY']} if os.getenv('QDRANT_API_KEY') else {}
        self.embedding=CompatibleEmbeddings()
    def index(self,chunks):
        for offset in range(0,len(chunks),32):
            batch=chunks[offset:offset+32];vectors=self.embedding.embed([c.text for c in batch])
            r=httpx.get(f'{self.base}/collections/{self.collection}',headers=self.headers,timeout=10)
            if r.status_code==404:
                r=httpx.put(f'{self.base}/collections/{self.collection}',headers=self.headers,json={'vectors':{'size':len(vectors[0]),'distance':'Cosine'}},timeout=15)
            r.raise_for_status()
            r=httpx.put(f'{self.base}/collections/{self.collection}/points?wait=true',headers=self.headers,json={'points':[{'id':c.id,'vector':v} for c,v in zip(batch,vectors)]},timeout=30);r.raise_for_status()
    def search(self,query,allowed_ids,k=4):
        if not allowed_ids:return []
        vector=self.embedding.embed([query])[0]
        r=httpx.post(f'{self.base}/collections/{self.collection}/points/query',headers=self.headers,json={'query':vector,'filter':{'must':[{'has_id':allowed_ids}]},'limit':k,'with_payload':False},timeout=15);r.raise_for_status()
        # Never trust a remote vector service to enforce authorization correctly.
        allowed=set(allowed_ids)
        return [p['id'] for p in r.json()['result']['points'] if p['id'] in allowed]
