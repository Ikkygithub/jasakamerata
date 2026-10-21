import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import { api, mediaUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { ChatThread } from "./ChatThread";

export function ChatModal({ p, close }) {
  const { user } = useAuth();
  const [conv, setConv] = useState(null);
  const [error, setError] = useState("");
  const isCustomer = user && (user.role || "customer") === "customer";

  useEffect(() => {
    if (!isCustomer) return;
    api.post("/chat/conversations", { photographer_id: p.photographer_id }).then(setConv).catch((e) => setError(e.message));
  }, [isCustomer, p.photographer_id]);

  let content;
  if (!user) content = <div className="chat-gate"><p>Masuk terlebih dahulu untuk mengirim pesan ke fotografer.</p><Link to="/masuk" className="olive-btn" data-testid="chat-login-link">Masuk dengan Google</Link></div>;
  else if (!isCustomer) content = <div className="chat-gate"><p>Chat dengan fotografer hanya tersedia untuk akun customer.</p></div>;
  else if (error) content = <div className="chat-gate"><p>{error}</p></div>;
  else if (!conv) content = <div className="chat-gate"><p>Membuka percakapan...</p></div>;
  else content = <ChatThread conversation={conv} role="customer" />;

  return (
    <div className="modal-backdrop">
      <div className="chat-modal" data-testid="chat-modal">
        <button className="modal-close" onClick={close} data-testid="close-chat"><X size={18} /></button>
        <div className="chat-head"><img src={mediaUrl(p.profile_image || p.gallery?.[0])} alt={p.name} /><div><h3>{p.name}</h3><span>Riwayat chat tersimpan di menu Chat</span></div></div>
        {content}
      </div>
    </div>
  );
}
