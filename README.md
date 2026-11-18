# Akademik Sohbet Yöneticisi

Windows 10/11 için PySide6 masaüstü uygulaması. Telegram'ın kullanıcı MTProto API'sini Telethon 1.x ile kullanır; bot hesabı kullanmaz. Koleksiyonlar uygulamanın yerel SQLite verisinde tutulur ve Telegram klasörlerini değiştirmez.

## Özellikler

- Telegram API ID/Hash, telefon kodu ve varsa 2FA ile kullanıcı oturumu açma; yeniden açılışta oturumu sürdürme.
- Telegram sohbetlerini içe aktarma, arama, tür filtreleri, yeni ileti akışı ve yerel bildirim modları.
- Hiyerarşik koleksiyon oluşturma, yeniden adlandırma, silme, taşıma, renk/simge değiştirme, sürükle-bırak ile sohbet ekleme ve sohbeti koleksiyondan çıkarma.
- Gerçek sohbet geçmişini sayfalar halinde görüntüleme; önceki mesajları yükleme, arama, yanıtlama, kopyalama, kendi mesajını düzenleme/silme, dosya indirme ve dosya/metin gönderme.
- Toplu gönderim önizlemesi, alt koleksiyonların alıcılarını birleştirme ve tekilleştirme, izin bulunmayan hedefleri işaretleme, onaylı kuyruk, iptal, FloodWait'te durma, kalıcı durum geçmişi ve başarısız hedefi elle tekrar deneme.
- Sohbetleri uygulama görünümünde gizleme; açık/koyu tema, yazı tipi/büyüklüğü, vurgu rengi, sohbet arka planı ve liste yoğunluğu.
- Panel genişlikleri sürüklenerek değişir ve yerel veritabanında saklanır.
- API Hash işletim sistemi kimlik bilgisi kasasında saklanır. Telethon oturumu Windows kullanıcısının `%APPDATA%` dizininde tutulur; EXE'nin geçici açılma klasörüne yazılmaz.

## İlk çalıştırma

1. Python 3.12 kurun.
2. PowerShell'de bu klasöre geçip `python -m venv .venv` ve `\.venv\Scripts\Activate.ps1` çalıştırın.
3. `pip install -r requirements.txt` çalıştırın.
4. `python main.py` ile uygulamayı açın.
5. **Ayarlar → Hesabı bağla / değiştir** yolundan kendi API ID ve Hash bilgilerinizi girin. Telegram doğrulama kodu uygulama içinden istenir.

API ID/Hash, Telegram'ın `my.telegram.org` geliştirici sayfasından alınır. Bu uygulama Telegram'ın resmî masaüstü uygulaması değildir. Mesajlar bağlı kişisel hesaptan gönderilir; Telegram kullanım şartlarına ve hedef sohbetlerdeki yetkinize uyun.

## Windows EXE üretimi

Windows 10/11 x64 ortamında `Build-Windows.cmd` dosyasına çift tıklayın veya açık bir PowerShell penceresinde `./build_windows.ps1` çalıştırın. Python 3.12 x64 ve internet bağlantısı gerekir; ilk derlemede paketlerin indirilmesi birkaç dakika sürebilir. Derleme penceresi sonuç gösterilene kadar açık kalır. Hata oluşursa ayrıntılar `build_windows.log` dosyasına yazılır. PyInstaller `dist/AkademikSohbetYoneticisi/` portable klasörünü ve yanında bağımlılıkları içeren tek dosyalı `dist/AkademikSohbetYoneticisi-OneFile.exe` sürümünü üretir. Klasör sürümünü dağıtırken tüm klasörü koruyun; tek dosyalı EXE tek başına çalışır.

GitHub Actions iş akışı `.github/workflows/windows-build.yml` Windows runner'da testleri çalıştırıp portable ZIP ve tek dosyalı EXE artifact'lerini üretir. Bu geliştirme oturumu Linux üzerinde çalıştığı ve bağlanmış bir uygulama deposu bulunmadığı için Windows build iş akışı bu oturumda çalıştırılmadı; burada Windows `.exe` üretildiği iddia edilmemektedir.

## Testler

```bash
python -m pip install -r requirements-dev.txt
QT_QPA_PLATFORM=offscreen python -m pytest tests -q
```

Testler SQLite klasör hiyerarşisini, döngü engellemeyi, sohbet silinmeden koleksiyondan çıkarılmasını, gizleme, kuyruk/iptal/FloodWait davranışını ve UI açılışını kontrol eder. Gerçek Telegram hesabıyla E2E test için API kimlik bilgileri ve kullanıcı tarafından seçilmiş bir test sohbeti gerekir; bu testler otomatik mesaj göndermez.

## Mimari

- `main.py`: PySide6 arayüzü, qasync uygulama döngüsü ve kullanıcı işlemleri.
- `telegram_service.py`: Telethon oturum, senkronizasyon, geçmiş, dosya, mesaj ve yeni ileti güncellemeleri.
- `storage.py`: SQLite şeması, migrasyon, sohbet/klasör ilişkileri, tercih ve gönderim geçmişi.
- `messaging.py`: Onaylanmış toplu gönderim ve kuyruk durumu.
- `security.py`: işletim sistemi keyring üzerinden API Hash saklama.
- `tests/`: çevrimdışı otomatik kontroller.

Uygulama gönderilen mesajı Telegram'ın kabul ettiği durumla raporlar. Okundu bilgisi yalnız Telegram tarafından teyit edilirse Telegram'ın gerçek okundu durumu kullanılır; gönderim başarısı okundu olarak sunulmaz. FloodWait geldiğinde kuyruk bekleme süresini atlatmaya çalışmaz; o hedefi işaretler ve sonraki gönderimleri durdurur.
