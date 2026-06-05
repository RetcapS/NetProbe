"""
NetProbe - Doğruluk (correctness) Testleri
===========================================

Protokolün temel ve kenar durumlarını otomatik doğrular:
  1. Kayıpsız aktarım (Stop-and-Wait + Sliding Window) -> bütünlük OK
  2. Kayıplı aktarım -> yeniden gönderim devreye girer, bütünlük yine OK
  3. Duplicate yönetimi -> ACK kaybında alıcı veriyi 2. kez yazmaz
  4. Başarısız paket yolu -> max_retries aşılınca paket başarısız raporlanır
  5. Bozulma (corruption) -> checksum ile yakalanır, yeniden gönderimle kurtarılır

Çalıştırma:  python experiments/test_transfer.py
"""

import hashlib
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import protocol           # noqa: E402
import server             # noqa: E402
import client             # noqa: E402
from netsim import LossyChannel   # noqa: E402

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "received")
_port = [9300]


def next_port():
    _port[0] += 1
    return _port[0]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def start_server(port, loss=0.0, clean=False, **kw):
    """Sunucuyu bir thread'de başlatır, sonucu dict ile döndürür."""
    res = {}

    def _run():
        if clean:
            raw = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            raw.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            raw.bind(("127.0.0.1", port))
            chan = LossyChannel(raw)
            res["m"] = server.run_server(out_dir=OUT, sock=chan, idle_timeout=8.0,
                                         verbose=False, **kw)
        else:
            res["m"] = server.run_server(host="127.0.0.1", port=port, out_dir=OUT,
                                         loss_rate=loss, seed=port + 1,
                                         idle_timeout=8.0, verbose=False, **kw)
    t = threading.Thread(target=_run)
    t.start()
    time.sleep(0.3)
    return t, res


class DropSeqChannel(LossyChannel):
    """Belirli seq numaralı DATA paketlerini HER ZAMAN düşürür (deterministik)."""
    def __init__(self, sock, drop_seqs):
        super().__init__(sock)
        self.drop_seqs = set(drop_seqs)

    def sendto(self, data, addr):
        pkt = protocol.parse_packet(data)
        if pkt and pkt.ptype == protocol.PKT_DATA and pkt.seq in self.drop_seqs:
            self.dropped += 1
            return len(data)   # gönderme
        return super().sendto(data, addr)


def main():
    os.makedirs(OUT, exist_ok=True)
    passed = 0
    failed = 0

    def check(name, cond, detail=""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [GEÇTİ] {name}  {detail}")
        else:
            failed += 1
            print(f"  [BAŞARISIZ] {name}  {detail}")

    print("NetProbe doğruluk testleri\n" + "=" * 50)

    # 1+2) Kayıpsız ve kayıplı aktarım, her iki protokol
    cases = [
        ("Stop-and-Wait, kayıpsız", "sample.txt", "stop-and-wait", 1, 0.0),
        ("Sliding Window, kayıpsız", "medium.bin", "sliding-window", 16, 0.0),
        ("Sliding Window, %10 kayıp", "small.bin", "sliding-window", 16, 0.10),
        ("Stop-and-Wait, %20 kayıp", "small.bin", "stop-and-wait", 1, 0.20),
    ]
    for name, fname, mode, win, loss in cases:
        p = next_port()
        t, res = start_server(p, loss=loss)
        m = client.send_file("127.0.0.1", p, os.path.join(DATA, fname), mode=mode,
                             window=win, payload_size=1024, timeout=0.2,
                             loss_rate=loss, seed=p, verbose=False)
        t.join(15)
        ok = (os.path.exists(os.path.join(OUT, fname)) and
              sha(os.path.join(DATA, fname)) == sha(os.path.join(OUT, fname)))
        check(name, ok, f"(retx={m.retransmissions}, timeout={m.timeouts}, "
                        f"dup_data_srv={res['m'].dup_data_received})")

    # 3) Duplicate yönetimi: simetrik kayıpta sunucuda dup_data > 0 olmalı, bütünlük OK
    p = next_port()
    t, res = start_server(p, loss=0.15)
    m = client.send_file("127.0.0.1", p, os.path.join(DATA, "small.bin"),
                         mode="sliding-window", window=8, payload_size=1024,
                         timeout=0.2, loss_rate=0.15, seed=p, verbose=False)
    t.join(15)
    integ = sha(os.path.join(DATA, "small.bin")) == sha(os.path.join(OUT, "small.bin"))
    check("Duplicate yönetimi (alıcı 2. kez yazmaz)",
          res["m"].dup_data_received > 0 and integ,
          f"(dup_data={res['m'].dup_data_received}, bütünlük={'OK' if integ else 'FAIL'})")

    # 4) Başarısız paket yolu: seq=3 daima düşürülür -> max_retries aşılır
    p = next_port()
    t, res = start_server(p, clean=True)
    raw = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    drop_chan = DropSeqChannel(raw, drop_seqs={3})
    m = client.send_file("127.0.0.1", p, os.path.join(DATA, "small.bin"),
                         mode="sliding-window", window=8, payload_size=1024,
                         timeout=0.12, max_retries=5, seed=p, verbose=False,
                         _channel=drop_chan)
    t.join(15)
    check("Başarısız paket raporlanır (max_retries aşıldı)",
          m.failed_packets == 1,
          f"(failed_packets={m.failed_packets}, timeouts={m.timeouts})")

    # 5) Bozulma: client çıkışında corrupt -> checksum yakalar, yeniden gönderimle kurtarılır
    p = next_port()
    t, res = start_server(p, clean=True)
    raw = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    corrupt_chan = LossyChannel(raw, corrupt_rate=0.10, seed=p)
    m = client.send_file("127.0.0.1", p, os.path.join(DATA, "small.bin"),
                         mode="sliding-window", window=8, payload_size=1024,
                         timeout=0.2, seed=p, verbose=False, _channel=corrupt_chan)
    t.join(15)
    integ = sha(os.path.join(DATA, "small.bin")) == sha(os.path.join(OUT, "small.bin"))
    check("Bozulma checksum ile yakalanır ve kurtarılır",
          res["m"].corrupt_received > 0 and integ,
          f"(corrupt_srv={res['m'].corrupt_received}, retx={m.retransmissions}, "
          f"bütünlük={'OK' if integ else 'FAIL'})")

    print("=" * 50)
    print(f"TOPLAM: {passed} geçti, {failed} başarısız")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
