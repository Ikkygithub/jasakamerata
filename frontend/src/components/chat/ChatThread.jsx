import { useCallback, useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { toast } from "sonner";
import { api, fmtTime } from "@/lib/api";

export function ChatThread({ conversation, role, onSent }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const bodyRef = useRef(null);
  const cid = conversation.conversation_id;

  const load = useCallback(() => api.get(`/chat/conversations/${cid}/messages`).then(setMessages).catch(() => {}), [cid]);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => { bodyRef.current?.scrollTo(0, bodyRef.current.scrollHeight); }, [messages.length]);

  const send = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    try {
      const msg = await api.post(`/chat/conversations/${cid}/messages`, { text });
      setMessages((m) => [...m, msg]);
      setText("");
      onSent?.();
    } catch (err) { toast(err.message); }
  };

  return (
    <div className="thread" data-testid="chat-thread">
      <div className="chat-body" ref={bodyRef} data-testid="chat-messages">
        {!messages.length && <div className="bubble received">Mulai percakapan — tanyakan paket, tanggal, atau kebutuhan khususmu.</div>}
        {messages.map((m) => (
          <div className={`bubble ${m.sender_role === role ? "sent" : "received"}`} key={m.message_id} data-testid={`chat-message-${m.message_id}`}>
            {m.text}<small>{fmtTime(m.created_at)}</small>
          </div>
        ))}
      </div>
      <form className="chat-compose" onSubmit={send}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Tulis pesan..." data-testid="chat-message-input" />
        <button data-testid="chat-send-button"><Send size={17} /></button>
      </form>
    </div>
  );
}
