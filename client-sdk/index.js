"use strict";
class OmniRAGClient {
  constructor(o={}) { this.host=o.host||"http://localhost:8000"; this.timeout=o.timeout||120000; }
  async _req(m,p,b) {
    const c=new AbortController(),t=setTimeout(()=>c.abort(),this.timeout);
    try {
      const r=await fetch(`${this.host}${p}`,{method:m,headers:{"Content-Type":"application/json"},body:b?JSON.stringify(b):undefined,signal:c.signal});
      if(!r.ok) throw new Error(`OmniRAG API ${r.status}`);
      return r.json();
    } finally { clearTimeout(t); }
  }
  ingest(filePath,metadata={}) { return this._req("POST","/api/v1/ingest",{file_path:filePath,metadata}); }
  chat(query,conversationId=null) { return this._req("POST","/api/v1/chat",{query,conversation_id:conversationId}); }
  listDocuments() { return this._req("GET","/api/v1/documents",null); }
  deleteDocument(id) { return this._req("DELETE",`/api/v1/documents/${id}`,null); }
  health() { return this._req("GET","/health",null); }
}
module.exports=OmniRAGClient;
