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

GitHub Actions iş akışı `.github/workflows/windows-build.yml`, `main` dalına yapılan push işlemlerinde, pull request'lerde ve elle başlatıldığında Windows runner üzerinde bağımlılık ve sözdizimi kontrollerini, otomatik testleri ve başarılı testlerin ardından portable ZIP ile tek dosyalı EXE derlemelerini gerçekleştirir. Sonuçlar ilgili Actions çalıştırmasının artifact bölümünde yer alır; gerçek Telegram hesabıyla uçtan uca doğrulama ayrıca yapılmalıdır.

## Testler

```bash
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
QT_QPA_PLATFORM=offscreen python -m pytest tests -q
```

Testler SQLite klasör hiyerarşisini, döngü engellemeyi, sohbet silinmeden koleksiyondan çıkarılmasını, gizleme, kuyruk/iptal/FloodWait davranışını ve UI açılışını kontrol eder. Gerçek Telegram hesabıyla E2E test için API kimlik bilgileri ve kullanıcı tarafından seçilmiş bir test sohbeti gerekir; bu testler otomatik mesaj göndermez.

Windows PowerShell'de son satır yerine `$env:QT_QPA_PLATFORM = 'offscreen'` ve `python -m pytest tests -q` komutlarını çalıştırın. Editable kurulum, depo klasörünün adı farklı olsa bile `academic_chat_manager` importlarının çalışmasını sağlar.

## Mimari

- `main.py`: PySide6 arayüzü, qasync uygulama döngüsü ve kullanıcı işlemleri.
- `telegram_service.py`: Telethon oturum, senkronizasyon, geçmiş, dosya, mesaj ve yeni ileti güncellemeleri.
- `storage.py`: SQLite şeması, migrasyon, sohbet/klasör ilişkileri, tercih ve gönderim geçmişi.
- `messaging.py`: Onaylanmış toplu gönderim ve kuyruk durumu.
- `security.py`: işletim sistemi keyring üzerinden API Hash saklama.
- `tests/`: çevrimdışı otomatik kontroller.

Uygulama gönderilen mesajı Telegram'ın kabul ettiği durumla raporlar. Okundu bilgisi yalnız Telegram tarafından teyit edilirse Telegram'ın gerçek okundu durumu kullanılır; gönderim başarısı okundu olarak sunulmaz. FloodWait geldiğinde kuyruk bekleme süresini atlatmaya çalışmaz; o hedefi işaretler ve sonraki gönderimleri durdurur.

## Stable releases and automatic updates

Son kullanıcı için Python, Git ve .venv gerekmez: ilk kurulumu [GitHub Releases](https://github.com/baturyusuf/academic_chat_manager_complete/releases/latest) sayfasındaki **AcademicChatManager-Setup.exe** ile yapın. Stable kurulum üst çubukta yeni sürümü gösterir; onayla indirir, doğrular ve yeniden başlatır. CI/portable ve kaynak kodu çalıştırmaları otomatik güncelleme yapmaz.

Yayın süreci (repo sahibi için):
1. Önce bu altyapıyı main'e birleştirin; main'den publish branch'ini oluşturun ve PR/branch koruması ile yalnız güvenilir değişiklikleri kabul edin.
2. Güvenilir, yerel bir Python ortamında cryptography kurun. Aşağıdaki komut tek seferlik 32 bayt Ed25519 private key üretir. Çıktıyı hiçbir zaman commit veya log etmeyin; Settings → Secrets and variables → Actions altında ACM_RELEASE_SIGNING_KEY olarak kaydedin ve güvenli çevrimdışı yedeğini alın.

   ```sh
   python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"
   ```

3. main → publish PR ile yayınlayın veya publish üzerinde workflow_dispatch çalıştırın. Testler, Windows build, imzalı manifest ve release otomatik üretilir. Workflow run numarası pyproject taban sürümünün patch bileşenine eklenir; major/minor değişimi bilinçli pyproject değişikliğidir. Tekrar çalıştırma aynı tag'i kullanır; mevcut yayımlanmış release değiştirilmez. Doküman/test-only push yayın tetiklemez; elle tetikleme de son yayımlanan tag ile uygulama dosyaları aynıysa yeni release üretmez. CI ayrıca installer'ı geçici dizine kurar, frozen EXE'nin sürüm ve asset kontrolünü çalıştırır, ardından kaldırır.
4. İlk kurulumun kaynağı GitHub Releases olmalıdır. Ed25519 doğrulama anahtarı pakete gömülür; sonraki güncellemeler aynı anahtarla imzalanmalıdır. Anahtar rotasyonu için yeni güven kökü dağıtım planı gerekir. Windows Authenticode henüz yoktur; SmartScreen uyarısı çıkabilir.

Güncelleme, doğrulanmış tam installer paketini indirir (delta güncelleme yok). Kurulu uygulama kapandıktan sonra helper SQLite yedeği alır, kurulumu uygular ve uygulamayı yeniden başlatır. APPDATA ve Windows Credential Manager korunur. Kurulum hataları staging dizinindeki log ile raporlanır; otomatik binary rollback henüz yoktur. Sorun halinde önceki release installer'ı ve migration uyumluluğu kontrol edilerek manuel kurtarma yapılmalıdır. Stable yayınlamadan önce temiz Windows 10/11 kullanıcı hesabında iki ardışık imzalı sürümle kurulum, güncelleme ve veri koruma testi yapın.
