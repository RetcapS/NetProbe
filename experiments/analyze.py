"""
NetProbe - Sonuç Analizi ve Grafik Üretimi
===========================================

results/experiments.csv dosyasını okur, tekrarların ortalamasını alır ve
föydeki dört senaryo için grafikler (results/*.png) ile özet tablolar
(results/summary_*.csv) üretir.

Çalıştırma:  python experiments/analyze.py
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS = os.path.join(BASE, "results")
CSV = os.path.join(RESULTS, "experiments.csv")

# Protokol renk/etiketleri
STYLE = {
    "stop-and-wait":  dict(color="#d62728", marker="o", label="Stop-and-Wait"),
    "sliding-window": dict(color="#1f77b4", marker="s", label="Sliding Window"),
}
plt.rcParams.update({"figure.dpi": 120, "font.size": 11, "axes.grid": True,
                     "grid.alpha": 0.3, "axes.axisbelow": True})


def agg(df, group_cols, val, ok_only=True):
    """Tekrarlar üzerinden ortalama ve standart sapma (hata çubukları için)."""
    d = df[df["integrity_ok"] == 1] if ok_only else df
    g = d.groupby(group_cols)[val]
    return g.mean(), g.std().fillna(0.0)


def main():
    df = pd.read_csv(CSV)
    print("Okunan satır:", len(df))

    # ---------------- S1: Paket boyutunun etkisi ----------------
    s1 = df[df["scenario"] == "S1"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    for mode, st in STYLE.items():
        d = s1[s1["mode"] == mode]
        x = sorted(d["payload_size"].unique())
        gm, gs = agg(d, "payload_size", "goodput_kbps")
        cm, cs = agg(d, "payload_size", "completion_time_s")
        ax1.errorbar(x, [gm[v] for v in x], yerr=[gs[v] for v in x],
                     capsize=3, **st)
        ax2.errorbar(x, [cm[v] for v in x], yerr=[cs[v] for v in x],
                     capsize=3, **st)
    ax1.set_xlabel("Payload boyutu (bayt)"); ax1.set_ylabel("Goodput (kbps)")
    ax1.set_title("S1: Payload boyutu vs Goodput"); ax1.legend()
    ax2.set_xlabel("Payload boyutu (bayt)"); ax2.set_ylabel("Tamamlanma süresi (s)")
    ax2.set_title("S1: Payload boyutu vs Tamamlanma süresi"); ax2.legend()
    fig.suptitle("Senaryo 1 — Paket (payload) boyutunun etkisi (small.bin, kayıp=0.03)",
                 fontweight="bold")
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_s1_payload.png")); plt.close(fig)

    # ---------------- S2: Timeout değerinin etkisi ----------------
    s2 = df[df["scenario"] == "S2"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    x = sorted(s2["timeout"].unique())
    rm, rs = agg(s2, "timeout", "retransmissions", ok_only=False)
    cm, cs = agg(s2, "timeout", "completion_time_s")
    ax1.errorbar(x, [rm[v] for v in x], yerr=[rs[v] for v in x], capsize=3,
                 color="#9467bd", marker="o")
    ax1.set_xscale("log"); ax1.set_xlabel("Timeout (s, log)")
    ax1.set_ylabel("Yeniden gönderim sayısı")
    ax1.set_title("S2: Timeout vs Yeniden gönderim")
    ax2.errorbar(x, [cm[v] for v in x], yerr=[cs[v] for v in x], capsize=3,
                 color="#2ca02c", marker="s")
    ax2.set_xscale("log"); ax2.set_xlabel("Timeout (s, log)")
    ax2.set_ylabel("Tamamlanma süresi (s)")
    ax2.set_title("S2: Timeout vs Tamamlanma süresi")
    fig.suptitle("Senaryo 2 — Timeout değerinin etkisi (sliding window, kayıp=0.05, RTT~6-9 ms)",
                 fontweight="bold")
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_s2_timeout.png")); plt.close(fig)

    # ---------------- S3: Kayıp oranının etkisi ----------------
    s3 = df[df["scenario"] == "S3"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    for mode, st in STYLE.items():
        d = s3[s3["mode"] == mode]
        x = sorted(d["loss_rate"].unique())
        gm, gs = agg(d, "loss_rate", "goodput_kbps")
        rm, rs = agg(d, "loss_rate", "retransmission_rate", ok_only=False)
        xs_ok = [v for v in x if v in gm.index]
        ax1.errorbar(xs_ok, [gm[v] for v in xs_ok], yerr=[gs[v] for v in xs_ok],
                     capsize=3, **st)
        ax2.errorbar(x, [rm[v] for v in x], yerr=[rs[v] for v in x], capsize=3, **st)
    ax1.set_xlabel("Yapay kayıp oranı"); ax1.set_ylabel("Goodput (kbps)")
    ax1.set_title("S3: Kayıp oranı vs Goodput (başarılı aktarımlar)"); ax1.legend()
    ax2.set_xlabel("Yapay kayıp oranı"); ax2.set_ylabel("Yeniden gönderim oranı")
    ax2.set_title("S3: Kayıp oranı vs Yeniden gönderim oranı"); ax2.legend()
    fig.suptitle("Senaryo 3 — Kayıp oranının etkisi (small.bin, payload=1024, timeout=0.08)",
                 fontweight="bold")
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_s3_loss.png")); plt.close(fig)

    # ---------------- S4: Dosya boyutunun etkisi ----------------
    s4 = df[df["scenario"] == "S4"]
    size_order = {"small.bin": 50 * 1024, "medium.bin": 512 * 1024, "large.bin": 2 * 1024 * 1024}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    for mode, st in STYLE.items():
        d = s4[s4["mode"] == mode].copy()
        d["bytes"] = d["file"].map(size_order)
        x = sorted(d["bytes"].unique())
        cm, cs = agg(d, "bytes", "completion_time_s")
        gm, gs = agg(d, "bytes", "goodput_kbps")
        ax1.errorbar([v/1024 for v in x], [cm[v] for v in x], yerr=[cs[v] for v in x],
                     capsize=3, **st)
        ax2.errorbar([v/1024 for v in x], [gm[v] for v in x], yerr=[gs[v] for v in x],
                     capsize=3, **st)
    ax1.set_xscale("log"); ax1.set_yscale("log")
    ax1.set_xlabel("Dosya boyutu (KB, log)"); ax1.set_ylabel("Tamamlanma süresi (s, log)")
    ax1.set_title("S4: Dosya boyutu vs Tamamlanma süresi"); ax1.legend()
    ax2.set_xscale("log")
    ax2.set_xlabel("Dosya boyutu (KB, log)"); ax2.set_ylabel("Goodput (kbps)")
    ax2.set_title("S4: Dosya boyutu vs Goodput"); ax2.legend()
    fig.suptitle("Senaryo 4 — Dosya boyutunun etkisi (payload=1024, kayıp=0.03)",
                 fontweight="bold")
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_s4_filesize.png")); plt.close(fig)

    # ---------------- Protokol karşılaştırma (S3 goodput bar) ----------------
    fig, ax = plt.subplots(figsize=(8, 4.4))
    losses = sorted(s3["loss_rate"].unique())
    import numpy as np
    width = 0.38
    xpos = np.arange(len(losses))
    for i, (mode, st) in enumerate(STYLE.items()):
        d = s3[s3["mode"] == mode]
        gm, _ = agg(d, "loss_rate", "goodput_kbps")
        vals = [gm.get(l, 0.0) for l in losses]
        ax.bar(xpos + (i - 0.5) * width, vals, width, color=st["color"], label=st["label"])
    ax.set_xticks(xpos); ax.set_xticklabels([str(l) for l in losses])
    ax.set_xlabel("Yapay kayıp oranı"); ax.set_ylabel("Ortalama goodput (kbps)")
    ax.set_title("Protokol karşılaştırması — Goodput (kayıp oranına göre)", fontweight="bold")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_protocol_compare.png")); plt.close(fig)

    # ---------------- Özet tablolar (rapor için) ----------------
    def save_summary(scn, group, fname):
        d = df[df["scenario"] == scn]
        cols = ["completion_time_s", "throughput_kbps", "goodput_kbps",
                "retransmissions", "retransmission_rate", "timeouts",
                "avg_rtt_ms", "failed_packets", "integrity_ok"]
        summ = d.groupby(group)[cols].mean().round(3)
        summ["n"] = d.groupby(group).size()
        summ.to_csv(os.path.join(RESULTS, fname))
        return summ

    print("\n--- S1 özet (mode, payload) ---")
    print(save_summary("S1", ["mode", "payload_size"], "summary_s1.csv"))
    print("\n--- S2 özet (timeout) ---")
    print(save_summary("S2", ["timeout"], "summary_s2.csv"))
    print("\n--- S3 özet (mode, loss) ---")
    print(save_summary("S3", ["mode", "loss_rate"], "summary_s3.csv"))
    print("\n--- S4 özet (mode, file) ---")
    print(save_summary("S4", ["mode", "file"], "summary_s4.csv"))

    print("\nGrafikler ve özetler results/ klasörüne yazıldı.")
    figs = [f for f in os.listdir(RESULTS) if f.endswith(".png")]
    print("Üretilen grafikler:", sorted(figs))


if __name__ == "__main__":
    main()
