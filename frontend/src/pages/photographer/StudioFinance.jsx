import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, money, fmtTime, STATUS } from "@/lib/api";
import { StatusPill } from "@/components/dashboard/BookingRow";
import { run } from "./StudioTabs";

const LEDGER_LABEL = { earning: "Pendapatan 95%", payout_reserve: "Dana dicadangkan (penarikan)", payout_release: "Dana dikembalikan" };

export function BankTab({ bank, reload }) {
  const [form, setForm] = useState({ bank_name: bank.bank_name || "", holder_name: bank.holder_name || "", account_number: "" });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const save = async (e) => { e.preventDefault(); if (await run(() => api.put("/photographer/bank", form), "Rekening disimpan")) { setForm({ ...form, account_number: "" }); reload(); } };
  return (
    <div className="studio-split">
      <div className="panel-form" data-testid="bank-status">
        <h3>Rekening penarikan</h3>
        {bank.complete ? <><p><b>{bank.bank_name}</b> · {bank.holder_name}</p><p data-testid="bank-masked">Nomor: {bank.masked}</p><p className="muted small">Diperbarui {bank.updated_at && fmtTime(bank.updated_at)}. Rekening dipakai untuk semua penarikan saldo. Belum ada verifikasi bank otomatis — pastikan data sesuai buku tabungan.</p></>
          : <p className="notice" data-testid="bank-missing">Rekening belum ditambahkan{bank.legacy ? ` (data lama ${bank.masked} perlu dilengkapi nama bank & pemilik)` : ""}.</p>}
      </div>
      <form className="panel-form" onSubmit={save} data-testid="bank-form">
        <h3>{bank.complete ? "Perbarui rekening" : "Tambahkan rekening"}</h3>
        <label>Nama bank<input required value={form.bank_name} onChange={set("bank_name")} placeholder="Contoh: BCA, BRI, Mandiri" data-testid="bank-name-input" /></label>
        <label>Nama pemilik rekening<input required value={form.holder_name} onChange={set("holder_name")} data-testid="bank-holder-input" /></label>
        <label>Nomor rekening<input required inputMode="numeric" autoComplete="off" value={form.account_number} onChange={set("account_number")} data-testid="bank-number-input" /></label>
        <p className="muted small">Disimpan terenkripsi. Hanya kamu (tersamar) dan admin saat memproses transfer yang dapat melihatnya.</p>
        <button className="olive-btn" data-testid="bank-save-button">Simpan rekening</button>
      </form>
    </div>
  );
}

export function WalletTab({ wallet, reload }) {
  const [amount, setAmount] = useState("");
  const [payouts, setPayouts] = useState([]);
  const [ledger, setLedger] = useState([]);
  const load = useCallback(() => { api.get("/photographer/payouts").then(setPayouts).catch(() => {}); api.get("/photographer/ledger").then(setLedger).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);
  const n = Number(amount);
  const invalid = amount && (n < wallet.min || n > wallet.max || n > wallet.available) ? (n > wallet.available ? "Melebihi saldo yang dapat ditarik" : "Nominal harus Rp100.000 – Rp10.000.000") : "";
  const request = async (e) => {
    e.preventDefault();
    if (invalid) return toast(invalid);
    if (await run(() => api.post("/photographer/payouts", { amount: n }), "Permintaan penarikan diajukan")) { setAmount(""); load(); reload(); }
  };
  return (
    <>
      <div className="notice" data-testid="wallet-demo-notice">{wallet.note}</div>
      <div className="stats four">
        <div><span>Dapat ditarik</span><b data-testid="wallet-available">{money(wallet.available)}</b></div>
        <div><span>Saldo tertunda (pesanan berjalan)</span><b>{money(wallet.pending)}</b></div>
        <div><span>Dicadangkan untuk penarikan</span><b data-testid="wallet-reserved">{money(wallet.reserved)}</b></div>
        <div><span>Total ditarik</span><b>{money(wallet.paid_out)}</b></div>
      </div>
      <p className="muted small">Total pendapatan 95%: <b>{money(wallet.earned)}</b> · Komisi platform 5% dari pesananmu: <b>{money(wallet.commission)}</b> · <Link to="/kebijakan/penarikan-saldo">Kebijakan penarikan</Link></p>
      {!wallet.bank.complete ? <p className="notice" data-testid="wallet-bank-missing">Rekening belum ditambahkan. <Link to="/studio/rekening">Lengkapi rekening</Link> untuk menarik saldo.</p> : (
        <form className="panel-form inline" onSubmit={request} data-testid="payout-form">
          <input required type="number" min={wallet.min} max={wallet.max} step="1000" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Nominal (Rp100.000 – Rp10.000.000)" data-testid="payout-amount-input" />
          <button className="olive-btn" disabled={!!invalid} data-testid="payout-submit">Ajukan ke {wallet.bank.bank_name} {wallet.bank.masked}</button>
        </form>
      )}
      {invalid && <p className="field-error" data-testid="payout-error">{invalid}</p>}
      <h3 className="list-title">Riwayat penarikan</h3>
      {!payouts.length && <p className="muted">Belum ada permintaan penarikan.</p>}
      {payouts.map((p) => <div className="mini-row tall" key={p.payout_id} data-testid={`payout-${p.payout_id}`}><span><b>{money(p.amount)}</b><small>{p.bank_name} {p.bank_account_masked} · {fmtTime(p.created_at)}{p.transfer_reference && ` · Ref: ${p.transfer_reference}`}{p.note && ` · ${p.note}`}</small></span><StatusPill status={p.status} /></div>)}
      <h3 className="list-title">Riwayat transaksi saldo</h3>
      {!ledger.length && <p className="muted">Belum ada transaksi.</p>}
      {ledger.map((e) => <div className="mini-row" key={e.entry_id}><span>{LEDGER_LABEL[e.type] || e.type} · {e.ref} · {fmtTime(e.created_at)}</span><b className={e.amount < 0 ? "neg" : "pos"}>{e.amount < 0 ? "−" : "+"}{money(Math.abs(e.amount))}</b></div>)}
    </>
  );
}

export function VerificationTab({ profile, reload }) {
  const v = profile.verification || { status: "not_submitted" };
  const [form, setForm] = useState({ experience: "", links: "", consent: false });
  const [files, setFiles] = useState({ id_document: null, supporting: null });
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    const fd = new FormData();
    Object.entries(form).forEach(([k, val]) => fd.append(k, val));
    if (files.id_document) fd.append("id_document", files.id_document);
    if (files.supporting) fd.append("supporting", files.supporting);
    setBusy(true);
    try { await api.upload("/photographer/verification", fd); toast("Pengajuan verifikasi diterima dan menunggu pemeriksaan admin"); reload(); } catch (err) { toast(err.message); } finally { setBusy(false); }
  };
  const canSubmit = ["not_submitted", "needs_fix", "rejected"].includes(v.status);
  return (
    <div className="studio-split">
      <div className="panel-form" data-testid="verification-status">
        <h3>Status verifikasi profesional</h3>
        <StatusPill status={v.status} />
        {v.note && <p className="notice">Catatan admin: {v.note}</p>}
        <p className="muted small">Verifikasi profesional terpisah dari pendaftaran akun. Sistem hanya memeriksa kelengkapan otomatis (formulir, tipe & ukuran file, minimal 3 portofolio). Lencana Terverifikasi muncul setelah admin menyetujui — sistem tidak memeriksa keaslian KTP secara otomatis.</p>
      </div>
      {canSubmit ? (
        <form className="panel-form" onSubmit={submit} data-testid="verification-form">
          <h3>Ajukan verifikasi</h3>
          <label>Pengalaman fotografi<textarea rows={4} value={form.experience} onChange={(e) => setForm({ ...form, experience: e.target.value })} placeholder="Lama berkarya, jenis acara yang biasa ditangani, peralatan..." data-testid="verification-experience-input" /></label>
          <label>Tautan pendukung (Instagram/website)<input value={form.links} onChange={(e) => setForm({ ...form, links: e.target.value })} data-testid="verification-links-input" /></label>
          <label>KTP (JPG/PNG/PDF, maks 8 MB) — disimpan privat<input type="file" accept=".jpg,.jpeg,.png,.webp,.pdf" onChange={(e) => setFiles({ ...files, id_document: e.target.files[0] })} data-testid="verification-id-input" /></label>
          <label>Dokumen pendukung (opsional)<input type="file" accept=".jpg,.jpeg,.png,.webp,.pdf,.zip" onChange={(e) => setFiles({ ...files, supporting: e.target.files[0] })} data-testid="verification-supporting-input" /></label>
          <label className="check"><input type="checkbox" checked={form.consent} onChange={(e) => setForm({ ...form, consent: e.target.checked })} data-testid="verification-consent-checkbox" /> Saya setuju dokumen disimpan privat untuk keperluan verifikasi sesuai <Link to="/kebijakan/privasi" target="_blank">kebijakan privasi</Link>.</label>
          <button className="olive-btn" disabled={busy} data-testid="verification-submit">{busy ? "Mengirim..." : "Kirim pengajuan"}</button>
        </form>
      ) : <div className="panel-form"><p>{v.status === "approved" ? "Profilmu sudah terverifikasi." : `Pengajuan ${STATUS[v.status]?.toLowerCase()}.`}</p></div>}
    </div>
  );
}
