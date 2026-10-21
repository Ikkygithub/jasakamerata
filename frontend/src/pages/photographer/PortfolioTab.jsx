import { useCallback, useEffect, useState } from "react";
import { Trash2, Upload, Star, ArrowUp, ArrowDown, Plus } from "lucide-react";
import { toast } from "sonner";
import { api, mediaUrl } from "@/lib/api";
import { run } from "./StudioTabs";

function ItemCard({ it, first, last, move, reload }) {
  const [title, setTitle] = useState(it.title || "");
  const [description, setDescription] = useState(it.description || "");
  const dirty = title !== (it.title || "") || description !== (it.description || "");
  const save = async () => { if (await run(() => api.put(`/photographer/portfolio/${it.item_id}`, { title, description }), "Info portofolio disimpan")) reload(); };
  const cover = async () => { if (await run(() => api.post(`/photographer/portfolio/${it.item_id}/cover`), "Sampul diperbarui")) reload(); };
  const remove = async () => { if (window.confirm("Hapus foto ini dari portofolio?") && (await run(() => api.del(`/photographer/portfolio/${it.item_id}`), "Foto dihapus"))) reload(); };
  return (
    <div className={it.is_cover ? "pf-card cover" : "pf-card"} data-testid={`pf-item-${it.item_id}`}>
      <div className="pf-img"><img src={mediaUrl(it.url)} alt={title || "Portofolio"} />{it.is_cover && <span className="cover-tag">Sampul</span>}</div>
      <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Judul" data-testid={`pf-title-${it.item_id}`} />
      <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Deskripsi singkat" data-testid={`pf-desc-${it.item_id}`} />
      <div className="row-actions">
        {dirty && <button className="olive-btn" onClick={save} data-testid={`pf-save-${it.item_id}`}>Simpan</button>}
        {!it.is_cover && <button className="icon-btn" title="Jadikan sampul" onClick={cover} data-testid={`pf-cover-${it.item_id}`}><Star size={15} /></button>}
        <button className="icon-btn" title="Naikkan" disabled={first} onClick={() => move(-1)} data-testid={`pf-up-${it.item_id}`}><ArrowUp size={15} /></button>
        <button className="icon-btn" title="Turunkan" disabled={last} onClick={() => move(1)} data-testid={`pf-down-${it.item_id}`}><ArrowDown size={15} /></button>
        <button className="icon-btn danger" title="Hapus" onClick={remove} data-testid={`pf-delete-${it.item_id}`}><Trash2 size={15} /></button>
      </div>
    </div>
  );
}

export function PortfolioTab({ reload: reloadProfile }) {
  const [items, setItems] = useState(null);
  const [file, setFile] = useState(null);
  const [meta, setMeta] = useState({ title: "", description: "" });
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState("");
  const [inputKey, setInputKey] = useState(0);
  const load = useCallback(() => api.get("/photographer/portfolio").then(setItems).catch(() => setItems([])), []);
  useEffect(() => { load(); }, [load]);
  const reload = () => { load(); reloadProfile(); };

  const pick = (f) => {
    if (preview) URL.revokeObjectURL(preview);
    if (f && !["image/jpeg", "image/png", "image/webp"].includes(f.type)) { toast("Gunakan file JPG, PNG, atau WEBP"); return; }
    if (f && f.size > 8 * 1024 * 1024) { toast("Ukuran file maksimal 8 MB"); return; }
    setFile(f || null);
    setPreview(f ? URL.createObjectURL(f) : "");
  };
  const upload = async (e) => {
    e.preventDefault();
    if (!file) return toast("Pilih foto terlebih dahulu");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", meta.title);
    fd.append("description", meta.description);
    setBusy(true);
    try { await api.upload("/photographer/portfolio", fd); toast("Foto diunggah"); pick(null); setInputKey((k) => k + 1); setMeta({ title: "", description: "" }); reload(); } catch (err) { toast(err.message); } finally { setBusy(false); }
  };
  const move = async (i, dir) => {
    const ids = items.map((x) => x.item_id);
    [ids[i], ids[i + dir]] = [ids[i + dir], ids[i]];
    if (await run(() => api.post("/photographer/portfolio/reorder", { ids }))) reload();
  };

  return (
    <>
      <form className="panel-form upload-form" onSubmit={upload} data-testid="portfolio-upload-form">
        <div className="upload-drop">{preview ? <img src={preview} alt="Pratinjau" data-testid="portfolio-preview" /> : <Upload size={22} />}</div>
        <div className="upload-fields">
          <label>Foto (JPG/PNG/WEBP, maks 8 MB)<input key={inputKey} type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => pick(e.target.files[0])} data-testid="portfolio-file-input" /></label>
          <div className="two-col"><label>Judul<input value={meta.title} onChange={(e) => setMeta({ ...meta, title: e.target.value })} data-testid="portfolio-title-input" /></label><label>Deskripsi<input value={meta.description} onChange={(e) => setMeta({ ...meta, description: e.target.value })} data-testid="portfolio-desc-input" /></label></div>
          <button className="olive-btn" disabled={busy || !file} data-testid="portfolio-upload-button"><Plus size={15} /> {busy ? "Mengunggah..." : "Unggah foto"}</button>
        </div>
      </form>
      {items === null && <p className="muted">Memuat portofolio...</p>}
      {items?.length === 0 && <div className="empty" data-testid="portfolio-empty"><p>Belum ada portofolio. Unggah minimal 3 foto terbaikmu.</p></div>}
      <div className="pf-grid" data-testid="studio-gallery">{items?.map((it, i) => <ItemCard key={`${it.item_id}-${it.title}-${it.description}`} it={it} first={i === 0} last={i === items.length - 1} move={(d) => move(i, d)} reload={reload} />)}</div>
    </>
  );
}
