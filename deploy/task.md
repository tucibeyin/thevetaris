# Vetaris VPS Taşıma — Görev Listesi

Eski VPS: `51.81.34.27`  →  Yeni VPS: `135.125.175.223`
Domain: `thevetaris.com` (Squarespace DNS)

> ⚠️ **ÖNEMLİ:** Eski VPS **paylaşımlı/çok-kiracılı** bir sunucu. Üzerinde 10+ site var
> (teqlif.com, mottosoft.com, factnetworking.io, LiveKit, gunicorn/uvicorn app'leri...).
> Bu taşımada **SADECE `thevetaris.com`** yeni (adanmış) VPS'e alınacak. Eski VPS'in
> nginx'ine, diğer sitelerine, `/etc/letsencrypt`'in tamamına **DOKUNULMAYACAK**.
> Eski VPS'te sadece: (L bölümünde) `thevetaris` nginx symlink'i + `vetaris.service` kaldırılacak.

**Çalışma şekli:** Her adımı birlikte yapıyoruz. Her adımda:
1. Claude adımı açıklar + komutu verir.
2. Sen çalıştırırsın (VPS adımları) veya Claude yapar (repo adımları).
3. Çıktıyı paylaşırsın → birlikte kontrol → **onay** → sonraki adım.

Durum işaretleri: `[ ]` bekliyor · `[~]` devam ediyor · `[x]` tamam · `[!]` sorun var

---

## BÖLÜM A — Bilgi Toplama (eski VPS'te çalıştır)

- [x] **A1. OS ve sürümler** — İki VPS de BİREBİR AYNI: Debian 13 (trixie) 13.6 · Python 3.13.5 ·
  PostgreSQL 17.11. Sürüm uyumsuzluğu yok, `pg_dump`/`pg_restore` sorunsuz.
  Eski VPS'te certbot 4.0.0 kurulu. Yeni VPS'te PostgreSQL 17.11 zaten kurulu (psql çalışıyor),
  certbot yok. (`nginx: command not found` normal — `/usr/sbin` normal kullanıcının PATH'inde
  değil; A3 gerçek durumu gösterecek.)

- [x] **A2. SSL / certbot** — `thevetaris.com` sertifikası var:
  `/etc/letsencrypt/live/thevetaris.com/` (ECDSA, son kullanma 2026-11-06). Certbot systemd
  timer aktif. `/etc/letsencrypt` içinde 11 farklı domain var → **tamamı kopyalanmayacak**,
  sadece `thevetaris.com` cert'i taşınacak veya yeni VPS'te sıfırdan alınacak.

- [x] **A3. Nginx** — Kurulu ve çalışıyor (root servisi; `command not found` sadece PATH).
  `thevetaris` sitesi: `/etc/nginx/sites-available/thevetaris` (symlink `sites-enabled/thevetaris`),
  `proxy_pass http://127.0.0.1:8801`, 80 + 443 (certbot yönetiyor). thevetaris için özel
  `client_max_body_size` yok. → **Gerçek dosya içeriği A3b'de alınacak.**
  Not: eski VPS'te vetaris `0.0.0.0:8801` dinliyor (tüm arayüzler); yeni VPS'te ufw 8801'i
  kapatacağız, sorun değil (kod değişikliği ayrı iş).

- [x] **A4. systemd unit** — Eski VPS'teki GERÇEK unit zaten doğru (repo'daki bayat):
  ```ini
  [Unit]
  Description=Vetaris E-Commerce Python Server
  After=network.target
  [Service]
  User=tucibeyin
  Group=tucibeyin
  WorkingDirectory=/var/www/thevetaris.com
  ExecStart=/var/www/thevetaris.com/venv/bin/python3 src/server.py
  Restart=always
  [Install]
  WantedBy=multi-user.target
  ```
  Yeni VPS'te buna `After=postgresql.service` + `RestartSec=3` ekleyeceğiz (F1).

- [x] **A5. PostgreSQL** — DB `vetaris`, sahip `tucibeyin`, **~8 MB** (çok küçük), `en_US.UTF-8`.
  `pg_hba.conf`: local→`peer`, `127.0.0.1/32`→`scram-sha-256`. `.env`'de `DB_HOST=localhost`
  → 127.0.0.1 → **parolalı (scram) auth**. Yeni VPS'in default `pg_hba` aynı → değişiklik yok.

- [x] **A6. `.env`** — Sende. `DB_USER`/`DB_PASS` dolu (parolalı auth doğrulandı). E3'te aynısı kullanılacak.
  (`git status` → `.env` ve `deploy/vetaris.service` "modified" ama commit edilmemiş; önemsiz.)

- [!] **A7. Disk'te git'te OLMAYAN gerçek içerik VAR — taşınması ŞART:**
  - `public/images/` altında ~14 adet Türkçe isimli ürün görseli (FORMÜL-A.jpg, Hücresel
    yenileme2.jpg, sprey_kutu.jpg, ...) — git'te değil.
  - **`public/videos/`** — komple dizin, git'te değil (video bölümü bunları kullanıyor).
  → D bölümünde `git clone` sonrası `public/` dizini eski VPS'ten `rsync` ile senkronlanacak.

- [x] **A8. Firewall / cron** — Eski VPS ufw: 22, 80/443, + LiveKit/TURN portları (diğer app'ler
  için). Cron boş (certbot systemd timer kullanıyor). Yeni adanmış VPS'te sadece 22 + 80/443 gerek.

---

## BÖLÜM A2 — Ek Bilgi (karar öncesi son kontroller)

- [x] **A3b. Eski VPS nginx config** — Sade: `proxy_pass http://127.0.0.1:8801` + standart
  certbot SSL bloğu + HTTP→HTTPS 301. Özel timeout / buffering / Range / `client_max_body_size`
  YOK (Range'i `server.py` kendi hallediyor). → `certbot --nginx` yeni VPS'te bunun aynısını
  üretecek. G1 taslağı yeterli.

- [x] **A9. Taşınacak boyut** — `public/` toplam 26 MB (`images/` 20 MB, `videos/` 5.9 MB =
  tek dosya `video.mp4`). rsync saniyeler sürer, disk derdi yok.

- [x] **A10. DNS** — `thevetaris.com` A → `51.81.34.27` (**doğrudan, Cloudflare YOK**).
  `www` → CNAME → apex. NS: `ns-cloud-b{1..4}.googledomains.com` (Google Cloud DNS; yönetim
  paneli Squarespace'te ama authoritative NS hâlâ Google). → Cutover: Squarespace panelinden
  apex `A` kaydını `135.125.175.223` yap; `www` CNAME olduğu için otomatik takip eder.
  HTTP-01 cert doğrulaması cutover sonrası sorunsuz çalışır (proxy yok).

- [x] **A11. Yeni VPS durumu** — Kullanıcı sitelerini eski→yeni VPS'e **tek tek elle taşıyor**;
  teqlif bitti, sıra vetaris'te. Yeni VPS: nginx kurulu+çalışıyor, `sites-enabled/` = sadece
  teqlif. Disk 99G/68G boş, RAM 11Gi. **teqlif'e dokunulmayacak.**

- [x] **A11b. Postgres + certbot (yeni VPS)** — Postgres'te sadece `teqlif` DB var (vetaris yok
  → temiz). **`certbot` KURULU DEĞİL** (`command not found`) → C3'te kurulacak.
  ufw zaten aktif, `Nginx Full` + Cloudflare aralıkları açık (C4 neredeyse hazır).

- [x] **A11c. Yeni VPS'te thevetaris SSL zaten HAZIR** 🎉
  - `/etc/letsencrypt/live/thevetaris.com/` mevcut, `archive/thevetaris.com/*3.pem`'e symlink,
    **geçerli: `notAfter=Nov 6 11:28:53 2026`** (~2 ay). Daha önce letsencrypt kopyalanırken gelmiş.
  - `renewal/thevetaris.com.conf` var: `authenticator=nginx`, `installer=nginx`, account
    `6c391a...`. → certbot kurulunca `certbot renew` çalışır (DNS yeni VPS'i gösterince).
  - Nginx'te vetaris config YOK, `/var/www/thevetaris.com` YOK, `vetaris.service` YOK → uygulama temiz kurulacak.
  - **Sonuç:** B1 kararına gerek kalmadı. Sertifika hazır → G'de **tam SSL'li nginx config**
    doğrudan yazılacak; `certbot --nginx` ile yeniden ihraç GEREKMİYOR. certbot sadece
    ileride otomatik yenileme için kurulacak.
  - Kontrol edilecek: `/etc/letsencrypt/options-ssl-nginx.conf` + `ssl-dhparams.pem` +
    `accounts/` var mı (C3'te certbot kurulunca options dosyası kesin gelir).

---

## BÖLÜM B — Kararlar

- [x] **B1. SSL** — ÇÖZÜLDÜ. Sertifika yeni VPS'te zaten var ve geçerli (Nov 6'ya kadar,
  A11c). certbot'u sadece otomatik yenileme için kuracağız (C3). Nginx'e tam SSL config
  doğrudan yazılacak (G1). DNS geçişinde HTTPS kesintisi **olmayacak**.

- [x] **B2. Linux kullanıcı** — `tucibeyin` (yeni VPS'te mevcut). ✓

- [x] **B3. Erişim** — SSH + sudo var. ✓

- [ ] **B4. Bakım penceresi / zamanlama** — DNS TTL'i ne zaman düşürelim, cutover ne zaman? → _______

---

## BÖLÜM C — Yeni VPS Temel Kurulum (yeni VPS'te)

> nginx / postgresql / python3 / pip / ufw / rsync ZATEN kurulu (teqlif taşınırken gelmiş).
> Eksik olan tek şey: **certbot**. C2/C4 gereksiz (kullanıcı + firewall hazır).

- [x] **C3. Eksik paketler** — ✅ certbot 4.0.0 + python3-certbot-nginx + python3-venv kuruldu
  (git zaten vardı). `certbot.timer` otomatik etkinleşti. `options-ssl-nginx.conf` +
  `ssl-dhparams.pem` mevcut. **`certbot certificates` → `thevetaris.com` GEÇERLİ (64 gün,
  ECDSA, thevetaris.com + www)** — account+archive+renewal hepsi tam. SSL tamamen hazır,
  H1 karşılandı. Kalan tek SSL işi: DNS sonrası `renew --dry-run` (H2).

---

## BÖLÜM D — Kod & Uygulama (yeni VPS'te, `tucibeyin` kullanıcısı ile)

- [x] **D1. Dizin + clone** — ✅ `/var/www/thevetaris.com` (sahip `tucibeyin`), HEAD `0092efd`
  (local ile aynı). Not: repo'daki `.env` placeholder (DB_PASS boş) → D3'te gerçek değerlerle ezilecek.

- [x] **D2. venv + bağımlılıklar** — ✅ `bcrypt 5.0.0`, `psycopg2-binary 2.9.12`,
  `python-dotenv 1.2.3` kuruldu. (bcrypt sürüm farkı sorun değil — hash uyumlu.)

- [x] **D3. `.env`** — ✅ Eski VPS'ten kopyalandı, `chmod 600`, 5 satır dolu.

- [x] **D4. `public/` senkron** — ✅ tar-over-ssh ile çekildi (rsync iki uçta da yoktu):
  `ssh eski 'tar -C /var/www/thevetaris.com -czf - public' | tar -C /var/www/thevetaris.com -xzf -`
  Sonuç: `public/` 26 MB, `images/` 18 dosya, `videos/video.mp4` 6.16 MB. ✓

---

## BÖLÜM E — Veritabanı Taşıma

- [x] **E1. Eski VPS dump** — ✅ `/tmp/vetaris.dump` 17K. **Referans sayılar:**
  `products=3, orders=0, order_items=0, users=2, posts=1`.

- [x] **E2. Dump transferi** — ✅ Yeni VPS'e `scp` ile çekildi (`/tmp/vetaris.dump`, 17K).

- [x] **E3. DB kullanıcısı + veritabanı** — `vetaris` DB + `tucibeyin` rolü yeni VPS'te zaten
  vardı ama DB **boştu** (tablo yok). Yeni oluşturmak gerekmedi.

- [x] **E4. Parola eşitleme + restore** — ✅ `ALTER USER tucibeyin WITH PASSWORD` (`.env` ile
  eşitlendi) → `pg_restore -d vetaris --no-owner --role=tucibeyin` hatasız.

- [x] **E5. Doğrulama** — ✅ Sayılar birebir: `products=3, orders=0, order_items=0, users=2,
  posts=1`. TCP+parola auth (uygulamanın yolu, `127.0.0.1`) da çalışıyor.

---

## BÖLÜM F — systemd Servisi (yeni VPS'te)

- [x] **F1. Unit dosyası** — ✅ `/etc/systemd/system/vetaris.service` yazıldı (`After`/`Requires
  postgresql.service` + `RestartSec=3` eklendi).

- [x] **F2. Etkinleştir + başlat** — ✅ `active (running)`, enabled. Log: "Database initialized
  successfully" (parola auth çalışıyor).

- [x] **F3. Lokal test** — ✅ `127.0.0.1:8801/` → 200 OK; `/api/products` → 3 ürün
  (Türkçe isimler + `/images/FORMÜL-A.jpg` yolları) döndü. (8801 `0.0.0.0` dinliyor ama
  ufw'de açık değil → dışarıdan erişilemez, sadece nginx.)

---

## BÖLÜM G — Nginx (tam SSL'li — sertifika zaten var)

- [x] **G1. Config** — ✅ `/etc/nginx/sites-available/thevetaris` yazıldı (eski VPS yapısının aynısı).

- [x] **G2. Etkinleştir** — ✅ symlink eklendi, `nginx -t` OK, reload. teqlif etkilenmedi (200).

- [x] **G3. DNS'siz test** — ✅ Yeni VPS'ten: 443→200, `/api/products` 3 ürün, 80→301.
  Mac'ten gerçek IP + SNI ile: 200, `<title>Vetaris | Hayvansal Destek Ürünleri</title>`,
  sertifika hatası yok. **Yeni VPS fonksiyonel olarak hazır.**

---

## BÖLÜM H — SSL doğrulama

- [x] **H1. Sertifika + certbot durumu** — ✅ C3'te doğrulandı: `certbot certificates` →
  `thevetaris.com` VALID (64 gün). Account/archive/renewal tam.

- [ ] **H2. Yenileme testi** — DNS geçişinden ÖNCE `--dry-run` başarısız olur (HTTP-01 hâlâ
  eski VPS'e gider); **DNS geçişinden SONRA** çalıştır:
  ```bash
  sudo certbot renew --dry-run
  sudo systemctl status certbot.timer --no-pager
  ```

---

## BÖLÜM I — DNS Geçişi (Squarespace paneli)

- [x] **I1. TTL / kayıt tespiti** — apex A TTL 3600, AAAA yok, `www` CNAME→apex.
  Squarespace'te **2 adet** apex A kaydı var (`@` + `thevetaris.com`, ikisi de aynı IP).

- [x] **I2. Ön test** — `/etc/hosts` ile yapıldı (J-ön), hepsi OK.

- [x] **I3. Kayıtları değiştir** — ✅ Squarespace'te her iki apex A kaydı da
  `51.81.34.27` → `135.125.175.223`. `www`/MX/TXT/NS'e dokunulmadı.

- [x] **I4. Yayılma** — ✅ Anında: authoritative + 8.8.8.8 + 1.1.1.1 hepsi `135.125.175.223`.

- [x] **I5. Canlı** — ✅ `https://thevetaris.com` 200, title doğru, `/api/products` OK.

---

## BÖLÜM J — Doğrulama

- [x] **J-ön (`/etc/hosts` ile, DNS öncesi)** — ✅ Kullanıcı tarayıcıdan tam gezinme testi
  yaptı: ana sayfa/görsel/video/favicon, ürün detay (Türkçe görseller), giriş/çıkış,
  sepet→sipariş, admin panel (ürün/blog ekleme), sertifika kilidi — **HEPSİ OK**.

- [x] **J-son (gerçek DNS)** — ✅ `https://thevetaris.com` 200 + title + `/api/products`.
  `certbot renew --dry-run` → **thevetaris.com (success)**. Otomatik yenileme çalışıyor.
  Kalan küçük kontrol: `curl -sI http://thevetaris.com` → 301 (kozmetik).

- [x] **Yan bulgu — yeni VPS'te 10 ARTIK renewal conf** — `certbot renew --dry-run` diğer 10
  domain için FAIL veriyor (DNS'leri hâlâ eski VPS'te). Vetaris'i ETKİLEMEZ.
  **Karar: temizlik YAPILMAYACAK** — o siteler de yeni VPS'e taşınacak, conf'lar lazım olacak.
  Her site taşındıkça kendi FAIL'i düzelir.

---

## BÖLÜM K — Repo Güncellemeleri

- [x] **K1.** `deploy/vetaris.service` → gerçek deploy'a göre güncellendi (User=tucibeyin,
  /var/www/thevetaris.com, postgresql bağımlılığı, RestartSec).
- [x] **K2.** `deploy/vetaris_nginx.conf` → tam SSL'li (443 + certbot bloğu + HTTP→HTTPS 301).
- [x] **K3.** `deploy/deploy.md` + `deploy/task.md` → gerçekleşen adımlar işlendi.
- [ ] **K4.** commit + push (`main`) — kullanıcı onayı bekliyor.

---

## BÖLÜM L — Eski VPS'te thevetaris'i Kaldırma

- [x] **L1. Final `pg_dump`** — GEREK YOK. Site trafiği sıfır, geçiş penceresinde yazma olmadı.
  (Gerekirse: `sudo -u postgres pg_dump -Fc vetaris -f ~/vetaris-final.dump`)

- [ ] **L2. (Hazır olunca)** Eski VPS'te SADECE vetaris'i kaldır — **nginx'i DURDURMA**:
  ```bash
  sudo systemctl disable --now vetaris.service
  sudo rm /etc/nginx/sites-enabled/thevetaris
  sudo nginx -t && sudo systemctl reload nginx
  # sonra istege bagli: sudo -u postgres dropdb vetaris ; sudo rm -rf /var/www/thevetaris.com
  # certbot: sudo certbot delete --cert-name thevetaris.com  (eski VPS'te; yeni VPS'te KALSIN)
  ```

- [ ] **L3.** TTL'i normale çıkarmak istersen Squarespace'te apex A → 3600 (opsiyonel, zaten 3600).

---

## Rollback (her an)

| Sorun | Aksiyon |
|---|---|
| Yeni site açılmıyor | Squarespace apex `A` kaydını `51.81.34.27`'ye geri al (~5 dk, TTL 300) |
| SSL hatası | Sertifika zaten kopya olarak yeni VPS'te; nginx config'i kontrol et. Çözülmezse DNS geri al |
| DB eksik/bozuk | `sudo -u postgres dropdb vetaris && sudo -u postgres createdb -O <DB_USER> vetaris` → E4 tekrar |
| Görsel eksik | `rsync` ile `public/` tekrar |

Eski VPS L2'ye kadar hep ayakta → rollback garantili.
