"""
NetProbe - Deney Koşucusu
=========================

Föy bölüm 4.6 ve 7'deki senaryoları çalıştırır ve sonuçları
results/experiments.csv dosyasına yazar. Her konfigürasyon birkaç kez
tekrarlanır (ortalama + değişkenlik için).

Senaryolar:
  S1 - Paket Boyutunun Etkisi   (farklı payload boyutları)
  S2 - Timeout Değerinin Etkisi (farklı ACK timeout değerleri)
  S3 - Kayıp Oranının Etkisi    (farklı yapay paket kaybı oranları)
  S4 - Dosya Boyutunun Etkisi   (küçük / orta / büyük dosya)
Uygun olduğunda Stop-and-Wait ve Sliding Window karşılaştırılır.

İstemci ve sunucu GERÇEK UDP soketleri ile (127.0.0.1) ayrı thread'lerde
çalışır; yapay kayıp/gecikme her iki yöne (simetrik) uygulanır.

Çalıştırma (parça parça, her biri tek seferde biter):
    python experiments/run_experiments.py init S1 S2
    python experiments/run_experiments.py S3a S3b
    python experiments/run_experiments.py S4a S4b
veya hepsi birden:
    python experiments/run_experiments.py all
"""

import csv
import hashlib
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import server   # noqa: E402
import client   # noqa: E402
from netsim import LossyChannel   # noqa: E402

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(BASE, "data")
OUT = "/tmp/netprobe_received"   # deney alici ciktilari: yerel FS (silinebilir, hizli, tutarli)
RESULTS = os.path.join(BASE, "results")
CSVPATH = os.path.join(RESULTS, "experiments.csv")

_port = [9400]
_count = [0]

FIELDS = ["scenario", "mode", "file", "filesize", "payload_size", "window",
          "timeout", "loss_rate", "delay_ms", "repeat", "completion_time_s",
          "throughput_kbps", "goodput_kbps", "data_packets_sent", "retransmissions",
          "retransmission_rate", "timeouts", "acks_received", "dup_acks",
          "dup_data_server", "failed_packets", "avg_rtt_ms", "min_rtt_ms",
          "max_rtt_ms", "integrity_ok"]

STARTUP = 0.05      # sunucu thread'inin bind olması için bekleme
FIN_LINGER = 0.15   # deneyde sunucunun FIN sonrası kısa beklemesi


def next_port():
    _port[0] += 1
    return _port[0]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def one_transfer(fname, mode, window, payload, timeout, loss, delay_ms, jitter_ms,
                 max_retries=5):
    port = next_port()
    src = os.path.join(DATA, fname)
    sres = {}

    def _srv():
        raw = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        raw.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        raw.bind(("127.0.0.1", port))
        chan = LossyChannel(raw, loss, delay_ms, jitter_ms, seed=port * 2 + 1)
        sres["m"] = server.run_server(out_dir=OUT, sock=chan, loss_rate=loss,
                                      idle_timeout=4.0, fin_linger=FIN_LINGER, verbose=False)

    out_file = os.path.join(OUT, fname)
    if os.path.exists(out_file):
        os.remove(out_file)   # eski (stale) dosya yanlis OK vermesin
    t = threading.Thread(target=_srv)
    t.start()
    time.sleep(STARTUP)
    mc = client.send_file("127.0.0.1", port, src, mode=mode, window=window,
                         payload_size=payload, timeout=timeout, max_retries=max_retries,
                         loss_rate=loss, delay_ms=delay_ms, jitter_ms=jitter_ms,
                         seed=port * 2, verbose=False)
    t.join(timeout=60)
    s = mc.summary()
    # Butunluk: dosya bu aktarimda yazildi mi, hash tutuyor mu VE hic paket basarisiz olmadi mi
    integrity = (os.path.exists(out_file) and sha(src) == sha(out_file)
                 and s["failed_packets"] == 0)
    dup_srv = sres.get("m").dup_data_received if sres.get("m") else 0
    s["dup_data_server"] = dup_srv
    s["integrity_ok"] = int(integrity)
    return s


def record(w, scenario, mode, fname, payload, window, timeout, loss, delay, jitter, reps):
    for r in range(reps):
        s = one_transfer(fname, mode, window, payload, timeout, loss, delay, jitter)
        row = {k: s.get(k) for k in FIELDS}
        row.update({"scenario": scenario, "mode": mode, "file": fname,
                    "payload_size": payload, "window": window, "timeout": timeout,
                    "loss_rate": loss, "delay_ms": delay, "repeat": r})
        w.writerow(row)
        _count[0] += 1
        ok = "OK" if s["integrity_ok"] else "FAIL"
        print("  [%3d] %-3s %-14s %-11s pl=%-4d win=%-2d to=%-5s loss=%-4s "
              "-> t=%6.3fs good=%8.1fkbps retx=%-4d dupSrv=%-3d [%s]"
              % (_count[0], scenario, mode, fname, payload, window, timeout, loss,
                 s["completion_time_s"], s["goodput_kbps"], s["retransmissions"],
                 s["dup_data_server"], ok), flush=True)


# --- senaryo parçaları ---
def chunk_S1(w):
    print(">> S1: Paket boyutunun etkisi", flush=True)
    for mode, win in [("stop-and-wait", 1), ("sliding-window", 16)]:
        for pl in [256, 512, 1024, 1400]:
            record(w, "S1", mode, "small.bin", pl, win, 0.08, 0.03, 1.0, 0.5, reps=3)

def chunk_S2(w):
    print(">> S2: Timeout değerinin etkisi (sliding window, kayıp=0.05)", flush=True)
    for to in [0.005, 0.015, 0.04, 0.1, 0.3]:
        record(w, "S2", "sliding-window", "small.bin", 1024, 16, to, 0.05, 3.0, 1.5, reps=3)

def chunk_S3a(w):
    print(">> S3a: Kayıp oranının etkisi (stop-and-wait)", flush=True)
    for loss in [0.0, 0.02, 0.05, 0.1, 0.2, 0.3]:
        record(w, "S3", "stop-and-wait", "small.bin", 1024, 1, 0.08, loss, 1.0, 0.5, reps=2)

def chunk_S3b(w):
    print(">> S3b: Kayıp oranının etkisi (sliding window)", flush=True)
    for loss in [0.0, 0.02, 0.05, 0.1, 0.2, 0.3]:
        record(w, "S3", "sliding-window", "small.bin", 1024, 16, 0.08, loss, 1.0, 0.5, reps=3)

def chunk_S4a1(w):
    print(">> S4a1: Dosya boyutu (stop-and-wait, küçük+orta)", flush=True)
    for fname in ["small.bin", "medium.bin"]:
        record(w, "S4", "stop-and-wait", fname, 1024, 1, 0.08, 0.03, 1.0, 0.5, reps=2)

def chunk_S4a2(w):
    print(">> S4a2: Dosya boyutu (stop-and-wait, büyük)", flush=True)
    record(w, "S4", "stop-and-wait", "large.bin", 1024, 1, 0.08, 0.03, 1.0, 0.5, reps=2)

def chunk_S4b(w):
    print(">> S4b: Dosya boyutunun etkisi (sliding window)", flush=True)
    for fname in ["small.bin", "medium.bin", "large.bin"]:
        record(w, "S4", "sliding-window", fname, 1024, 32, 0.08, 0.03, 1.0, 0.5, reps=2)

CHUNKS = {"S1": chunk_S1, "S2": chunk_S2, "S3a": chunk_S3a, "S3b": chunk_S3b,
          "S4a1": chunk_S4a1, "S4a2": chunk_S4a2, "S4b": chunk_S4b}


def main():
    os.makedirs(RESULTS, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    cmds = sys.argv[1:] or ["all"]
    if cmds == ["all"]:
        cmds = ["init"] + list(CHUNKS.keys())

    if cmds and cmds[0] == "init":
        with open(CSVPATH, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
        print("init: %s sıfırlandı" % CSVPATH, flush=True)
        cmds = cmds[1:]

    if not cmds:
        return
    t0 = time.time()
    f = open(CSVPATH, "a", newline="")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    for c in cmds:
        if c in CHUNKS:
            CHUNKS[c](w)
            f.flush()
        else:
            print("bilinmeyen parça: %s" % c, flush=True)
    f.close()
    print("Parça(lar) %s tamam, %.1f sn" % (cmds, time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
