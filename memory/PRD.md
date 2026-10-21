# PRD — Jasa Kamera

## Original problem statement
Membangun ulang website Jasa Kamera sebagai marketplace jasa fotografi freelance di Kota Makassar. Platform mempertemukan customer dengan fotografer untuk kategori Wedding, Commercial, Event, dan Graduation. Customer dapat mencari, melihat portofolio, chat, menyimpan favorit, dan mengajukan booking. Fotografer wajib memilih satu kategori saat mendaftar dan memasukkan nomor rekening untuk wallet/pencairan. Nomor rekening serta data transaksi sensitif harus terenkripsi dan dimasking. Autentikasi yang dipilih adalah Google OAuth terkelola. Pembayaran ditunda untuk tahap ini. Data awal terdiri dari 12 profil fotografer DEMO.

## Architecture decisions
- React dengan React Router, Tailwind primitives, Lucide icons, dan CSS editorial responsif.
- FastAPI + MongoDB melalui Motor; seluruh akses database memakai environment yang tersedia.
- API memakai `/api` prefix dan frontend hanya memakai `REACT_APP_BACKEND_URL`.
- Role-ready Google OAuth session flow menggunakan callback fragment, server-side session exchange, httpOnly cookie, dan validasi response provider.
- Nomor rekening memakai Fernet encryption server-side dan hanya masked value yang dikembalikan ke client.
- Payment sengaja ditunda; booking menyimpan `payment_status: deferred` dan tidak mengklaim transaksi nyata.

## User personas
- Customer Makassar yang ingin menemukan fotografer terpercaya untuk momen personal, event, graduation, atau kebutuhan brand.
- Fotografer freelance yang ingin memamerkan karya, mengelola layanan, menerima permintaan, dan menyiapkan wallet/pencairan.
- Admin platform yang memvalidasi fotografer dan mengawasi operasional marketplace.

## Core requirements (static)
- Empat kategori final: Wedding, Commercial, Event, Graduation.
- Homepage marketplace, pencarian, filter kategori, list/grid, profil publik, galeri, paket layanan, chat, favorit, booking, dan dashboard customer.
- Registrasi fotografer dengan kategori dan rekening terenkripsi.
- API protected untuk session, chat, favorite, booking, dan dashboard.
- Data DEMO tidak boleh dianggap transaksi nyata atau ulasan nyata.
- Semua kontrol dan informasi penting memiliki `data-testid` unik.

## Implemented
### 2026-10-19
- Mengganti template awal dengan homepage Jasa Kamera bergaya editorial: hero, pencarian, kategori, fotografer pilihan, layanan, cara kerja, CTA fotografer, footer.
- Menambahkan 12 fotografer DEMO dengan empat kategori, galeri, paket, harga Rupiah, badge verifikasi, dan profil publik.
- Menambahkan pencarian/filter backend, list/grid frontend, profil fotografer, galeri navigable, paket, dan booking request modal.
- Menambahkan registrasi fotografer dengan validasi empat kategori dan rekening terenkripsi/masked.
- Menambahkan Google OAuth callback flow, session cookie, `/auth/me`, logout, protected dashboard, dan controlled OAuth errors.
- Menambahkan endpoint chat, favorites, bookings, dashboard summary, serta error states untuk pengguna belum masuk.
- Menyimpan auth testing playbook dan menjalankan regression backend/frontend sampai lulus.


### 2026-10-19 — Fase 2 (Booking, Kalender, Chat, Studio, Admin)
- Backend dipecah modular: core.py, auth.py, seed.py, routers/{catalog,availability,bookings,chat,customer,photographer,admin}.py.
- Role-based access (customer/photographer/admin) via require_role; admin lewat env ADMIN_EMAILS; fotografer terhubung lewat email pendaftaran.
- Booking lifecycle: pending → accepted/declined → completed/cancelled, riwayat status, cek bentrok server-side (booking diterima + blokir jadwal), validasi jam/tanggal/tengah malam, rekomendasi fotografer alternatif saat bentrok.
- Kalender ketersediaan publik + blokir jadwal oleh fotografer.
- Chat persisten: conversations + messages, unread counter, inbox customer & fotografer (polling).
- Studio Fotografer (/studio): ringkasan, pesanan, kalender, layanan CRUD, portofolio (URL), chat, wallet DEMO + permintaan pencairan (snapshot rekening terenkripsi), profil.
- Panel Admin (/admin): ringkasan, verifikasi fotografer (pendaftar baru tersembunyi sampai disetujui), pesanan, pencairan, pengguna, audit log.
- Frontend dipecah menjadi pages/ components/ context/ lib/; tampilan publik tidak berubah.
- Testing: iteration_4 backend 16/16, frontend semua alur lulus; temuan minor sudah diperbaiki.


### 2026-10-21 — Fase 3 (Master prompt Jasakamerata, bertahap)
- Pilihan user: Midtrans DITUNDA, login Google saja, Hostinger Web/Cloud (PHP/MySQL), tetap 4 kategori.
- Branding Jasakamerata (title, meta, OG, favicon.svg, header/footer, auth, policy). Badge "Made with Emergent" disisipkan platform (bukan kode app).
- Komisi 5%/95%; ledger idempoten (koleksi ledger + wallets, unique key) — earning & platform_commission sekali per pesanan selesai.
- Pendaftaran fotografer = onboarding setelah Google login (/daftar) tanpa rekening; rekening di Studio → Rekening (terenkripsi, masked, terkunci saat penarikan berjalan, audit).
- Portofolio upload ke Emergent Object Storage (portfolio_items, /api/media/{id}), judul/deskripsi/sampul/urutan/hapus.
- Pesanan: pending → accepted → delivered (file privat/tautan) → revision_requested/disputed/completed; ulasan sekali per pesanan selesai; slot lock saat accept.
- Penarikan Rp100rb–10jt: reserve atomik → admin approve → process → success (referensi wajib) / fail / reject (dana kembali).
- Verifikasi profesional terpisah (KTP privat, cek kelengkapan otomatis, keputusan admin).
- Admin: rifkyapriawan04@gmail.com via ADMIN_EMAILS (server-side). Tab: ringkasan, fotografer, verifikasi, pesanan, penarikan, ledger, pengguna, audit. /admin/dashboard & /photographer/dashboard alias.
- Customer dropdown (Profil Saya/Pesanan/Chat/Favorit/Keluar); beranda maks 2 fotografer per kategori; halaman /kebijakan/*.
- Dokumentasi pemilik: /app/docs/PANDUAN_PEMILIK.md (hosting: Web/Cloud Hostinger tidak bisa menjalankan FastAPI+MongoDB).
- Testing iteration_5: backend 22/22 + legacy 33 pass; frontend ~95%; temuan sudah diperbaiki.

## Backlog setelah Fase 3
- P0: Hubungkan domain jasakamerata.com + uji Google SSO di produksi.
- P1: Midtrans Snap sandbox + webhook (saat user siap), notifikasi email (Resend), reservasi slot sementara saat checkout.
- P2: Jam kerja mingguan di kalender, moderasi portofolio, ganti window.prompt dengan dialog.

## Next backlog (setelah fase 2)
- P1: Upload portofolio langsung (object storage), notifikasi in-app/email, ulasan setelah booking selesai.
- P1: Payment gateway sandbox (ditunda user), refund.
- P2: Realtime chat (websocket), skenario uji ADDIE/SUS, rate limiting.
- Catatan hosting: hPanel Hostinger (shared/cloud) hanya menyediakan MySQL; MongoDB perlu VPS Hostinger atau MongoDB Atlas.

## Prioritized backlog (lama)
### P0 — next required
- Integrasikan database-backed photographer dashboard dengan profil, portofolio, layanan, kalender, dan status verifikasi.
- Lengkapi inbox/conversation history yang membaca dan mengurutkan pesan dari backend.
- Tambahkan role middleware admin dan halaman verifikasi, pengguna, transaksi, komisi, refund, serta audit log.

### P1 — next product phase
- Tambahkan checkout sandbox resmi setelah provider dan kredensial merchant ditentukan.
- Implementasikan availability conflict checking, request-to-book status history, dan alternative photographer matching.
- Tambahkan wallet ledger, payout request, withdrawal status, dan admin review tanpa mengklaim transfer otomatis.

### P2 — research readiness
- Tambahkan notifikasi in-app, review hanya setelah booking selesai, upload portfolio dengan object storage, dan moderation.
- Tambahkan task flows serta pengumpulan SUS untuk penelitian ADDIE.
- Tambahkan observability, rate limiting, webhook verification, dan security audit lanjutan.

## Known limitations
- **PAYMENT DEFERRED/MOCKED**: belum ada gateway, QRIS, VA, webhook, refund sungguhan, atau payout sungguhan.
- Positive Google OAuth membutuhkan session eksternal; negative/error handling sudah divalidasi.
- Dashboard photographer dan admin masih menjadi backlog tahap berikutnya.