# Station2EPW Desktop

Windows için geliştirilmiş, istasyon saatlik meteoroloji verilerini **EnergyPlus EPW** (`*.epw`) formatına dönüştüren masaüstü uygulaması. Arayüz **PySide6** ile yazılmıştır; veri işleme **pandas** ve **numpy** kullanır.

Tarık Aykan tarafından, **betanova.tech** çatısı altında geliştirilmiştir.

## Özellikler

- CSV ve Excel (`*.xlsx`, `*.xlsm`) okuma; CSV için UTF-8 / UTF-8-SIG / Latin-1 ve **chardet** ile kodlama denemesi, ayırıcı tahmini
- Tek kolon **datetime** veya Year–Minute alanlarına eşleştirme
- Birim dönüşümü (sıcaklık, basınç, rüzgar, radyasyon); **W/m² → Wh/m²** için saatlik ortalama güç varsayımı raporda belirtilir
- Kalite kontrol özeti (8760 saat uyarısı, tekrarlayan zaman, fiziksel aralıklar vb.)
- EPW üst bilgisi ve 35 saatlik meteoroloji alanı sırası ile uyumlu satır üretimi
- İşlem raporu ve TXT dışa aktarım
- İsteğe bağlı işlenmiş veri CSV çıktısı

## Gereksinimler

- Python **3.11+**
- Windows (EXE için PyInstaller aynı ortamda çalıştırılır)

## Kurulum

Depodaki `station2epw_desktop` klasörüne gidin:

```powershell
cd station2epw_desktop
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Uygulamayı çalıştırma

```powershell
python main.py
```

## Teknik uyumluluk (EnergyPlus / CBE)

Proje aşağıdaki denetime göre güncellenmiştir:

| Kontrol | Durum |
|--------|--------|
| Saatlik veri kolon sırası (Year … Liquid Precipitation Quantity) | EnergyPlus *Weather File Format* veri sözlüğü ile aynı sıra (`EPW_HOURLY_COLUMNS`) |
| Saat alanı 1–24 | Kaynak 0–23 ise +1; zaten 1–24 tam sayı ise dokunulmaz (`normalize_hours_for_epw`) |
| Datetime kolonu | `pandas.to_datetime` → `year`…`minute`; dakika 0–59’e yuvarlanır |
| Basınç | hPa seçildiğinde ×100 → **Pa** (EPW birimi) |
| Rüzgar | km/h → ÷3,6; knot → ×0,514444 → **m/s** |
| Radyasyon | Çıktı **Wh/m²** (tam sayı); W/m² girdisi için ×1 saat varsayımı |
| Eksik değerler | `EPW_MISSING_VALUES` ile alan bazlı kodlar |
| LOCATION satırı | **Enlem, boylam, saat dilimi (saat), rakım (m)** sırası EnergyPlus IDD ile uyumlu |
| Üst bilgi | `DATA PERIODS` satırında dönem adı **`Data`** (TMY3 örnekleriyle uyum); `GROUND TEMPERATURES` tek derinlikli geçerli yapı |

**CBE Climate Tool / Ladybug:** Bu araçlar EnergyPlus EPW okuyucusu ile aynı üst bilgi ve 35 veri alanını bekler. Yukarıdaki düzeltmeler (özellikle LOCATION alan sırası ve `DATA PERIODS`) dosyanın bu ekosistemde açılması için gereklidir. Tam yıl (ör. 8760 saat) olmayan dosyalar bazı araçlarda uyarı verebilir; bu beklenen davranıştır.

## Otomatik doğrulama (önerilir)

Kurulumdan sonra tek komutla birimler, kolon sırası, LOCATION ve örnek CSV ile uçtan uca EPW üretimini test edin:

```powershell
cd station2epw_desktop
python tools/verify_epw.py
```

Başarılı çıktı: `verify_epw: OK (all checks passed).`

## Örnek veriyle uçtan uca test (GUI)

1. `python main.py` ile uygulamayı açın.  
2. **1. Dosya yükle:** `sample_data/sample_station_data.csv` seçin; tabloda önizleme ve satır sayısı görünmeli.  
3. **2. İstasyon bilgileri:** Örnek: Şehir `Samsun`, Ülke `Turkey`, istasyon adı, WMO veya kod, enlem/boylam, saat dilimi `3`, rakım, veri yılı `2024`, kaynak/açıklama.  
4. **3. Kolon eşleştirme:** Otomatik tahminde `datetime` ve meteoroloji kolonları dolu olmalı; gerekirse düzeltin.  
5. **4. Birim dönüşümü:** Sıcaklık °C, basınç **hPa**, rüzgar **m/s**, radyasyon **Wh/m²** (örnek GHI zaten Wh/m²).  
6. **5. Veri kontrolü:** **Kontrolleri çalıştır** — kritik hata olmamalı; 8760 saat uyarısı bu örnekte normaldir.  
7. **6. EPW oluştur:** Çıktı klasörü seçin, dosya adını onaylayın, **EPW dosyası oluştur** — oluşan yolu not edin.  
8. **7. Rapor:** İsterseniz **TXT olarak kaydet**.  

**Harici doğrulama (isteğe bağlı):** Üretilen `.epw` dosyasını [CBE Clima Tool](https://clima.cbe.berkeley.edu/) (kendi EPW’nizi yükleme) veya Ladybug / Rhino EPW akışında açarak yükleme hatası olmadığını doğrulayın.

## EXE oluşturma

Önce PyInstaller kurun:

```powershell
pip install pyinstaller
```

Ardından:

```powershell
.\build_exe.bat
```

veya doğrudan:

```powershell
pyinstaller --noconfirm --onefile --windowed --name Station2EPW main.py
```

Çıktı genelde `dist\Station2EPW.exe` altında oluşur. Bu depoda PyInstaller **6.x** ile `main.py` komutu başarıyla tamamlanarak doğrulanmıştır; oluşan EXE tek dosya olarak çalışır.

PyInstaller uyarılarında **numba / tbb12.dll** vb. görürseniz, ortamınızdaki isteğe bağlı bilim paketlerinden kaynaklanır; çoğu durumda EXE yine çalışır. Sorun yaşanırsanız `build_exe.bat` yerine sanal ortamda yalnızca `requirements.txt` paketleri kurulu tutmayı deneyin.

PySide6 için bazı sistemlerde ek `--collect-all PySide6` bayrakları gerekebilir; sorun yaşanız PyInstaller günlük çıktısına göre gizli içe aktarmaları ekleyin.

## Bilinen sınırlılıklar (ilk sürüm)

- **Tasarım koşulları**, **tipik/ekstrem dönemler** ve **yer sıcaklıkları** üst bilgisinde minimal yer tutucu değerler kullanılır; iklim tasarımı doğrudan bu EPW’dan okunmamalıdır.
- İleri düzey EPW alanları (ışınım, bulut, görüş vb.) eşlenmezse EnergyPlus **missing** kodları ile doldurulur.
- Çok büyük dosyalarda bellek kullanımı pandas yükleme modeline bağlıdır; ilk sürüm tüm tabloyu bellekte tutar.
- Rapor ilk sürümde **TXT** olarak verilir; PDF sonraya bırakılmıştır.

## Gelecek geliştirmeler

- Tasarım koşulları ve yer sıcaklığı için ikinci aşama hesap veya harici kaynak bağlantısı  
- Çoklu Excel sayfası ve şema şablonları  
- PDF rapor ve günlük (log) dosyası  
- `pytest` ile CI entegrasyonu (`tools/verify_epw.py` genişletilebilir)  

## Lisans

Projeye özgü lisans dosyası eklenmediyse, kullanım koşullarını depo sahibi ile netleştirin.
