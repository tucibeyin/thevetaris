# Vetaris — VPS Taşıma Planı (51.81.34.27 → 135.125.175.223)

> Amaç: `thevetaris.com` sitesini eski VPS'ten yeni VPS'e, SSL sertifikaları + Nginx +
> systemd + PostgreSQL verisi dahil olmak üzere kesintiyi en aza indirerek taşımak.
>
> **Bu dosya önce birlikte gözden geçirilecek, sonra uygulanacak.** Aşağıdaki
> "Doğrulanacaklar" bölümündeki bilgiler netleşmeden geçişe başlama.

---

## 1. Mevcut Durum Analizi

### 1.1 Eski VPS (51.81.34.27)
```
/var/www/thevetaris.com/
├── deploy/          # systemd + nginx örnek dosyaları (repo içinde)
├── monitor.sh       # journalctl -u vetaris.service -f
├── public/          # statik frontend (html/css/js/images)
├── requirements.txt # psycopg2-binary, bcrypt, python-dotenv
├── seed_admin.py    # admin@vetaris.com / admin  (ilk kurulum)
├── src/             # server.py (http.server, PORT=8801), database.py
└── venv/            # Python sanal ortamı (repo'da yok, .gitignore'da)
```

### 1.2 Uygulama mimarisi
- **Backend:** saf Python `http.server` (framework yok), `src/server.py`, **port 8801**,
  `127.0.0.1` üzerinde dinliyor; Nginx reverse proxy ile 80/443'ten proxy'leniyor.
- **DB:** PostgreSQL, lokal (`DB_HOST=localhost`), veritabanı adı `vetaris`.
  Sunucudaki gerçek `.env` içinde `DB_USER` ve `DB_PASS` **dolu** → **parolalı auth**
  (md5/scram). Yeni VPS'te de aynı kullanıcı adı + aynı parola ile kurulacak ki kod
  değişmeden çalışsın. (Repo'daki örnek `.env` yanıltıcı: `DB_USER=tucibeyin`, `DB_PASS=` boş —
  gerçek değerler sunucudaki `.env`'de.)
- **Şema:** `src/database.py` içindeki `init_db()` tüm tabloları `CREATE TABLE IF NOT EXISTS`
  ile açılışta oluşturuyor: `users, sessions, products, orders, order_items, blog_posts`.
- **Statik dosyalar:** `public/` klasöründen doğrudan servis ediliyor (Range request desteği
  video için var). Ürün görselleri `public/images/` içinde **veya** admin panelinden elle
  girilen URL'ler ile (`/api/upload` endpoint'i sadece stub, gerçek dosya yükleme YOK).
- **Disk'e yazma yok:** `database.py` diske hiçbir şey yazmıyor. Kalıcı durum **sadece
  PostgreSQL'de**. Yani taşınması gereken tek "canlı veri" → Postgres dump'ı.

### 1.3 Git deposu
- Repo: `https://github.com/tucibeyin/Vetaris.git`, branch `main`.
- `.gitignore`: `venv/`, `.env`, `*.log`, `__pycache__/` → bunlar repoda YOK, elle taşınacak/yeniden oluşturulacak.

### 1.4 Repo'daki deploy dosyaları ile gerçek kurulum arasındaki TUTARSIZLIKLAR (düzeltilecek)
| Dosya | Repo'daki değer | Gerçek/Doğru değer |
|---|---|---|
| `deploy/vetaris.service` → `WorkingDirectory` | `/var/www/vetaris.com` | `/var/www/thevetaris.com` |
| `deploy/vetaris.service` → `User`/`Group` | `debian` | `tucibeyin` (yeni VPS'te ne olacaksa) |
| `deploy/vetaris.service` → `ExecStart` | `.../python3 src/server.py` | `WorkingDirectory` doğruysa OK |
| `deploy/vetaris_nginx.conf` | sadece `listen 80` | SSL bloğu certbot ekleyecek |

> Not: `server_name thevetaris.com www.thevetaris.com` repo'da doğru.

### 1.5 Domain / DNS
- Domain yönetimi **Squarespace** (Google Domains'ten devralınan panel).
- Şu an A kaydı → `51.81.34.27`. Geçişte → `135.125.175.223` yapılacak.
- `www` için A veya CNAME kaydı da güncellenecek.

---

## 2. Doğrulanacaklar (geçişten ÖNCE eski VPS'te çalıştır)

```bash
# --- İşletim sistemi / sürümler ---
cat /etc/os-release
python3 --version
psql --version
nginx -v

# --- SSL: certbot kullanılıyor mu, hangi sertifikalar var? ---
sudo certbot certificates 2>/dev/null || ls -la /etc/letsencrypt/live/ 2>/dev/null
sudo systemctl list-timers | grep -i certbot

# --- Nginx: gerçekte aktif olan config ---
ls -la /etc/nginx/sites-enabled/
sudo nginx -T | grep -E "server_name|proxy_pass|listen|ssl_certificate" 

# --- systemd servis: gerçek unit dosyası ---
systemctl cat vetaris.service
systemctl status vetaris.service --no-pager

# --- PostgreSQL: sürüm, auth yöntemi, DB boyutu ---
sudo -u postgres psql -c "\l+" | grep -i vetaris
sudo -u postgres psql -c "\du"
sudo cat /etc/postgresql/*/main/pg_hba.conf | grep -v '^#' | grep -v '^$'

# --- .env gerçek içeriği ---
cat /var/www/thevetaris.com/.env

# --- public/images altında git'te OLMAYAN dosya var mı? (elle yüklenmiş görseller) ---
cd /var/www/thevetaris.com && git status --porcelain public/ && git ls-files public/images/

# --- cron / ek servisler / firewall ---
crontab -l; sudo crontab -l
sudo ufw status verbose
```

**Bu çıktıları paylaş → planı kesinleştirelim.**

---

## 3. Taşıma Envanteri

| Öğe | Kaynak | Yöntem |
|---|---|---|
| Uygulama kodu | GitHub `main` | Yeni VPS'te `git clone` |
| Python bağımlılıkları | `requirements.txt` | Yeni VPS'te `pip install` (venv yeniden) |
| `.env` | Eski VPS `/var/www/thevetaris.com/.env` | `scp` ile kopyala (veya elle yaz) |
| PostgreSQL verisi | Eski VPS `vetaris` DB | `pg_dump` → `scp` → `pg_restore` |
| `public/images/` elle yüklenenler | Eski VPS | `rsync` (git'te olmayan varsa) |
| Nginx config | `/etc/nginx/sites-available/` | Yeniden oluştur (repo'daki + certbot) |
| systemd unit | `/etc/systemd/system/vetaris.service` | Yeniden oluştur (düzeltilmiş) |
| SSL sertifikası | `/etc/letsencrypt/` | **Seçenek A:** yeni VPS'te certbot ile yeniden al (önerilen) / **Seçenek B:** `/etc/letsencrypt` dizinini kopyala |
| DNS | Squarespace | A/AAAA/`www` kayıtlarını yeni IP'ye çevir |

---

## 4. Adım Adım Geçiş

### Aşama 0 — Hazırlık (kesintisiz, DNS'e dokunmadan)

#### 0.1 Yeni VPS temel kurulum (135.125.175.223)
```bash
# root veya sudo'lu kullanıcı ile
adduser tucibeyin && usermod -aG sudo tucibeyin   # eski VPS ile aynı kullanıcı adı
apt update && apt upgrade -y
apt install -y git nginx postgresql postgresql-contrib python3 python3-venv python3-pip \
               certbot python3-certbot-nginx ufw rsync

# Firewall
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

#### 0.2 Kod
```bash
sudo mkdir -p /var/www/thevetaris.com
sudo chown tucibeyin:tucibeyin /var/www/thevetaris.com
git clone https://github.com/tucibeyin/Vetaris.git /var/www/thevetaris.com
cd /var/www/thevetaris.com
```

#### 0.3 Python venv
```bash
cd /var/www/thevetaris.com
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

#### 0.4 `.env`
```bash
# Eski VPS'ten kopyala (yerel makinenden):
scp tucibeyin@51.81.34.27:/var/www/thevetaris.com/.env /tmp/vetaris.env
scp /tmp/vetaris.env tucibeyin@135.125.175.223:/var/www/thevetaris.com/.env
# VEYA elle oluştur (mevcut içerik):
#   DB_HOST=localhost
#   DB_NAME=vetaris
#   DB_USER=tucibeyin
#   DB_PASS=            <-- parolalı auth'a geçersek burayı doldur
#   DB_PORT=5432
chmod 600 /var/www/thevetaris.com/.env
```

#### 0.5 PostgreSQL — kullanıcı + boş veritabanı
> `<DB_USER>` ve `<DB_PASS>` = sunucudaki `.env` içindeki gerçek değerler. Aynısını kullan.
```bash
sudo -u postgres psql <<SQL
CREATE USER "<DB_USER>" WITH PASSWORD '<DB_PASS>';
CREATE DATABASE vetaris OWNER "<DB_USER>";
GRANT ALL PRIVILEGES ON DATABASE vetaris TO "<DB_USER>";
SQL
```
> Eski VPS parolalı auth kullanıyor (`.env`'de `DB_USER`/`DB_PASS` dolu). Yeni VPS'te de
> **birebir aynı kullanıcı adı + parola** → kod ve `.env` hiç değişmez. Debian/Ubuntu'da
> `pg_hba.conf` zaten yerel bağlantılar için `scram-sha-256`/`md5` verir; ekstra ayar gerekmez.
> `.env` dosyasını eski VPS'ten olduğu gibi kopyalaman yeterli.

#### 0.6 Veritabanı dump + restore
```bash
# --- Eski VPS'te (parola .env'den) ---
export PGPASSWORD='<DB_PASS>'
pg_dump -U '<DB_USER>' -h localhost -Fc -d vetaris -f /tmp/vetaris.dump
#   Alternatif (en garanti):  sudo -u postgres pg_dump -Fc vetaris -f /tmp/vetaris.dump

# --- Yerel makineye çek, yeni VPS'e at ---
scp tucibeyin@51.81.34.27:/tmp/vetaris.dump /tmp/vetaris.dump
scp /tmp/vetaris.dump tucibeyin@135.125.175.223:/tmp/vetaris.dump

# --- Yeni VPS'te restore ---
export PGPASSWORD='<DB_PASS>'
pg_restore -U '<DB_USER>' -h localhost -d vetaris --no-owner --role='<DB_USER>' /tmp/vetaris.dump
#   Alternatif:  sudo -u postgres pg_restore -d vetaris --no-owner --role='<DB_USER>' /tmp/vetaris.dump

# Doğrula
psql -U '<DB_USER>' -h localhost -d vetaris -c "\dt"
psql -U '<DB_USER>' -h localhost -d vetaris -c "SELECT count(*) FROM products;"
psql -U '<DB_USER>' -h localhost -d vetaris -c "SELECT count(*) FROM orders;"
psql -U '<DB_USER>' -h localhost -d vetaris -c "SELECT count(*) FROM users;"
```
> `init_db()` zaten tabloları açar; ama dump'ı restore etmek verinin de gelmesini sağlar.
> Sıralama önemli değil (IF NOT EXISTS), yine de restore'u servis başlamadan önce yap.

#### 0.7 Elle yüklenmiş görseller (varsa)
```bash
# 2. bölümdeki git kontrolünde public/images altında git'te olmayan dosya çıktıysa:
rsync -avz tucibeyin@51.81.34.27:/var/www/thevetaris.com/public/images/ \
           tucibeyin@135.125.175.223:/var/www/thevetaris.com/public/images/
```

#### 0.8 systemd servis (DÜZELTİLMİŞ)
`/etc/systemd/system/vetaris.service`:
```ini
[Unit]
Description=Vetaris E-Commerce Python Server
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=tucibeyin
Group=tucibeyin
WorkingDirectory=/var/www/thevetaris.com
ExecStart=/var/www/thevetaris.com/venv/bin/python3 src/server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vetaris.service
sudo systemctl status vetaris.service --no-pager
curl -I http://127.0.0.1:8801/          # 200 beklenir
```
> İstersen `deploy/vetaris.service` dosyasını da repoda bu içerikle güncelleyelim (ayrı commit).

#### 0.9 Nginx (önce HTTP, SSL'i certbot ekleyecek)
`/etc/nginx/sites-available/thevetaris.com`:
```nginx
server {
    listen 80;
    listen [::]:80;
    server_name thevetaris.com www.thevetaris.com;

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:8801;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/thevetaris.com /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

#### 0.10 SSL sertifikası

**Seçenek A — Yeni VPS'te yeniden al (ÖNERİLEN, en temiz):**
DNS henüz eski sunucuyu gösterdiği için `--nginx` doğrulaması geçmez. İki alt yol:

- **A1 (kesintisiz):** DNS TTL'i düşür (Aşama 1.1), DNS'i çevir, yayılınca:
  ```bash
  sudo certbot --nginx -d thevetaris.com -d www.thevetaris.com
  ```
  Bu sırada birkaç dakika HTTPS uyarısı olabilir (kısa kesinti penceresi).

- **A2 (kesintisiz, önceden):** DNS çevirmeden, DNS-01 doğrulaması ile önceden al:
  ```bash
  sudo certbot certonly --manual --preferred-challenges dns \
    -d thevetaris.com -d www.thevetaris.com
  # Squarespace DNS'e verilen TXT kaydını ekle, doğrulat.
  ```
  Sonra Nginx SSL bloğunu elle ekle (aşağıdaki tam config).

**Seçenek B — Eski sertifikaları kopyala (hızlı, geçici):**
```bash
sudo rsync -avz tucibeyin@51.81.34.27:/etc/letsencrypt/ /etc/letsencrypt/   # sudo gerektirir
sudo systemctl enable --now certbot.timer    # sonraki yenilemeler yeni VPS'te
```
> Sertifika dosya bazlı olduğu için kopyalama çalışır; ama yenileme (renew) DNS yeni VPS'i
> gösterene kadar başarısız olur. DNS çevrildikten sonra `sudo certbot renew --dry-run` ile test et.

**SSL'li tam Nginx config** (certbot `--nginx` genelde otomatik ekler; elle gerekirse):
```nginx
server {
    listen 80;
    listen [::]:80;
    server_name thevetaris.com www.thevetaris.com;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name thevetaris.com www.thevetaris.com;

    ssl_certificate     /etc/letsencrypt/live/thevetaris.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/thevetaris.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:8801;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 0.11 DNS çevirmeden yeni sunucuyu test et
Yerel makinede `/etc/hosts`'a geçici satır:
```
135.125.175.223  thevetaris.com www.thevetaris.com
```
Tarayıcıdan / `curl -I https://thevetaris.com` ile kontrol et: ana sayfa, ürün listesi
(`/api/products`), admin girişi, blog. Sonra `/etc/hosts` satırını sil.

---

### Aşama 1 — DNS Geçişi (kısa kesinti penceresi)

#### 1.1 Önceden (geçişten ~24 saat önce)
- Squarespace DNS panelinde A / `www` kayıtlarının **TTL'ini 300 sn** (veya en düşük) yap.

#### 1.2 Geçiş anı
- Eski VPS hâlâ ayakta ve çalışıyor olsun (rollback için).
- Squarespace DNS:
  - `@` (A) → `135.125.175.223`
  - `www` (A veya CNAME) → `135.125.175.223` / `thevetaris.com`
  - Varsa AAAA (IPv6) kaydını yeni VPS IPv6'sı ile güncelle veya sil.
- Yayılmayı izle: `dig +short thevetaris.com @8.8.8.8`, `dig +short thevetaris.com @1.1.1.1`

#### 1.3 DNS yayılınca
```bash
# Yeni VPS'te (Seçenek A1 seçtiysek):
sudo certbot --nginx -d thevetaris.com -d www.thevetaris.com
sudo systemctl reload nginx
```

---

### Aşama 2 — Doğrulama (yeni VPS canlı)

```bash
curl -I  https://thevetaris.com
curl -sI http://thevetaris.com            # 301 → https
curl -s  https://thevetaris.com/api/products | head -c 300
```
Tarayıcıdan manuel kontrol:
- [ ] Ana sayfa + görseller (favicon dahil)
- [ ] Ürün listesi ve ürün detay (`product.html`)
- [ ] Türkçe karakterli dosya yolları (yakın zamanda düzeltildi — commit `233dabe`)
- [ ] Video bölümü (Range request)
- [ ] Kayıt / giriş / çıkış (cookie tabanlı session)
- [ ] Sepet + sipariş oluşturma → DB'ye yazıyor mu
- [ ] Admin panel (`/admin.html`) — ürün ekle/güncelle/sil, sipariş durumu, blog
- [ ] `SELECT count(*)` sayıları eski VPS ile aynı mı
- [ ] `sudo certbot renew --dry-run`
- [ ] `journalctl -u vetaris.service -f` — hata yok

---

### Aşama 3 — Eski VPS Devre Dışı

> DNS geçişinden **en az 48–72 saat sonra**, yeni sunucu sorunsuz çalışıyorsa.

1. Son bir `pg_dump` al, güvenli yerde sakla (yedek).
2. Eski VPS'te `vetaris.service` ve `nginx`'i durdur.
3. 1 hafta bekle, sonra eski VPS'i imha et / provider'da iptal et.
4. Squarespace DNS TTL'ini normale (3600) çıkar.

---

## 5. Rollback Planı

| Sorun | Aksiyon |
|---|---|
| Yeni VPS'te site açılmıyor | Squarespace DNS'i `51.81.34.27`'ye geri al (TTL 300 olduğu için ~5 dk) |
| SSL hatası | Geçici olarak Seçenek B (eski sertifikaları kopyala) veya DNS geri al |
| DB verisi eksik/bozuk | Servisi durdur, `dropdb vetaris && createdb`, temiz `pg_restore`, tekrar |
| Sadece bazı görseller yok | `rsync` ile `public/images/` tekrar senkron |

Eski VPS Aşama 3'e kadar hiç kapatılmadığı için rollback her zaman mümkün.

---

## 6. Riskler / Dikkat

- **DB parola auth:** Eski VPS parolalı auth kullanıyor (`.env`'de `DB_USER`/`DB_PASS` dolu).
  Yeni VPS'te birebir aynı kullanıcı + parola oluştur, `.env`'i aynen kopyala → kodda değişiklik yok.
  `pg_dump`/`restore` `-U <DB_USER> -h localhost` + `PGPASSWORD` ile; takılırsan `sudo -u postgres` ile.
- **`init_db()` her açılışta çalışıyor:** Zararsız (`IF NOT EXISTS`) ama restore'u servis
  başlamadan yap ki tablo/veri çakışması olmasın.
- **`seed_admin.py`:** Yeni kurulumda çalıştırma — DB'yi zaten restore ediyoruz. Sadece admin
  yoksa çalıştır; varsayılan parola `admin` → **canlıda değiştir**.
- **`deploy/` içindeki `.service` ve `.conf` dosyaları güncel değil** (bkz. 1.4). Geçiş
  sonrası repoyu düzeltip commit'leyelim.
- **Squarespace CNAME/A kısıtları:** Bazı Squarespace planlarında apex (`@`) için A kaydı
  yerine yönlendirme zorunlu olabilir; panelde "Custom Records" bölümünü kontrol et.
- **E-posta / MX kayıtları:** Domain'de e-posta varsa MX/TXT(SPF/DKIM) kayıtlarına
  DOKUNMA — sadece A/AAAA/`www` değişecek.
- **Port 8801 dışarı açık olmasın:** Sadece Nginx proxy'lesin; `ufw` ile 8801 kapalı kalsın
  (zaten `server.py` `127.0.0.1` değil `""` dinliyor — Nginx Full dışında 8801 portunu
  ufw'de açma; istersen `server.py`'de bind adresini `127.0.0.1` yapmayı ayrı iş olarak ele alalım).

---

## 7. Hızlı Komut Özeti (yeni VPS, sırayla)

```bash
# 0. paketler
sudo apt update && sudo apt install -y git nginx postgresql postgresql-contrib \
  python3 python3-venv python3-pip certbot python3-certbot-nginx ufw rsync
sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw --force enable

# 1. kod + venv
sudo mkdir -p /var/www/thevetaris.com && sudo chown $USER:$USER /var/www/thevetaris.com
git clone https://github.com/tucibeyin/Vetaris.git /var/www/thevetaris.com
cd /var/www/thevetaris.com
python3 -m venv venv && ./venv/bin/pip install -U pip && ./venv/bin/pip install -r requirements.txt

# 2. .env  (scp veya elle)
scp tucibeyin@51.81.34.27:/var/www/thevetaris.com/.env ./.env && chmod 600 .env

# 3. postgres  (<DB_USER>/<DB_PASS> = .env'deki gerçek değerler)
sudo -u postgres psql -c "CREATE USER \"<DB_USER>\" WITH PASSWORD '<DB_PASS>';"
sudo -u postgres psql -c "CREATE DATABASE vetaris OWNER \"<DB_USER>\";"
# eski VPS: sudo -u postgres pg_dump -Fc vetaris -f /tmp/vetaris.dump  → scp → yeni VPS:
sudo -u postgres pg_restore -d vetaris --no-owner --role='<DB_USER>' /tmp/vetaris.dump

# 4. systemd  (deploy.md 0.8'deki içerik)
sudo nano /etc/systemd/system/vetaris.service
sudo systemctl daemon-reload && sudo systemctl enable --now vetaris.service
curl -I http://127.0.0.1:8801/

# 5. nginx (http)
sudo nano /etc/nginx/sites-available/thevetaris.com
sudo ln -s /etc/nginx/sites-available/thevetaris.com /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# 6. /etc/hosts ile test → sonra DNS çevir → certbot
sudo certbot --nginx -d thevetaris.com -d www.thevetaris.com
sudo certbot renew --dry-run
```
