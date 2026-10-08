# Sezkar Muhasebe

İki ortağın günlük gelir ve giderlerini, fişleriyle birlikte tuttuğu web uygulaması. Tarayıcıdan bir adrese girilir, e-posta ve şifreyle oturum açılır; telefona ya da bilgisayara bir şey kurmak gerekmez.

- **Günlük kayıt:** yakıt, yevmiye, yemek, ek gider... Tutar, kategori, kim ödedi, fiş fotoğrafı. Telefondan fişi çekip doğrudan eklenebilir.
- **Gelir kaydı:** parayı kimin aldığıyla birlikte.
- **Sabit giderler:** leasing, kira gibi aylık ödemeler. Taksitler her ay kendiliğinden açılır; günü yaklaşınca sayfada uyarı ve e-posta gelir.
- **Ortak hesabı:** kim cebinden ne ödedi, kim ne aldı, sonuçta kim kime ne kadar borçlu.
- **Pano ve rapor:** bu ayın neti, son 14 günün gelir-gider grafiği, giderin kategorilere dağılımı, aylık kâr/zarar, son 12 ayın seyri.
- **Döküm:** muhasebeci için Excel (çok sayfalı) ve CSV.
- **Telefonda uygulama gibi:** ana ekrana eklenir, tam ekran açılır. Açık ve koyu tema.

Teknik: Python 3.11+, FastAPI, SQLAlchemy, SQLite, Jinja2 şablonları. Ayrı bir ön yüz derlemesi ya da dış servis yok; tek süreç, tek veri klasörü. Görünüm sezkar.com ile aynı marka renklerini (turuncu `#FC4D06`, siyah `#0E0F11`) ve yazı ailesini (Archivo) kullanır.

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

## Buluta kurmak (ortakların webden girmesi için)

Uygulamanın iki özel ihtiyacı var; servis seçerken bunlara bakın:

1. **Kalıcı disk.** Veritabanı ve fiş fotoğrafları diskte durur. Diski olmayan (her yeniden başlatmada sıfırlanan) planlarda kayıtlar silinir.
2. **Sürekli açık tek süreç.** E-posta hatırlatmaları uygulamanın içinden gider; kullanılmayınca uyuyan ücretsiz planlarda hatırlatma gitmez.

Ekim 2026'da servislerin kendi fiyat sayfalarından alınan rakamlar (değişebilir, kurmadan önce bakın):

| Servis | Aylık yaklaşık | Bölge | Not |
|---|---|---|---|
| **Render** (önerilen) | 7 $ (512 MB) + disk 0,25 $/GB → 2 GB ile ~7,5 $ | Frankfurt | Depodaki `render.yaml` ile kurulur. Diskin her gün otomatik yedeği alınır, en az 7 gün saklanır. Ücretsiz planı disk desteklemez ve 15 dakikada uyur; bu uygulamaya uymaz. |
| Railway | 5 $ abonelik (5 $ kullanım dahil); RAM 10 $/GB, disk 0,15 $/GB | Amsterdam | Küçük kullanımda aylık 5 $ içinde kalması beklenir. Hobby planda disk en çok 5 GB. Kurulum elle yapılır (aşağıda). |
| Fly.io | 3,19 $ (512 MB) + disk 0,15 $/GB | Frankfurt dahil | En ucuzu ama kurulum komut satırından; bu depoda hazır dosyası yok. |

Kaynaklar: [Render fiyatları](https://render.com/pricing), [Render diskleri](https://render.com/docs/disks), [Render ücretsiz plan sınırları](https://render.com/docs/free), [Railway fiyatları](https://docs.railway.com/reference/pricing/plans), [Railway volume](https://docs.railway.com/reference/volumes), [Fly.io fiyatları](https://fly.io/docs/about/pricing/).

### Render ile (önerilen)

1. [render.com](https://render.com) üzerinde hesap açın ve GitHub hesabınızı bağlayın.
2. **New > Blueprint** deyip bu depoyu seçin. Render `render.yaml` dosyasını okur: Frankfurt'ta bir web servisi ve 2 GB disk oluşturur.
3. Kurulum bitince servis sayfasındaki `https://...onrender.com` adresini açın. Kurulum sayfası bir **kurulum anahtarı** sorar: servis sayfasında **Environment** sekmesindeki `KURULUM_ANAHTARI` değerini kopyalayıp yapıştırın. (Adresi sizden önce bulan biri defteri kendi adına kuramasın diye.)
4. İki ortağın adını, şirket e-postasını ve şifresini girin. Defter hazır.
5. İsterseniz **Settings > Custom Domains** ile kendi alan adınızı bağlayın (örn. `muhasebe.sezkar.com`); sertifikayı Render kendisi alır.
6. E-posta hatırlatmaları için **Environment** sekmesine aşağıdaki SMTP değişkenlerini ekleyin.

Bundan sonra `main` dalına gönderilen her değişiklik kendiliğinden yayına girer. Diskli servislerde güncelleme sırasında uygulama birkaç saniye kapalı kalır; bu Render'ın veriyi korumak için yaptığı bir şeydir.

> `render.yaml` Render'ın belgelerindeki alan adlarına göre yazıldı ama Render üzerinde çalıştırılarak denenmedi. Kurulumda bir alan hata verirse ekrandaki mesaj hangi satır olduğunu söyler.

### Railway ile

1. [railway.com](https://railway.com) üzerinde **New Project > Deploy from GitHub repo** ile bu depoyu seçin. `Dockerfile` kendiliğinden bulunur.
2. Servise bir **Volume** ekleyin, bağlama yolu `/data` olsun.
3. **Variables** bölümüne `HTTPS_ONLY=1` ve (önerilir) `KURULUM_ANAHTARI=<uzun bir parola>` ekleyin.
4. **Settings > Networking > Generate Domain** ile adres alın, bölge olarak Amsterdam'ı seçin.

### Kendi sunucunuzda (Docker + otomatik HTTPS)

```bash
cp .env.example .env        # DOMAIN, BASE_URL ve (isterseniz) SMTP bilgilerini doldurun
docker compose up -d --build
```

Caddy alan adı için sertifikayı kendisi alır. Veritabanı ve fişler `./veri` klasöründe durur.

> Docker dosyaları bu ortamda Docker ile derlenip denenmedi. Kapsayıcının başlangıç betiği (`scripts/baslat.py`) ayrıca çalıştırılıp denendi: veri klasörünü uygulama kullanıcısına verir, yetkiyi bırakır, `PORT` değişkenini dinler.

Docker'sız çalıştırırsanız: tek süreç kullanın (`--workers` vermeyin), ters vekil `Host`, `X-Forwarded-For` ve `X-Forwarded-Proto` başlıklarını iletsin, yükleme sınırını açın (Nginx: `client_max_body_size 150m;`), HTTPS'te `HTTPS_ONLY=1` yapın.

## Ayarlar (ortam değişkenleri)

| Değişken | Ne işe yarar | Varsayılan |
|---|---|---|
| `APP_NAME` | Sekme başlığında ve e-postalarda görünen ad | Sezkar Muhasebe |
| `BASE_URL` | E-postalardaki bağlantının adresi | Render/Railway'de kendiliğinden bulunur; yoksa http://localhost:8000 |
| `HTTPS_ONLY` | Oturum çerezi yalnızca HTTPS'te gitsin | 0 |
| `KURULUM_ANAHTARI` | Verilirse ilk kurulum sayfası bu anahtarı sorar | boş |
| `DATA_DIR` | Veritabanı ve fişlerin klasörü | ./data (Docker'da /data) |
| `TZ_NAME` | Saat dilimi | Europe/Istanbul |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TLS` | E-posta sunucusu | boş (kapalı) |
| `REMINDER_HOUR` | Hatırlatmaların gideceği en erken saat | 9 |
| `REMINDERS_ENABLED` | Hatırlatmaları aç/kapat | 1 |
| `MAX_UPLOAD_MB` | Dosya başına yükleme sınırı | 15 |
| `SECRET_KEY` | Oturum imza anahtarı | ilk açılışta üretilir, veri klasöründe saklanır |

### E-posta hatırlatmaları

Şirket e-postanız Google Workspace ya da Gmail ise (hesapta iki adımlı doğrulama açıkken bir "uygulama şifresi" üretmeniz gerekir):

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=muhasebe@sirketiniz.com
SMTP_PASSWORD=uygulama-sifresi
SMTP_FROM=Sezkar Muhasebe <muhasebe@sirketiniz.com>
SMTP_TLS=starttls
```

Uygulama yeniden başladıktan sonra **Ayarlar > E-posta hatırlatmaları > Bana deneme e-postası gönder** ile sınayın.

Hatırlatma kuralı, her sabit gider için ayrı:

1. Vadeye "kaç gün önce hatırlatılsın" süresi kadar kala bir kez,
2. vade günü bir kez,
3. ödeme geciktiyse, "ödendi" işaretlenene kadar haftada bir (geciken bütün ödemeler tek e-postada).

Ayarlar'da bildirimi açık olan ortaklara gider. SMTP tanımlı değilse uyarılar yalnızca sayfalarda görünür.

## Telefona eklemek

Mağazadan uygulama indirmek gerekmez. Siteyi telefonda açıp:

- **iPhone (Safari):** Paylaş düğmesi > "Ana Ekrana Ekle".
- **Android (Chrome):** üç nokta menüsü > "Uygulamayı yükle" ya da "Ana ekrana ekle".

Ana ekranda SK simgesiyle durur, dokununca adres çubuğu olmadan açılır. Kayıtlar her zaman sunucudan gelir; internet yokken defter açılmaz, bunun yerine kısa bir "bağlantı yok" sayfası görünür.

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

Her şey tek klasörde: `defter.db` (veritabanı) ve `fisler/` (dosyalar). Render diskin günlük yedeğini kendisi alır. Kendi sunucunuzda:

```bash
scripts/yedekle.sh ./veri ./yedekler      # uygulama çalışırken de güvenle alınır
```

Bunu günlük bir `cron` işi yapıp yedekleri başka bir yere kopyalamanızı öneririm.

## Testler

```bash
pip install -r requirements-dev.txt
pytest
```

Tutar okuma, ortak bakiyesi, taksit üretimi, hatırlatma kuralları ve sayfa akışları (kayıt + fiş, ödeme, döküm, kurulum anahtarı, telefona ekleme dosyaları) sınanır.

## Klasörler

```
app/
  main.py            uygulama, ara katmanlar, hata sayfaları, telefona ekleme dosyaları
  config.py          ortam değişkenleri
  models.py          tablolar
  money.py           tutar okuma / yazma (kuruş)
  icons.py           arayüz ve kategori simgeleri
  security.py        şifre, oturum, başka siteden gelen istek koruması
  routers/           sayfalar: auth, dashboard, transactions, fixed, partners, reports, settings
  services/          hesap mantığı: balance, fixed, reports, charts, exports, reminders, receipts
  templates/, static/ (static/brand: logo ve simgeler)
scripts/             baslat.py (kapsayıcı başlangıcı), ornek_veri.py, yedekle.sh, sifre_sifirla.py
render.yaml          Render kurulum tarifi
tests/
```

## Bilinen sınırlar

- İki ortak için tasarlandı. Hesap mantığı daha fazla ortağı kaldırır ama kurulum sayfası iki kişi tanımlar; üçüncü kişi ve "yalnızca görebilen" muhasebeci hesabı yok.
- Veritabanı şeması için tam bir geçiş aracı yok. Tablolar ilk açılışta oluşturulur; sonradan eklenen sütunlar (ör. kategori simgesi) açılışta kendiliğinden eklenir. Daha büyük şema değişikliklerinde Alembic eklemek gerekir.
- Çıkış yapmak yalnızca o cihazdaki oturumu kapatır. Bir cihaz kaybolursa şifreyi değiştirin: şifre değişince diğer bütün cihazlardaki oturumlar düşer.
- "Şifremi unuttum" e-postası yok. Şifresini unutan ortak için sunucuda `python scripts/sifre_sifirla.py ortak@ornek.com` çalıştırılır.
- KDV ayrıştırma, fişten otomatik okuma ve araç/iş bazında takip bu sürümde yok.
