# Ortak Defter

İki ortağın günlük gelir ve giderlerini, fişleriyle birlikte tuttuğu küçük bir web uygulaması.

- **Günlük kayıt:** yakıt, yevmiye, yemek, ek gider... Tutar, kategori, kim ödedi, fiş fotoğrafı. Telefondan fişi çekip doğrudan eklenebilir.
- **Gelir kaydı:** parayı kimin aldığıyla birlikte.
- **Sabit giderler:** leasing, kira gibi aylık ödemeler. Taksitler her ay kendiliğinden açılır; günü yaklaşınca sayfada uyarı ve e-posta gelir.
- **Ortak hesabı:** kim cebinden ne ödedi, kim ne aldı, sonuçta kim kime ne kadar borçlu.
- **Rapor:** aylık kâr/zarar, giderin kategorilere dağılımı, son 12 ayın seyri, gün gün döküm.
- **Döküm:** muhasebeci için Excel (çok sayfalı) ve CSV.

Teknik: Python 3.11+, FastAPI, SQLAlchemy, SQLite, Jinja2 şablonları. Ayrı bir ön yüz derlemesi ya da dış servis yok; tek süreç, tek veri klasörü.

## Bilgisayarda denemek

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

<http://localhost:8000> adresini açın. İlk açılışta iki ortağın adını, e-postasını ve şifresini soran kurulum sayfası gelir.

Dolu bir defter görmek isterseniz örnek veriyle ayrı bir klasörde açın:

```bash
DATA_DIR=./deneme-veri python scripts/ornek_veri.py
DATA_DIR=./deneme-veri uvicorn app.main:app
# giriş: fatma@example.com / deneme-1234
```

## Sunucuya kurmak (Docker + otomatik HTTPS)

Gerekenler: Docker kurulu bir sunucu ve sunucunun IP adresine yönlendirilmiş bir alan adı.

```bash
cp .env.example .env                               # DOMAIN, BASE_URL ve (isterseniz) SMTP bilgilerini doldurun
mkdir -p veri && sudo chown -R 10001:10001 veri    # uygulama kapsayıcıda bu kullanıcıyla çalışır
docker compose up -d --build
```

`chown` adımı atlanırsa uygulama veri klasörüne yazamaz ve "Veri klasörüne yazılamıyor" diyerek açılmaz.

Caddy alan adı için sertifikayı kendisi alır. Site açılınca **hemen kurulum sayfasını doldurun**: ilk gelen kişi ortak hesaplarını oluşturur, sonrasında kurulum sayfası kapanır.

Veritabanı ve fişler `./veri` klasöründe durur. Güncelleme için yeni dosyaları kopyalayıp `docker compose up -d --build` demek yeterli; veri klasörüne dokunulmaz.

> Bu kurulum dosyaları (Dockerfile, docker-compose, Caddyfile) yazıldı ama Docker ile çalıştırılarak denenmedi; uygulamanın kendisi doğrudan `uvicorn` ile denendi. İlk kurulumda `docker compose logs -f` ile bakın.

### Docker'sız

Uygulamayı bir kullanıcı altında çalıştırıp önüne Nginx ya da Caddy koyun:

```bash
DATA_DIR=/var/lib/ortak-defter uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers
```

Dikkat edilecekler:

- **Tek süreç** çalıştırın (`--workers` vermeyin). Hatırlatma döngüsü ve giriş deneme sınırı süreç içinde tutulur.
- Ters vekil `Host` başlığını olduğu gibi iletmeli (Nginx: `proxy_set_header Host $host;`). Başka siteden gelen form gönderimleri buna bakılarak reddedilir.
- Vekil gerçek ziyaretçi adresini de iletmeli (Nginx: `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` ve `proxy_set_header X-Forwarded-Proto $scheme;`). Yoksa hatalı giriş sınırı herkesi tek adres sayar ve birkaç yanlış şifre iki ortağı da 15 dakika kilitler.
- Vekilde yükleme sınırını açın (Nginx: `client_max_body_size 150m;`).
- HTTPS'te `HTTPS_ONLY=1` yapın.

## Ayarlar (`.env`)

| Değişken | Ne işe yarar | Varsayılan |
|---|---|---|
| `APP_NAME` | Üstte görünen ad | Ortak Defter |
| `BASE_URL` | E-postalardaki bağlantının adresi | http://localhost:8000 |
| `HTTPS_ONLY` | Oturum çerezi yalnızca HTTPS'te gitsin | 0 |
| `DATA_DIR` | Veritabanı ve fişlerin klasörü | ./data |
| `TZ_NAME` | Saat dilimi | Europe/Istanbul |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TLS` | E-posta sunucusu | boş (kapalı) |
| `REMINDER_HOUR` | Hatırlatmaların gideceği en erken saat | 9 |
| `REMINDERS_ENABLED` | Hatırlatmaları aç/kapat | 1 |
| `MAX_UPLOAD_MB` | Dosya başına yükleme sınırı | 15 |
| `SECRET_KEY` | Oturum imza anahtarı | ilk açılışta üretilir, veri klasöründe saklanır |

### E-posta hatırlatmaları

Herhangi bir SMTP hesabı olur. Gmail için örnek (hesapta iki adımlı doğrulama açıkken "uygulama şifresi" üretmeniz gerekir):

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=adres@gmail.com
SMTP_PASSWORD=uygulama-sifresi
SMTP_FROM=Ortak Defter <adres@gmail.com>
SMTP_TLS=starttls
```

Uygulamayı yeniden başlattıktan sonra **Ayarlar > E-posta hatırlatmaları > Bana deneme e-postası gönder** ile sınayın.

Hatırlatma kuralı, her sabit gider için ayrı:

1. Vadeye "kaç gün önce hatırlatılsın" süresi kadar kala bir kez,
2. vade günü bir kez,
3. ödeme geciktiyse, "ödendi" işaretlenene kadar haftada bir.

Aynı gün birden fazla ödeme varsa tek e-postada toplanır. Ayarlar'da bildirimi açık olan ortaklara gider. SMTP tanımlı değilse uyarılar yalnızca "Bugün" ve "Sabit giderler" sayfalarında görünür.

## Ortak hesabı nasıl hesaplanıyor?

Her kayıtta "kim ödedi / parayı kim aldı" seçilir: ortaklardan biri ya da **Ortak hesap** (şirket hesabı, kasa).

- Bir ortağın **cebinden çıkan net** = ödediği giderler − teslim aldığı gelirler.
- İki ortağın cebinden dönen toplam, ortaklık payına göre (varsayılan %50 / %50) bölüşülür: bu "payına düşen"dir.
- Cebinden payına düşenden fazla çıkan ortak **alacaklı**, az çıkan **borçlu** olur.
- Ortakların birbirine yaptığı ödemeler ("Bu ödeme yapıldı, kaydet") bakiyeyi kapatır.
- "Ortak hesap" seçilen kayıtlar kimsenin cebinden çıkmadığı için bu hesaba girmez; kâr/zarar raporuna ise girer.

Örnek: Ortak A 1.000 ₺ yakıtı cebinden ödedi. Payına düşen 500 ₺ olduğu için ortak B, A'ya 500 ₺ borçlu görünür. B 500 ₺ gönderip kaydedince hesap denkleşir.

Tutarlar veritabanında kuruş olarak (tam sayı) tutulur; bölüşümde kuruş kaybolmaz.

## Sabit gider eklerken

"Sıradaki ödeme tarihi"ne **bundan sonraki ilk taksitin** tarihini, "kalan taksit sayısı"na o tarihten itibaren kalan taksiti yazın (kira gibi süresizse boş bırakın). Geçmişte ödenmiş taksitleri girmek gerekmez. Taksit tutarı ay ay değişiyorsa, ödendi işaretlerken gerçek ödenen tutarı yazabilirsiniz.

Yanlış işaretlenen bir ödemeyi geri almak için oluşan gider kaydını açıp silin; taksit yeniden "ödenecekler"e döner.

## Fişler

- Fotoğraf (JPG, PNG, WEBP, HEIC) ve PDF kabul edilir; kayıt başına en çok 8 dosya.
- Fotoğraflar yüklenirken en uzun kenarı 2000 piksele küçültülür ve JPG'ye çevrilir (telefonun 8-10 MB'lık çekimi birkaç yüz KB'a iner). Çekim konumu gibi EXIF bilgileri atılır. Özgün dosya saklanmaz.
- Dosyalar `DATA_DIR/fisler/yıl/ay/` altında durur ve yalnızca giriş yapmış ortaklara gösterilir.

## Yedek

Her şey tek klasörde: `defter.db` (veritabanı) ve `fisler/` (dosyalar).

```bash
scripts/yedekle.sh ./veri ./yedekler      # uygulama çalışırken de güvenle alınır
```

Bunu sunucuda günlük bir `cron` işi yapıp yedekleri başka bir yere kopyalamanızı öneririm. Geri yüklemek için uygulamayı durdurup iki parçayı veri klasörüne geri koyun.

## Testler

```bash
pip install -r requirements-dev.txt
pytest
```

Tutar okuma, ortak bakiyesi, taksit üretimi, hatırlatma kuralları ve sayfa akışları (kayıt + fiş, ödeme, döküm) sınanır.

## Klasörler

```
app/
  main.py            uygulama, ara katmanlar, hata sayfaları
  config.py          .env ayarları
  models.py          tablolar
  money.py           tutar okuma / yazma (kuruş)
  security.py        şifre, oturum, başka siteden gelen istek koruması
  routers/           sayfalar: auth, dashboard, transactions, fixed, partners, reports, settings
  services/          hesap mantığı: balance, fixed, reports, exports, reminders, receipts
  templates/, static/
scripts/             ornek_veri.py, yedekle.sh, sifre_sifirla.py
tests/
```

## Bilinen sınırlar

- İki ortak için tasarlandı. Hesap mantığı daha fazla ortağı kaldırır ama kurulum sayfası iki kişi tanımlar; üçüncü kişi ve "yalnızca görebilen" muhasebeci hesabı yok.
- Veritabanı şeması değişirse otomatik geçiş (migration) aracı yok; tablolar ilk açılışta oluşturulur. Şemaya dokunacak bir geliştirmede Alembic eklemek gerekir.
- Çıkış yapmak yalnızca o cihazdaki oturumu kapatır. Bir cihaz kaybolursa şifreyi değiştirin: şifre değişince diğer bütün cihazlardaki oturumlar düşer.
- "Şifremi unuttum" e-postası yok. Şifresini unutan ortak için sunucuda `python scripts/sifre_sifirla.py ortak@ornek.com` çalıştırılır (Docker: `docker compose exec defter python scripts/sifre_sifirla.py ...`).
- KDV ayrıştırma, fişten otomatik okuma ve araç/iş bazında takip bu sürümde yok.
