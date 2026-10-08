# Ortak Defter

İki ortağın günlük gelir ve giderlerini, fişleriyle birlikte tuttuğu küçük bir web uygulaması.

- **Günlük kayıt:** yakıt, yevmiye, yemek, ek gider... Tutar, kategori, kim ödedi, fiş fotoğrafı. Telefondan fişi çekip doğrudan eklenebilir.
- **Gelir kaydı:** parayı kimin aldığıyla birlikte.
- **Sabit giderler:** leasing, kira gibi aylık ödemeler. Taksitler her ay kendiliğinden açılır; günü yaklaşınca sayfada uyarı ve e-posta gelir.
- **Ortak hesabı:** kim cebinden ne ödedi, kim ne aldı, sonuçta kim kime ne kadar borçlu.
- **Rapor:** aylık kâr/zarar, giderin kategorilere dağılımı, son 12 ayın seyri, gün gün döküm.
- **Döküm:** muhasebeci için PDF ve Excel (çok sayfalı).

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

## Buluta kurmak (ortakların telefondan girmesi için)

Uygulamanın iki ihtiyacı var: **kalıcı disk** (veritabanı ve fişler) ve **sürekli açık tek süreç** (hatırlatma e-postaları içeriden gider). Kullanılmayınca uyuyan ya da diski olmayan ücretsiz planlar bu yüzden uymaz.

### Render ile (en kolay, ~7,5 $/ay)

1. [render.com](https://render.com) üzerinde hesap açın, GitHub hesabınızı bağlayın.
2. **New > Blueprint** deyip bu depoyu seçin. Render `render.yaml` dosyasını okur: Frankfurt'ta bir web servisi ve 2 GB disk kurar. Değişkenler (uygulama adı, hatırlatma adresi) dosyada hazır.
3. Kurulum bitince servis sayfasındaki `https://....onrender.com` adresini açın. Kurulum sayfası bir **kurulum anahtarı** sorar: servisin **Environment** sekmesindeki `KURULUM_ANAHTARI` değerini kopyalayıp yapıştırın.
4. İki ortağın adını, e-postasını ve şifresini girin. Defter hazır.
5. E-posta hatırlatmaları için **Environment** sekmesinde `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` değerlerini doldurun.
6. İsterseniz **Settings > Custom Domains** ile `muhasebe.sezkar.com` gibi bir alan adı bağlayın; sertifikayı Render alır.

`main` dalına gönderilen her değişiklik kendiliğinden yayına girer. Telefonda adresi açıp tarayıcı menüsünden **Ana ekrana ekle** deyince uygulama simgesiyle açılır.

### Fly.io ile (en ucuz, ~2 $/ay)

Bilgisayarda [flyctl](https://fly.io/docs/flyctl/install/) gerekir. `fly launch --copy-config --no-deploy`, ardından `fly secrets set KURULUM_ANAHTARI=... REMINDER_TO=info@sezkar.com APP_NAME="Sezkar Muhasebe"` ve `fly deploy --ha=false`. Ayrıntılar `fly.toml` içinde.

### Kendi sunucunuzda (Docker + otomatik HTTPS)

```bash
cp .env.example .env               # DOMAIN, BASE_URL, KURULUM_ANAHTARI ve SMTP bilgilerini doldurun
docker compose up -d --build
```

Caddy alan adı için sertifikayı kendisi alır. Veritabanı ve fişler `./veri` klasöründe durur; kapsayıcı açılışta klasörü kendi kullanıcısına verir, elle `chown` gerekmez. Güncelleme için yeni dosyaları çekip `docker compose up -d --build` demek yeterli.

> Docker, Render ve Fly dosyaları belgelerine göre yazıldı ama bu ortamda çalıştırılarak denenmedi. İlk kurulumda günlüklere bakın.

### Docker'sız

```bash
DATA_DIR=/var/lib/ortak-defter uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers
```

Tek süreç kullanın (`--workers` vermeyin). Ters vekil `Host`, `X-Forwarded-For` ve `X-Forwarded-Proto` başlıklarını iletsin, yükleme sınırını açın (Nginx: `client_max_body_size 150m;`), HTTPS'te `HTTPS_ONLY=1` yapın.

## Ayarlar (`.env`)

| Değişken | Ne işe yarar | Varsayılan |
|---|---|---|
| `APP_NAME` | Sekme başlığında ve e-postalarda görünen ad | Sezkar Muhasebe |
| `BASE_URL` | E-postalardaki bağlantının adresi | Render'da kendiliğinden; yoksa http://localhost:8000 |
| `HTTPS_ONLY` | Oturum çerezi yalnızca HTTPS'te gitsin | 0 |
| `DATA_DIR` | Veritabanı ve fişlerin klasörü | ./data |
| `TZ_NAME` | Saat dilimi | Europe/Istanbul |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TLS` | E-posta sunucusu | boş (kapalı) |
| `REMINDER_HOUR` | Hatırlatmaların gideceği en erken saat | 9 |
| `REMINDERS_ENABLED` | Hatırlatmaları aç/kapat | 1 |
| `REMINDER_TO` | Hatırlatmaların gideceği adres(ler), virgülle ayrılır; boşsa ortakların kendi adresleri | boş |
| `RATES_ENABLED` | TCMB'den günlük euro kuru çekilsin mi | 1 |
| `MAX_UPLOAD_MB` | Dosya başına yükleme sınırı | 15 |
| `SECRET_KEY` | Oturum imza anahtarı | ilk açılışta üretilir, veri klasöründe saklanır |
| `KURULUM_ANAHTARI` | Doluysa ilk kurulum sayfası bu anahtarı sorar | boş |

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

Aynı gün birden fazla ödeme varsa tek e-postada toplanır. `REMINDER_TO` tanımlıysa yalnızca o adrese (örneğin şirketin ortak posta kutusuna), değilse Ayarlar'da bildirimi açık olan ortaklara gider. SMTP tanımlı değilse uyarılar yalnızca "Bugün" ve "Sabit giderler" sayfalarında görünür.

## Ortak hesabı nasıl hesaplanıyor?

Her kayıtta "kim ödedi / parayı kim aldı" seçilir: ortaklardan biri ya da **Ortak hesap** (şirket hesabı, kasa).

- Bir ortağın **cebinden çıkan net** = ödediği giderler − teslim aldığı gelirler.
- Cebinden çıkan net kadar ortak **şirketten alacaklı** olur; teslim aldığı gelir ödediğinden fazlaysa **şirkete borçlu** olur.
- Ortaklar birbirine borçlanmaz; her ortağın hesabı yalnızca şirketle görülür.
- Şirketin ortağa yaptığı ödeme ("Şirket ödedi, kaydet") alacağı düşürür; ortağın şirkete yatırdığı para borcu kapatır.
- "Ortak hesap" seçilen kayıtlar kimsenin cebinden çıkmadığı için bu hesaba girmez; kâr/zarar raporuna ise girer.

Örnek: Ortak A 1.000 ₺ yakıtı cebinden ödedi. A, şirketten 1.000 ₺ alacaklı görünür; B'nin hesabı değişmez. Şirket A'ya 1.000 ₺ ödeyip kaydedince A'nın hesabı denkleşir.

Tutarlar veritabanında kuruş olarak (tam sayı) tutulur.

## Sabit gider eklerken

"Sıradaki ödeme tarihi"ne **bundan sonraki ilk taksitin** tarihini, "kalan taksit sayısı"na o tarihten itibaren kalan taksiti yazın (kira gibi süresizse boş bırakın). Geçmişte ödenmiş taksitleri girmek gerekmez. Taksit tutarı ay ay değişiyorsa, ödendi işaretlerken gerçek ödenen tutarı yazabilirsiniz.

Yanlış işaretlenen bir ödemeyi geri almak için oluşan gider kaydını açıp silin; taksit yeniden "ödenecekler"e döner.

### Euro cinsinden leasing

Tutarın yanından **€** seçin. Taksitler euro olarak tutulur, yanında günün kuruyla TL karşılığı gösterilir; pano ve rapordaki "bu ay ödenecek sabit giderler" de bu tahminle hesaplanır. Kur TCMB'nin günlük bülteninden (döviz satış) alınır: uygulama günde bir kez çeker, internet yoksa son bilinen kuru kullanır. Leasing şirketi başka bir kur uyguluyorsa "Sabit giderler > Euro kuru > Kuru elle gir" ile bugünün kurunu yazın; o gün için elle girilen kur TCMB kurunun önüne geçer.

"Ödendi" işaretlerken TL tutarı kurla dolu gelir; bankanın gerçekten çektiği tutarı yazıp düzeltin. Kayıtlara ve raporlara giren tutar her zaman ödenen TL'dir, muhasebe dökümü döviz görmez (yalnızca "Sabit ödemeler" sayfasında ayrı bir sütunda bilgi olarak durur).

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
