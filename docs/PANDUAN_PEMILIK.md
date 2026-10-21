# Panduan Jasakamerata untuk Pemilik Website

Versi: 21 Oktober 2026. Ditulis berdasarkan kode yang benar-benar ada di proyek ini.

## 1. Teknologi yang dipakai
| Bagian | Teknologi | Catatan |
|---|---|---|
| Tampilan (frontend) | React 19 (Create React App + CRACO) | Hasil build berupa file statis (HTML/JS/CSS) |
| Server (backend) | Python 3.11 + FastAPI | **Harus berjalan terus-menerus** (proses server) |
| Database | MongoDB | Koleksi: users, photographers, bookings, conversations, messages, favorites, portfolio_items, deliveries, reviews, verifications, ledger, wallets, payouts, availability_blocks, audit_logs |
| Penyimpanan file | Emergent Object Storage | Foto portofolio (publik), file hasil & dokumen KTP (privat). File tidak hilang saat redeploy |
| Login | Google (dikelola Emergent) | Tanpa kata sandi aplikasi |
| Pembayaran | **Belum aktif (DITUNDA)** | Pesanan berstatus pembayaran DEMO, tidak menagih dana |

## 2. Kecocokan dengan Hostinger Web/Cloud Hosting (status: DIANALISIS dari source code, belum diuji di Hostinger)
Paket Web/Cloud Hosting Hostinger (Premium, Business, Cloud) hanya menjalankan PHP + MySQL. Aplikasi ini butuh:
- Proses Python (FastAPI) yang terus berjalan → **tidak didukung** di Web/Cloud Hosting.
- Database MongoDB → **tidak tersedia** di hPanel (hPanel hanya menyediakan MySQL).

Kesimpulan: backend + database **tidak dapat** dijalankan di paket Web/Cloud Hosting Anda. Yang tetap bisa dimanfaatkan dari paket tersebut: **domain jasakamerata.com dan pengaturan DNS-nya di hPanel**, serta email domain bila ada.

### Pilihan (tanpa membeli apa pun sebelum Anda setuju)
1. **Direkomendasikan — Deploy di Emergent, domain tetap di Hostinger.** Backend, database, dan penyimpanan file berjalan di Emergent. Anda cukup mengarahkan domain dari hPanel. Tidak perlu migrasi database.
2. Hostinger VPS (KVM). Bisa menjalankan Python + MongoDB, tetapi ini paket berbeda (perlu pembelian) dan pemeliharaan server sendiri.
3. Menulis ulang backend ke PHP/MySQL supaya muat di Web Hosting. Ini pekerjaan besar dan berisiko, jadi tidak disarankan.

## 3. Menghubungkan jasakamerata.com (pilihan 1)
1. Di Emergent: buka proyek → **Deploy** → setelah aktif, buka **Custom Domain** → masukkan `jasakamerata.com` (dan `www.jasakamerata.com` bila perlu). Emergent akan menampilkan record DNS yang harus dibuat (biasanya A/CNAME).
2. Di hPanel Hostinger: **Domains → jasakamerata.com → DNS / Nameservers → Manage DNS records**.
   - Catat atau screenshot record lama dulu sebagai cadangan.
   - Tambahkan atau ubah record persis seperti yang ditampilkan Emergent. Hapus record A lama untuk `@` yang mengarah ke hosting Hostinger **hanya jika** Emergent memintanya.
3. Tunggu propagasi DNS (beberapa menit hingga 24 jam). HTTPS/SSL diaktifkan otomatis oleh Emergent setelah domain terverifikasi.
4. Cek: buka `https://jasakamerata.com`. Pastikan muncul gembok dan halaman Jasakamerata.
5. Rollback DNS: kembalikan record dari catatan langkah 2.

## 4. Login Google
- Login memakai layanan Google yang dikelola Emergent. Alamat kembali (redirect) dibuat otomatis dari domain yang sedang dibuka, sehingga tidak perlu mengatur Google Cloud Console.
- Setelah domain produksi aktif, uji: Masuk → pilih akun Google → harus kembali ke Jasakamerata dalam keadaan login. Status: **belum diuji di domain produksi**.
- Admin: email `rifkyapriawan04@gmail.com` ditetapkan di server (variabel `ADMIN_EMAILS` di backend/.env). Saat email itu login lewat Google (email terverifikasi Google), perannya otomatis menjadi admin. Pengguna lain tidak bisa mengubah perannya sendiri.
- Fotografer: masuk dengan Google di `/daftar`, isi nama + kategori, lalu akun menjadi fotografer. Rekening, portofolio, dan verifikasi diisi di Studio.

## 5. Operasional harian
- **Verifikasi fotografer:** Admin → Verifikasi. Buka KTP (setiap akses tercatat di audit log), lalu Setujui / Minta perbaikan / Tolak. Lencana Terverifikasi hanya muncul setelah disetujui.
- **Publikasi profil:** Admin → Fotografer → Tampilkan publik / Sembunyikan.
- **Komisi:** 5% platform, 95% fotografer. Dicatat sekali per pesanan saat customer menyetujui hasil (Admin → Komisi & Ledger).
- **Penarikan saldo** (Rp100.000–Rp10.000.000): Admin → Penarikan → Setujui → Mulai transfer → tampilkan nomor rekening lengkap → transfer manual lewat bank Anda → klik *Transfer berhasil* dan isi nomor referensi. Jika gagal atau ditolak, dana otomatis kembali ke saldo fotografer.
- **Sengketa:** Admin → Pesanan → filter "Dalam sengketa" → selesaikan atau batalkan.

## 6. Backup dan log
- Database: di Emergent, gunakan fitur backup atau ekspor yang tersedia pada deployment. Untuk server sendiri: `mongodump --uri "$MONGO_URL" --db <DB_NAME> --out backup-YYYYMMDD`, lalu pulihkan dengan `mongorestore`.
- File tersimpan di object storage dan terhubung lewat koleksi `portfolio_items`, `deliveries`, dan `verifications`. Jangan hapus koleksi ini.
- Log backend dapat dilihat di panel deployment Emergent (Logs).
- Rollback kode: gunakan fitur rollback/riwayat versi di Emergent, lalu deploy ulang.

## 7. Yang masih harus diselesaikan
| Hal | Status | Langkah |
|---|---|---|
| Pembayaran Midtrans | DITUNDA atas permintaan Anda | Saat siap: buat Server Key & Client Key **sandbox**, masukkan sendiri ke backend/.env (jangan dikirim lewat chat), lalu minta integrasi |
| Login email + kata sandi, verifikasi email | Tidak dibuat (Anda memilih Google saja) | Email sudah diverifikasi oleh Google |
| Domain produksi + uji Google SSO di domain | Menunggu langkah 3 | Ikuti langkah 3, lalu uji login |
| Badge "Made with Emergent" di pojok halaman | Disisipkan platform, bukan kode aplikasi | Hubungi dukungan Emergent untuk opsi menghilangkan badge |
| Notifikasi email | Belum ada | Indikator di aplikasi tersedia (badge chat/pesanan) |
