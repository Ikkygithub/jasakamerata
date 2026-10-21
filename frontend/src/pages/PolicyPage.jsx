import { Link, useParams } from "react-router-dom";
import { Header, Footer } from "@/components/layout/Header";

const POLICIES = {
  "syarat-ketentuan": ["Syarat & Ketentuan", [
    ["Tentang platform", "Jasakamerata mempertemukan customer dengan fotografer freelance di Makassar untuk kategori Wedding, Commercial, Event, dan Graduation. Jasakamerata bukan pihak yang melaksanakan sesi foto."],
    ["Akun", "Akun dibuat melalui login Google. Pengguna bertanggung jawab atas aktivitas pada akunnya. Peran admin hanya ditetapkan dari sisi server."],
    ["Fotografer", "Pendaftaran fotografer membuat akun dan akses Studio. Profil tampil publik setelah ditinjau admin. Lencana Terverifikasi hanya diberikan setelah pengajuan verifikasi profesional disetujui admin."],
    ["Pesanan", "Pesanan dibuat dari paket layanan dengan harga yang tercantum. Jadwal diperiksa server saat pesanan dibuat dan saat fotografer mengonfirmasi."],
  ]],
  privasi: ["Kebijakan Privasi", [
    ["Data yang dikumpulkan", "Nama, email, dan foto profil dari Google; data pesanan; pesan chat; rekening bank fotografer; dokumen verifikasi yang diunggah secara sukarela."],
    ["Perlindungan", "Nomor rekening disimpan terenkripsi dan hanya ditampilkan dalam bentuk tersamar. Dokumen identitas disimpan privat dan hanya dapat dibuka admin; setiap akses tercatat di audit log."],
    ["Akses data", "Customer dan fotografer hanya dapat melihat pesanan dan percakapan miliknya sendiri."],
  ]],
  "pembayaran-komisi": ["Pembayaran & Komisi", [
    ["Cara pembayaran", "Customer membayar melalui Midtrans setelah fotografer menerima pesanan, paling lambat 24 jam. Jika tidak dibayar, pesanan otomatis batal dan jadwal dilepas. Status Lunas hanya diberikan berdasarkan notifikasi Midtrans yang terverifikasi, bukan dari halaman browser. Selama pembayaran online belum diaktifkan, pesanan berjalan dalam mode DEMO tanpa tagihan."],
    ["Aliran dana", "Pembayaran customer diterima oleh merchant Jasakamerata. Jasakamerata tidak menyediakan escrow maupun split payment otomatis. Bagian fotografer (95%) dicatat di saldo dan dicairkan melalui penarikan yang diproses admin."],
    ["Komisi", "Komisi platform adalah 5% dari nilai jasa pesanan yang selesai. Fotografer menerima 95%. Contoh: jasa Rp500.000 → komisi Rp25.000, bagian fotografer Rp475.000. Tidak ada potongan tersembunyi."],
    ["Kapan pendapatan tercatat", "Pendapatan fotografer masuk ke saldo yang dapat ditarik setelah customer menyetujui hasil (pesanan Selesai). Pesanan yang masih berjalan atau dalam sengketa tercatat sebagai saldo tertunda."],
  ]],
  "pembatalan-refund": ["Pembatalan, Revisi & Sengketa", [
    ["Pembatalan", "Customer dapat membatalkan pesanan yang belum menerima hasil. Fotografer dapat menolak permintaan atau membatalkan pesanan yang dikonfirmasi dengan alasan."],
    ["Penyerahan hasil & revisi", "Fotografer menyerahkan hasil melalui platform (file atau tautan galeri). Customer dapat menyetujui hasil, meminta revisi sesuai paket, atau mengajukan keberatan. Tidak ada penyelesaian otomatis tersembunyi."],
    ["Sengketa", "Pesanan dalam sengketa ditinjau admin. Pendapatan terkait ditahan sampai keputusan admin."],
    ["Refund", "Pesanan yang sudah dibayar hanya dapat dibatalkan oleh admin. Refund diproses manual oleh admin ke customer dan tidak instan; statusnya tercatat di pesanan."],
  ]],
  "penarikan-saldo": ["Penarikan Saldo Fotografer", [
    ["Batas", "Minimum Rp100.000 dan maksimum Rp10.000.000 per permintaan, tidak melebihi saldo yang dapat ditarik."],
    ["Proses", "Saat diajukan, dana dicadangkan. Admin meninjau, memproses transfer bank secara manual, lalu mencatat nomor referensi transfer. Status Berhasil hanya diberikan setelah referensi transfer dicatat."],
    ["Ditolak atau gagal", "Jika permintaan ditolak atau transfer gagal, dana cadangan dikembalikan ke saldo yang dapat ditarik dan tercatat di riwayat transaksi."],
    ["Rekening", "Rekening dikelola di menu Rekening pada Studio dan tidak dapat diubah saat ada penarikan yang sedang diproses."],
  ]],
};

export default function PolicyPage() {
  const { slug } = useParams();
  const policy = POLICIES[slug] || POLICIES["syarat-ketentuan"];
  return (
    <>
      <Header />
      <main className="policy-page">
        <aside className="policy-nav">{Object.entries(POLICIES).map(([k, [t]]) => <Link key={k} to={`/kebijakan/${k}`} className={POLICIES[slug] === POLICIES[k] ? "active" : ""} data-testid={`policy-link-${k}`}>{t}</Link>)}</aside>
        <article data-testid="policy-content">
          <p className="eyebrow">KEBIJAKAN JASAKAMERATA · VERSI 2026-10</p>
          <h1>{policy[0]}</h1>
          {policy[1].map(([h, t]) => <section key={h}><h2>{h}</h2><p>{t}</p></section>)}
        </article>
      </main>
      <Footer />
    </>
  );
}
