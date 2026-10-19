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

## Prioritized backlog
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