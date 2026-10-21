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
| Pembayaran | Midtrans Snap (kode siap, **aktif setelah kunci diisi**) | Tanpa kunci → mode DEMO |
| Email notifikasi | Resend via Emergent (kode siap, **aktif setelah EMERGENT_EMAIL_KEY tersedia**) | Setiap percobaan tercatat di Admin → Email |

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

## 5b. Mengaktifkan Midtrans PRODUCTION
1. Login ke dashboard Midtrans (mode **Production**) → **Settings → Access Keys**. Salin Server Key dan Client Key.
2. Buka file `backend/.env` di proyek (atau menu Secrets/Environment pada deployment Emergent). Isi sendiri, jangan kirim lewat chat:
   `MIDTRANS_SERVER_KEY="..."`, `MIDTRANS_CLIENT_KEY="..."`, `MIDTRANS_IS_PRODUCTION="true"`. Restart backend atau deploy ulang.
3. Midtrans → **Settings → Configuration → Payment Notification URL**: `https://jasakamerata.com/api/payments/midtrans/notification`.
   **Perhatian:** akun merchant Anda juga dipakai website lain. Satu akun Midtrans hanya punya satu Notification URL. Mengubahnya akan memutus notifikasi ke website lama. Tanyakan dulu ke Midtrans apakah akun boleh dipakai untuk domain kedua, atau minta akun/merchant terpisah. Jangan ubah URL ini tanpa memastikan hal tersebut.
4. Finish Redirect URL: `https://jasakamerata.com/customer/pesanan`.
5. Uji dengan satu transaksi bernilai kecil. Pastikan status pesanan berubah menjadi "Lunas · terverifikasi Midtrans" dan Admin → Audit menampilkan `payment.settlement`.
6. Alur: customer membayar setelah fotografer menerima pesanan (batas 24 jam). Lewat dari itu, pesanan otomatis batal. Status lunas hanya dari notifikasi Midtrans yang tanda tangannya valid dan nominalnya cocok. Refund dilakukan manual oleh admin (status "Refund diproses manual").

## 5c. Email notifikasi
- Email terkirim ke fotografer saat ada pesanan baru atau pembayaran terverifikasi, dan ke customer saat hasil diserahkan. Balasan email diarahkan ke rifkyapriawan04@gmail.com.
- Saat ini `EMERGENT_EMAIL_KEY` di `backend/.env` masih kosong, sehingga email **belum terkirim**. Status ini tercatat jujur sebagai "disabled" di Admin → Email.

## 5d. Kata "emergent" di link
- Alamat `*.emergentagent.com` / `*.emergent.host` adalah alamat bawaan platform dan tidak bisa diganti. Hubungkan domain jasakamerata.com (bagian 3) agar link dan hasil pencarian memakai domain Anda.
- Sudah disiapkan: canonical dan og:url ke https://jasakamerata.com, `robots.txt`, dan `sitemap.xml`. Setelah domain aktif, daftarkan sitemap di Google Search Console.
- Halaman login Google tetap melewati `auth.emergentagent.com`, karena layanan login dikelola Emergent.

## 6. Backup dan log
- Database: di Emergent, gunakan fitur backup atau ekspor yang tersedia pada deployment. Untuk server sendiri: `mongodump --uri "$MONGO_URL" --db <DB_NAME> --out backup-YYYYMMDD`, lalu pulihkan dengan `mongorestore`.
- File tersimpan di object storage dan terhubung lewat koleksi `portfolio_items`, `deliveries`, dan `verifications`. Jangan hapus koleksi ini.
- Log backend dapat dilihat di panel deployment Emergent (Logs).
- Rollback kode: gunakan fitur rollback/riwayat versi di Emergent, lalu deploy ulang.

## 7. Yang masih harus diselesaikan
| Hal | Status | Langkah |
|---|---|---|
| Pembayaran Midtrans | Kode siap, kunci kosong | Ikuti bagian 5b |
| Email notifikasi | Kode siap, kunci email belum tersedia | Bagian 5c |
| Login email + kata sandi, verifikasi email | Tidak dibuat (Anda memilih Google saja) | Email sudah diverifikasi oleh Google |
| Domain produksi + uji Google SSO di domain | Menunggu langkah 3 | Ikuti langkah 3, lalu uji login |
| Badge "Made with Emergent" di pojok halaman | Disisipkan platform, bukan kode aplikasi | Hubungi dukungan Emergent untuk opsi menghilangkan badge |
