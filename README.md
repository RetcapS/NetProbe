# NetProbe — UDP Tabanlı Güvenilir Dosya Aktarımı, Trafik İzleme ve Ağ Performans Analiz Platformu

**Bilgisayar Ağları Dersi — Dönem Projesi**
Bursa Teknik Üniversitesi · Bilgisayar Mühendisliği Bölümü

NetProbe, UDP üzerinde **uygulama katmanında** kendi güvenilirlik mekanizmalarını
(sıra numarası, ACK, timeout, yeniden gönderim, checksum) uygulayan bir istemci–sunucu
dosya aktarım sistemidir. Aktarım sırasındaki ağ olaylarını kaydeder ve throughput,
goodput, RTT, kayıp/retransmission oranı gibi performans metriklerini üretir.

> Hazır bir güvenilir aktarım kütüphanesi **kullanılmamıştır**; tüm güvenilirlik
> mantığı `src/` altında elle gerçeklenmiştir. UDP soketleri Python standart
> kütüphanesinin `socket` modülü ile kullanılmıştır.

## Özellikler

- UDP istemci–sunucu mimarisi (gerçek `socket` programlama)
- İki güvenilir aktarım modu (aynı çekirdek döngü):
  - **Stop-and-Wait** (pencere = 1)
  - **Sliding Window** — Selective Repeat (pencere > 1)
- Sıra numarası, seçici ACK, timeout, paket başına en fazla 5 yeniden gönderim
- Duplicate paket yönetimi (alıcı veriyi ikinci kez yazmaz, ACK'i tekrarlar)
- Paket başına CRC32 checksum + dosya geneli SHA-256 bütünlük doğrulaması
- Trafik/olay loglama (CSV) ve metrik özeti (JSON)
- Yapay kayıp/gecikme kanalı ile kontrollü deney ortamı
- Otomatik deney koşucusu + matplotlib grafik üretimi

## Proje Yapısı

```
NetProbe/
├── README.md                  # bu dosya
├── requirements.txt           # Python bağımlılıkları
├── src/
│   ├── protocol.py            # Paket biçimi, serileştirme, CRC32, SHA-256
│   ├── netsim.py              # Yapay kayıp/gecikme kanalı (LossyChannel)
│   ├── metrics.py             # Olay loglama + metrik hesaplama
│   ├── server.py              # UDP sunucu (alıcı)  — çalıştırılabilir
│   └── client.py              # UDP istemci (gönderici) — çalıştırılabilir
├── experiments/
│   ├── test_transfer.py       # Doğruluk (correctness) testleri
│   ├── run_experiments.py     # 4 senaryo deney koşucusu
│   ├── analyze.py             # Grafik + özet tablo üretimi
│   └── gen_diagrams.py        # Rapor şemaları (mimari + akış)
├── data/                      # Test dosyaları (small/medium/large/sample)
├── results/                   # experiments.csv, grafikler (*.png), özetler
├── logs/                      # Aktarım olay/özet logları (CSV/JSON)
└── report/                    # Teknik rapor (PDF)
```

## Bağımlılıklar

- Python 3.8+
- Yalnızca standart kütüphane ile çalışır (socket, threading, struct, zlib, hashlib, csv, json).
- Deney/analiz için: `pandas`, `matplotlib`, `numpy`.

```bash
pip install -r requirements.txt
```

## Çalıştırma

### 1) Demo: tek dosya aktarımı (iki terminal)

Sunucu (alıcı):
```bash
cd src
python server.py --host 0.0.0.0 --port 9000 --output-dir ../received --loop
```

İstemci (gönderici) — Sliding Window:
```bash
cd src
python client.py --host 127.0.0.1 --port 9000 --file ../data/medium.bin \
    --protocol sliding-window --window 16 --payload 1024 --timeout 0.2
```

Stop-and-Wait ve yapay %5 kayıp ile:
```bash
python client.py --host 127.0.0.1 --port 9000 --file ../data/small.bin \
    --protocol stop-and-wait --payload 1024 --timeout 0.1 --loss 0.05
```

Önemli istemci parametreleri:

| Parametre | Açıklama | Varsayılan |
|-----------|----------|-----------|
| `--protocol` | `stop-and-wait` veya `sliding-window` | sliding-window |
| `--window` | Sliding window pencere boyutu | 16 |
| `--payload` | Veri payload boyutu (bayt) | 1024 |
| `--timeout` | ACK timeout süresi (s) | 0.3 |
| `--max-retries` | Paket başına en fazla yeniden gönderim | 5 |
| `--loss` | Yapay paket kaybı oranı [0–1] | 0.0 |
| `--delay` / `--jitter` | Yapay gecikme / sapma (ms) | 0.0 |
| `--metrics-dir` | Metriklerin (JSON/CSV) yazılacağı dizin | yok |

### 2) Doğruluk testleri

```bash
python experiments/test_transfer.py
```
Kayıpsız/kayıplı aktarım, duplicate yönetimi, başarısız-paket yolu ve
bozulma (checksum) kurtarmasını otomatik doğrular.

### 3) Deneyler ve grafikler

```bash
python experiments/run_experiments.py all     # results/experiments.csv üretir
python experiments/analyze.py                  # results/*.png ve özet tabloları üretir
python experiments/gen_diagrams.py             # mimari + protokol akış şemaları
```

## Protokol Özeti

Paket başlığı (15 bayt, big-endian): `type(1) | seq(4) | total(4) | length(2) | checksum(4)`.
Paket türleri: `DATA, ACK, META, META_ACK, FIN, FIN_ACK`. Checksum, başlık alanları +
payload üzerinden CRC32 ile hesaplanır. Dosya bütünlüğü tüm dosyanın SHA-256 özeti ile
doğrulanır. Ayrıntılar için teknik rapora bakınız.

## GitHub

Depo bağlantısı: `https://github.com/<kullanici-adi>/netprobe`  *(teslimden önce güncelleyiniz)*

## Lisans / Kaynaklar

Eğitim amaçlı dönem projesi. Kullanılan dış kütüphaneler: `pandas`, `matplotlib`,
`numpy` (yalnızca analiz/grafik için). Güvenilir aktarım protokolü tamamen özgün
olarak gerçeklenmiştir.
