"""NetProbe - Rapor için şema/diyagram üretimi (mimari + protokol akışı)."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS = os.path.join(BASE, "results")
plt.rcParams.update({"font.size": 10})

BLUE = "#1f77b4"; RED = "#d62728"; GRAY = "#555555"; GREEN = "#2ca02c"


def box(ax, x, y, w, h, text, fc="#eaf2fb", ec=BLUE, fs=9, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                fc=fc, ec=ec, lw=1.5))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", wrap=True)


# ---------- 1) Mimari blok diyagramı ----------
fig, ax = plt.subplots(figsize=(11, 4.6))
ax.set_xlim(0, 12); ax.set_ylim(0, 6); ax.axis("off")

box(ax, 0.3, 4.9, 4.0, 0.7, "İSTEMCİ (Gönderici)", fc="#dceaf7", ec=BLUE, fs=11, bold=True)
for i, t in enumerate(["Dosya → parçalara bölme (payload)",
                       "Sıra no + checksum (CRC32) ekleme",
                       "Selective Repeat / Stop-and-Wait",
                       "Timeout & yeniden gönderim (≤5)",
                       "UDP soketi (sendto/recvfrom)"]):
    box(ax, 0.3, 4.3 - i*0.72, 4.0, 0.6, t, fc="#f4f9ff", ec=BLUE, fs=8.5)

box(ax, 7.7, 4.9, 4.0, 0.7, "SUNUCU (Alıcı)", fc="#fde9e9", ec=RED, fs=11, bold=True)
for i, t in enumerate(["UDP soketi (recvfrom/sendto)",
                       "checksum doğrulama (bozuk→at)",
                       "Seçici ACK + duplicate yönetimi",
                       "Sıraya göre tampon + birleştirme",
                       "SHA-256 ile bütünlük doğrulama"]):
    box(ax, 7.7, 4.3 - i*0.72, 4.0, 0.6, t, fc="#fff4f4", ec=RED, fs=8.5)

# orta kanal (kutu ortada, oklar kutunun üstünde/altında -> çakışma yok)
box(ax, 4.85, 2.75, 2.3, 0.85, "AĞ KANALI\n(LossyChannel)\nyapay kayıp / gecikme",
    fc="#eeeeee", ec=GRAY, fs=8.5, bold=True)

# DATA oku (kutunun üstünde)
ax.annotate("", xy=(7.6, 4.05), xytext=(4.4, 4.05),
            arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=2))
ax.text(6.0, 4.22, "DATA paketleri →", ha="center", color=BLUE, fontsize=9)
# ACK oku (kutunun altında)
ax.annotate("", xy=(4.4, 2.3), xytext=(7.6, 2.3),
            arrowprops=dict(arrowstyle="-|>", color=RED, lw=2))
ax.text(6.0, 2.0, "← ACK paketleri", ha="center", color=RED, fontsize=9)
ax.text(6.0, 0.7, "META → / ← META_ACK   ·   FIN → / ← FIN_ACK (OK/FAIL)",
        ha="center", color=GRAY, fontsize=8.5, style="italic")

ax.set_title("Şekil A. NetProbe sistem mimarisi (istemci–kanal–sunucu)", fontweight="bold")
fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_arch.png"), dpi=120); plt.close(fig)


# ---------- 2) Protokol mesaj akışı (sequence) ----------
fig, ax = plt.subplots(figsize=(8.4, 7.2))
ax.set_xlim(0, 10); ax.set_ylim(0, 14); ax.axis("off")
cx, sx = 2.0, 8.0
ax.plot([cx, cx], [0.5, 13.2], color=BLUE, lw=1.2)
ax.plot([sx, sx], [0.5, 13.2], color=RED, lw=1.2)
box(ax, cx-1.3, 13.2, 2.6, 0.7, "İstemci", fc="#dceaf7", ec=BLUE, fs=11, bold=True)
box(ax, sx-1.3, 13.2, 2.6, 0.7, "Sunucu", fc="#fde9e9", ec=RED, fs=11, bold=True)

def msg(y, frm, to, label, color, lost=False, dash=False):
    style = (0, (4, 3)) if dash else "solid"
    if lost:
        ax.annotate("", xy=((frm+to)/2 + (0.5 if to>frm else -0.5), y-0.25),
                    xytext=(frm, y),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=1.6, linestyle=style))
        xm = (frm+to)/2 + (0.6 if to>frm else -0.6)
        ax.plot([xm-0.22, xm+0.22], [y-0.45, y-0.05], color="black", lw=2)
        ax.plot([xm-0.22, xm+0.22], [y-0.05, y-0.45], color="black", lw=2)
        ax.text(xm+0.5, y-0.25, "KAYIP", color="black", fontsize=8, va="center")
    else:
        ax.annotate("", xy=(to, y-0.3), xytext=(frm, y),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=1.6, linestyle=style))
    ax.text((frm+to)/2, y+0.12, label, ha="center", color=color, fontsize=8.5)

y = 12.6
msg(y, cx, sx, "META (dosya adı, boyut, paket sayısı, SHA-256)", BLUE); y -= 1.0
msg(y, sx, cx, "META_ACK", RED); y -= 1.1
msg(y, cx, sx, "DATA seq=0", BLUE); y -= 1.0
msg(y, sx, cx, "ACK 0", RED); y -= 1.1
msg(y, cx, sx, "DATA seq=1", BLUE, lost=True); y -= 1.15
ax.annotate("", xy=(cx-0.0, y+0.15), xytext=(cx-0.0, y+0.55),
            arrowprops=dict(arrowstyle="-|>", color=GRAY, lw=1.2))
ax.text(cx-1.45, y+0.35, "timeout\n(ACK gelmedi)", ha="center", color=GRAY, fontsize=7.6); y -= 0.15
msg(y, cx, sx, "DATA seq=1 (yeniden gönderim)", BLUE); y -= 1.0
msg(y, sx, cx, "ACK 1", RED); y -= 1.2
ax.text((cx+sx)/2, y+0.35, "… tüm paketler onaylanana kadar (pencere kayar) …",
        ha="center", color=GRAY, fontsize=8.2, style="italic"); y -= 0.7
msg(y, cx, sx, "FIN", BLUE); y -= 1.0
msg(y, sx, cx, "FIN_ACK (OK / FAIL)", RED); y -= 0.2

ax.set_title("Şekil B. Protokol mesaj akışı (kayıp + yeniden gönderim örneği)",
             fontweight="bold")
fig.tight_layout(); fig.savefig(os.path.join(RESULTS, "fig_sequence.png"), dpi=120); plt.close(fig)
print("Diyagramlar üretildi: fig_arch.png, fig_sequence.png")
