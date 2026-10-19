import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { MessageCircle } from "lucide-react";
import { api, fmtTime } from "@/lib/api";
import { ChatThread } from "./ChatThread";

export function Inbox({ role, onRead }) {
  const [list, setList] = useState(null);
  const [params, setParams] = useSearchParams();
  const active = params.get("c");

  const load = useCallback(() => api.get("/chat/conversations").then(setList).catch(() => setList([])), []);
  useEffect(() => { load(); const t = setInterval(load, 8000); return () => clearInterval(t); }, [load]);
  useEffect(() => {
    if (!active) return;
    const t = setTimeout(() => { load(); onRead?.(); }, 800);
    return () => clearTimeout(t);
  }, [active, load, onRead]);

  if (!list) return <p className="muted">Memuat percakapan...</p>;
  if (!list.length) return <div className="empty" data-testid="inbox-empty"><MessageCircle size={24} /><p>Belum ada percakapan.</p></div>;
  const conv = list.find((c) => c.conversation_id === active);
  const other = (c) => (role === "customer" ? { name: c.photographer_name, img: c.photographer_image } : { name: c.customer_name, img: c.customer_picture });

  return (
    <div className="inbox" data-testid="chat-inbox">
      <div className="inbox-list">
        {list.map((c) => {
          const o = other(c);
          const unread = c[`unread_${role}`];
          return (
            <button key={c.conversation_id} className={c.conversation_id === active ? "inbox-item active" : "inbox-item"} onClick={() => setParams({ c: c.conversation_id })} data-testid={`conversation-${c.conversation_id}`}>
              {o.img ? <img src={o.img} alt={o.name} /> : <span className="avatar">{o.name?.[0]}</span>}
              <span className="inbox-copy"><b>{o.name}</b><small>{c.last_message || "Belum ada pesan"}</small></span>
              <span className="inbox-meta"><small>{fmtTime(c.last_at)}</small>{unread > 0 && <i data-testid={`unread-${c.conversation_id}`}>{unread}</i>}</span>
            </button>
          );
        })}
      </div>
      <div className="inbox-thread">
        {conv ? <><div className="chat-head"><div><h3>{other(conv).name}</h3></div></div><ChatThread key={conv.conversation_id} conversation={conv} role={role} onSent={load} /></> : <div className="chat-gate"><p>Pilih percakapan untuk membaca pesan.</p></div>}
      </div>
    </div>
  );
}
