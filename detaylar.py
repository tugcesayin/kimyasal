"""
Kimyasal detay bilgileri: fiziksel özellikler, CAS numarası, atomlar ve bağlar.

Veriler PubChem'den çekilir (PUG View deneysel özellikler + CAS, PUG REST 2D kayıt),
Türkçeye çevrilir ve yerel veritabanına kaydedilir; aynı kimyasal ikinci kez anında gelir.
"""
import json
import re
import sqlite3
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest"

# Atom numarası -> sembol (indeks = atom numarası)
SEMBOLLER = [""] + (
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr "
    "Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb "
    "Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf "
    "Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og"
).split()

BAG_TURLERI = {1: "Tekli", 2: "İkili", 3: "Üçlü", 4: "Dörtlü", 5: "Koordine", 7: "İyonik"}

# PubChem başlığı -> bizim alan adımız
BASLIKLAR = {
    "Physical Description": "fiziksel_tanim",
    "Color/Form": "renk",
    "Odor": "koku",
    "Melting Point": "erime",
    "Boiling Point": "kaynama",
    "Density": "yogunluk",
    "Vapor Pressure": "buhar_basinci",
    "Viscosity": "viskozite",
    "Surface Tension": "yuzey_gerilimi",
    "Flash Point": "parlama",
    "Autoignition Temperature": "tutusma",
    "Solubility": "cozunurluk",
    "LogP": "logp",
}

# Bu alanlarda tercih edilen birim (varsa o değer seçilir)
TERCIH = {
    "erime": "°C", "kaynama": "°C", "parlama": "°C", "tutusma": "°C",
    "yogunluk": "g/c", "buhar_basinci": "mm Hg", "viskozite": "Pa", "yuzey_gerilimi": "N/m",
}

# Türkçeye çevrilecek (metin içeren) alanlar
CEVRILECEK = ("renk", "koku", "cozunurluk")


# --------------------------------------------------------------------------------------
# PubChem yanıtını ayrıştırma
# --------------------------------------------------------------------------------------
def _bilgi_metinleri(bolum):
    """Bir PUG View bölümündeki tüm değerleri düz metin listesi olarak döndürür."""
    metinler = []
    for bilgi in bolum.get("Information", []):
        deger = bilgi.get("Value", {})
        if "Number" in deger:
            sayilar = " - ".join(str(s) for s in deger["Number"])
            metinler.append(f"{sayilar} {deger.get('Unit', '')}".strip())
        elif "StringWithMarkup" in deger:
            metin = " ".join(p.get("String", "") for p in deger["StringWithMarkup"]).strip()
            if metin:
                metinler.append(metin)
    return metinler


def _bolumleri_gez(bolumler):
    for b in bolumler or []:
        yield b
        yield from _bolumleri_gez(b.get("Section"))


def _temizle(metin):
    # Sondaki kaynak notlarını at: "100 °C (NTP, 1992)" -> "100 °C"
    metin = re.sub(r"\s*\((?:[^()]*\d{4}[^()]*)\)\s*$", "", metin)
    metin = re.sub(r"\s+", " ", metin).strip().rstrip(".;,")
    return metin


# Sayısal değerlerdeki sık geçen İngilizce ifadeler
YERELLESTIRME = [
    (r"\(closed cup\)", "(kapalı kap)"), (r"\(open cup\)", "(açık kap)"),
    (r"\bclosed cup\b", "kapalı kap"), (r"\bopen cup\b", "açık kap"),
    (r"g/cu ?cm", "g/cm³"), (r"g/cu ?m\b", "g/m³"), (r"\bcu ?cm\b", "cm³"),
    (r"\bmm ?Hg\b", "mmHg"), (r"\bdeg ?C\b", "°C"),
    (r"\s+at\s+([^,;()]+)", r" (\1)"), (r"\bdecomposes\b", "bozunur"), (r"\bsublimes\b", "süblimleşir"),
    (r"\bapprox(?:imately|\.)?\s*", "yaklaşık "), (r"\bto\b", "–"),
]


def _yerellestir(metin):
    for kalip, yerine in YERELLESTIRME:
        metin = re.sub(kalip, yerine, metin, flags=re.IGNORECASE)
    return metin


def _sec(metinler, alan):
    """Aday değerlerden en uygununu seçer: tercih edilen birimi içeren, kısa ve okunur olanı."""
    adaylar = [_temizle(m) for m in metinler[:12]]
    adaylar = [a for a in adaylar if a and len(a) <= 160]
    if not adaylar:
        return None
    birim = TERCIH.get(alan)
    if birim:
        uygun = [a for a in adaylar if birim.lower() in a.lower()]
        if uygun:
            adaylar = uygun
    # Çok uzun açıklamalar yerine ilk birkaç aday içinden en kısasını seç
    return min(adaylar[:6], key=len)


def _hal_bul(metinler):
    yazi = " ".join(metinler[:5]).lower()
    puan = {
        "Sıvı": yazi.count("liquid"),
        "Gaz": yazi.count(" gas") + yazi.startswith("gas"),
        "Katı": sum(yazi.count(k) for k in ("solid", "crystal", "powder", "flakes", "pellets")),
    }
    en_iyi = max(puan, key=puan.get)
    return en_iyi if puan[en_iyi] else None


def ozellikleri_ayristir(pug_view):
    """PUG View 'Experimental Properties' yanıtından {alan: değer} sözlüğü çıkarır."""
    sonuc = {}
    bolumler = (pug_view or {}).get("Record", {}).get("Section", [])
    for b in _bolumleri_gez(bolumler):
        alan = BASLIKLAR.get(b.get("TOCHeading"))
        if not alan or alan in sonuc:
            continue
        metinler = _bilgi_metinleri(b)
        if not metinler:
            continue
        if alan == "fiziksel_tanim":
            sonuc["hal"] = _hal_bul(metinler)
            continue
        deger = _sec(metinler, alan)
        if deger:
            sonuc[alan] = deger if alan in CEVRILECEK else _yerellestir(deger)
    if not sonuc.get("hal"):
        sonuc.pop("hal", None)
    return sonuc


def cas_ayristir(pug_view):
    """PUG View 'CAS' yanıtından en sık geçen CAS numarasını döndürür."""
    bolumler = (pug_view or {}).get("Record", {}).get("Section", [])
    sayac = Counter()
    for b in _bolumleri_gez(bolumler):
        if b.get("TOCHeading") == "CAS":
            for m in _bilgi_metinleri(b):
                if re.fullmatch(r"\d{2,7}-\d{2}-\d", m.strip()):
                    sayac[m.strip()] += 1
    return sayac.most_common(1)[0][0] if sayac else None


def yapi_ayristir(kayit):
    """PUG REST kayıt yanıtından atom sayıları ve gruplanmış bağları çıkarır."""
    try:
        bilesik = kayit["PC_Compounds"][0]
    except (KeyError, IndexError, TypeError):
        return [], []
    atomlar = bilesik.get("atoms", {})
    aid_sembol = {
        aid: SEMBOLLER[z] if 0 < z < len(SEMBOLLER) else "?"
        for aid, z in zip(atomlar.get("aid", []), atomlar.get("element", []))
    }

    # Hill sıralaması: önce C, sonra H, sonra alfabetik
    def sira(s):
        return (0 if s == "C" else 1 if s == "H" else 2, s)

    sayim = Counter(aid_sembol.values())
    atom_listesi = [{"sembol": s, "adet": n} for s, n in sorted(sayim.items(), key=lambda x: sira(x[0]))]

    # Bağlarda karbon başa, hidrojen sona yazılır: C—H, C—O, O—H
    def bag_sira(s):
        return (0 if s == "C" else 2 if s == "H" else 1, s)

    baglar = bilesik.get("bonds", {})
    gruplar = Counter()
    for a1, a2, derece in zip(baglar.get("aid1", []), baglar.get("aid2", []), baglar.get("order", [])):
        s1, s2 = sorted((aid_sembol.get(a1, "?"), aid_sembol.get(a2, "?")), key=bag_sira)
        gruplar[(s1, s2, BAG_TURLERI.get(derece, "Diğer"))] += 1
    bag_listesi = [
        {"atom1": s1, "atom2": s2, "tur": tur, "adet": n}
        for (s1, s2, tur), n in sorted(gruplar.items(), key=lambda x: (-x[1], bag_sira(x[0][0]), bag_sira(x[0][1])))
    ]
    return atom_listesi, bag_listesi


# --------------------------------------------------------------------------------------
# Çeviri
# --------------------------------------------------------------------------------------
def turkceye_cevir(metinler):
    """Metinleri Google Translate ile Türkçeye çevirir; başarısız olursa olduğu gibi bırakır."""
    if not metinler:
        return {}
    try:
        from deep_translator import GoogleTranslator
        cevirmen = GoogleTranslator(source="en", target="tr")
    except Exception:
        return {}
    sonuc = {}
    for anahtar, metin in metinler.items():
        try:
            ceviri = cevirmen.translate(metin)
            if ceviri:
                sonuc[anahtar] = ceviri[0].upper() + ceviri[1:]
        except Exception:
            pass
    return sonuc


# --------------------------------------------------------------------------------------
# PubChem'den çekme + önbellek
# --------------------------------------------------------------------------------------
def _json_getir(url):
    """JSON döndürür; kayıt yoksa (404) None; bağlantı/sunucu hatasında istisna fırlatır."""
    res = requests.get(url, timeout=15, headers={"User-Agent": "kimyasAl/1.0"})
    if res.status_code == 404:
        return None
    res.raise_for_status()
    return res.json()


def pubchemden_cek(cid):
    adresler = {
        "ozellik": f"{PUBCHEM}/pug_view/data/compound/{cid}/JSON?heading=Experimental+Properties",
        "cas": f"{PUBCHEM}/pug_view/data/compound/{cid}/JSON?heading=CAS",
        "yapi": f"{PUBCHEM}/pug/compound/cid/{cid}/record/JSON",
    }
    with ThreadPoolExecutor(max_workers=3) as havuz:
        isler = {ad: havuz.submit(_json_getir, url) for ad, url in adresler.items()}
        yanitlar = {ad: is_.result() for ad, is_ in isler.items()}

    ozellikler = ozellikleri_ayristir(yanitlar["ozellik"])
    ceviriler = turkceye_cevir({a: ozellikler[a] for a in CEVRILECEK if a in ozellikler})
    for alan, ceviri in ceviriler.items():
        ozellikler[alan] = ceviri

    atomlar, baglar = yapi_ayristir(yanitlar["yapi"])
    return {
        "cid": cid,
        "cas": cas_ayristir(yanitlar["cas"]),
        "ozellikler": ozellikler,
        "atomlar": atomlar,
        "baglar": baglar,
    }


def _onbellek_hazirla(db_yolu):
    with sqlite3.connect(db_yolu) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS detaylar (cid INTEGER PRIMARY KEY, veri TEXT NOT NULL, tarih TEXT NOT NULL)")


def detay_getir(cid, db_yolu):
    """Önce yerel önbelleğe bakar, yoksa PubChem'den çekip kaydeder."""
    _onbellek_hazirla(db_yolu)
    with sqlite3.connect(db_yolu) as conn:
        satir = conn.execute("SELECT veri FROM detaylar WHERE cid = ?", (cid,)).fetchone()
    if satir:
        return json.loads(satir[0])

    veri = pubchemden_cek(cid)
    with sqlite3.connect(db_yolu) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO detaylar (cid, veri, tarih) VALUES (?, ?, ?)",
            (cid, json.dumps(veri, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
        )
    return veri
