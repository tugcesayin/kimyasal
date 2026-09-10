import sqlite3
import json
import requests
import re
import time
import os
import pubchempy as pcp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "kimyasal_veritabani.db")

# Önceden indirilecek yaygın kimyasalların listesi (Genişletilebilir)
ON_TANIMLI_KIMYASALLAR = [
    ("sülfürik asit", "sulfuric acid"),
    ("hidroklorik asit", "hydrochloric acid"),
    ("nitrik asit", "nitric acid"),
    ("asetik asit", "acetic acid"),
    ("fosforik asit", "phosphoric acid"),
    ("sitrik asit", "citric acid"),
    ("formik asit", "formic acid"),
    ("okzalik asit", "oxalic acid"),
    ("borik asit", "boric acid"),
    ("hidroflorik asit", "hydrofluoric acid"),
    ("sodyum hidroksit", "sodium hydroxide"),
    ("potasyum hidroksit", "potassium hydroxide"),
    ("kalsiyum hidroksit", "calcium hydroxide"),
    ("amonyum hidroksit", "ammonium hydroxide"),
    ("amonyak", "ammonia"),
    ("etanol", "ethanol"),
    ("metanol", "methanol"),
    ("izopropanol", "isopropanol"),
    ("aseton", "acetone"),
    ("kloroform", "chloroform"),
    ("diklorometan", "dichloromethane"),
    ("benzen", "benzene"),
    ("toluen", "toluene"),
    ("ksilen", "xylene"),
    ("dietil eter", "diethyl ether"),
    ("tetrahidrofuran", "tetrahydrofuran"),
    ("etil asetat", "ethyl acetate"),
    ("sodyum klorür", "sodium chloride"),
    ("potasyum klorür", "potassium chloride"),
    ("sodyum hipoklorit", "sodium hypochlorite"),
    ("sodyum bikarbonat", "sodium bicarbonate"),
    ("potasyum permanganat", "potassium permanganate"),
    ("bakır sülfat", "copper sulfate"),
    ("demir sülfat", "iron sulfate"),
    ("hidrojen peroksit", "hydrogen peroxide"),
    ("glikoz", "glucose"),
    ("fruktoz", "fructose"),
    ("üre", "urea"),
    ("kafein", "caffeine"),
    ("aspirin", "aspirin"),
    ("parasetamol", "paracetamol"),
    ("formaldehit", "formaldehyde"),
    ("fenol", "phenol"),
    ("anilin", "aniline"),
    ("hekzan", "hexane"),
    ("sikloheksan", "cyclohexane"),
    ("su", "water")
]

H_KODLARI_TR = {
    "H200": "Patlayıcı; kitlesel patlama tehlikesi",
    "H201": "Patlayıcı; kitlesel patlama tehlikesi",
    "H202": "Patlayıcı; ciddi fırlatma tehlikesi",
    "H203": "Patlayıcı; yangın, patlama veya fırlatma tehlikesi",
    "H204": "Yangın veya fırlatma tehlikesi",
    "H205": "Yangında kitlesel patlama tehlikesi",
    "H220": "Son derece yanıcı gaz",
    "H221": "Yanıcı gaz",
    "H222": "Son derece yanıcı aerosol",
    "H223": "Yanıcı aerosol",
    "H224": "Son derece yanıcı sıvı ve buhar",
    "H225": "Çok kolay tutuşan sıvı ve buhar",
    "H226": "Yanıcı sıvı ve buhar",
    "H227": "Yanıcı sıvı",
    "H228": "Yanıcı katı",
    "H229": "Basınçlı kap: ısıtılırsa patlayabilir",
    "H270": "Yangına neden olabilir veya yoğunlaştırabilir; oksitleyici",
    "H271": "Patlama veya yangına neden olabilir; güçlü oksitleyici",
    "H272": "Yangını yoğunlaştırabilir; oksitleyici",
    "H280": "Basınçlı gaz içerir; ısıtılırsa patlayabilir",
    "H290": "Metallere karşı aşındırıcı olabilir",
    "H300": "Yutulması halinde öldürücü",
    "H301": "Yutulması halinde zehirli",
    "H302": "Yutulması halinde zararlı",
    "H304": "Yutulması ve soluk yollarına kaçması halinde öldürücü olabilir",
    "H310": "Deri ile temasında öldürücü",
    "H311": "Deri ile temasında zehirli",
    "H312": "Deri ile temasında zararlı",
    "H314": "Ciddi deri yanıklarına ve göz hasarına neden olur",
    "H315": "Deri tahrişine neden olur",
    "H317": "Alerjik deri reaksiyonuna neden olabilir",
    "H318": "Ciddi göz hasarına neden olur",
    "H319": "Ciddi göz tahrişine neden olur",
    "H330": "Solunması halinde öldürücü",
    "H331": "Solunması halinde zehirli",
    "H332": "Solunması halinde zararlı",
    "H335": "Solunum yolu tahrişine neden olabilir",
    "H336": "Uyuşukluğa veya sersemliğe neden olabilir",
    "H340": "Genetik hasara neden olabilir",
    "H350": "Kansere neden olabilir",
    "H351": "Kansere neden olabileceğinden şüphelenilmektedir",
    "H360": "Doğurganlığa veya doğmamış çocuğa zarar verebilir",
    "H370": "Organlara zarar verir",
    "H372": "Uzun süreli veya tekrarlanan maruziyette organlara zarar verir",
    "H400": "Sucul organizmalar için çok zehirli",
    "H410": "Uzun süre kalıcı etkiyle sucul organizmalar için çok zehirli",
    "H411": "Uzun süre kalıcı etkiyle sucul organizmalar için zehirli",
    "H412": "Uzun süre kalıcı etkiyle sucul organizmalar için zararlı"
}

GHS_PIKTOGRAM = {
    "Explosive": {"sembol": "", "renk": "#ff6b35", "isim": "Patlayıcı"},
    "Flammable": {"sembol": "", "renk": "#ff4500", "isim": "Yanıcı"},
    "Oxidizer": {"sembol": "", "renk": "#ffa500", "isim": "Oksitleyici"},
    "Compressed Gas": {"sembol": "", "renk": "#4a90d9", "isim": "Basınçlı Gaz"},
    "Corrosive": {"sembol": "", "renk": "#8b4513", "isim": "Aşındırıcı"},
    "Toxic": {"sembol": "", "renk": "#800080", "isim": "Zehirli"},
    "Harmful": {"sembol": "", "renk": "#ffd700", "isim": "Zararlı"},
    "Health Hazard": {"sembol": "", "renk": "#dc143c", "isim": "Sağlık Tehlikesi"},
    "Environmental Hazard": {"sembol": "", "renk": "#228b22", "isim": "Çevre Tehlikesi"},
}

H_KATEGORI = {
    "H2": {"isim": "Fiziksel Tehlike", "renk": "#ff6b35", "ikon": "!"},
    "H3": {"isim": "Sağlık Tehlikesi", "renk": "#e74c3c", "ikon": "+"},
    "H4": {"isim": "Çevre Tehlikesi", "renk": "#27ae60", "ikon": "*"},
}

def hill_sirala(formul):
    elementler = re.findall(r'([A-Z][a-z]?)(\d*)', formul)
    sayac = {}
    for el, sayi in elementler:
        if el:
            sayac[el] = sayac.get(el, 0) + (int(sayi) if sayi else 1)
    sonuc = []
    if 'C' in sayac:
        sonuc.append(('C', sayac.pop('C')))
        if 'H' in sayac:
            sonuc.append(('H', sayac.pop('H')))
    elif 'H' in sayac:
        sonuc.append(('H', sayac.pop('H')))
    for el in sorted(sayac.keys()):
        sonuc.append((el, sayac[el]))
    return ''.join(f"{el}{sayi if sayi > 1 else ''}" for el, sayi in sonuc)

def formul_alt_indis(formul):
    return re.sub(r'(\d+)', lambda m: ''.join(chr(0x2080 + int(d)) for d in m.group()), formul)

def ghs_find(sections):
    for s in sections:
        if s.get("TOCHeading") == "GHS Classification":
            return s
        if "Section" in s:
            r = ghs_find(s["Section"])
            if r:
                return r
    return None

def veritabani_kur():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kimyasallar (
            arama_adi TEXT PRIMARY KEY,
            isim TEXT,
            formul TEXT,
            agirlik TEXT,
            cid TEXT,
            yapi_url TEXT,
            h_kodlari TEXT,
            piktogramlar TEXT
        )
    """)
    conn.commit()
    conn.close()

def veri_cek_ve_kaydet(tr_ad, en_ad):
    print(f"-> İndiriliyor: {tr_ad} ({en_ad})...")
    try:
        compounds = pcp.get_compounds(en_ad, "name")
        if not compounds:
            print(f"Bulunamadı: {en_ad}")
            return
        c = compounds[0]

        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{requests.utils.quote(en_ad)}/cids/JSON"
        res = requests.get(url, timeout=10)
        cid = res.json()["IdentifierList"]["CID"][0]
        yapi_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG?record_type=2d&image_size=600x600"

        data_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON"
        data = requests.get(data_url, timeout=10).json()

        sections = data["Record"]["Section"]
        ghs = ghs_find(sections)
        h_kodlari_ham = set()
        piktogramlar = set()

        if ghs:
            for info in ghs.get("Information", []):
                baslik = info.get("Name", "")
                for item in info.get("Value", {}).get("StringWithMarkup", []):
                    text = item.get("String", "")
                    if "Pictogram" in baslik or "GHS" in baslik:
                        for pg_isim in GHS_PIKTOGRAM:
                            if pg_isim.lower() in text.lower():
                                piktogramlar.add(pg_isim)
                    match = re.search(r"(H\d{3})", text)
                    if match:
                        h_kodlari_ham.add(match.group(1))

        h_listesi = []
        for kod in sorted(h_kodlari_ham):
            tr = H_KODLARI_TR.get(kod, "Açıklama bulunamadı")
            prefix = kod[:2]
            kat = H_KATEGORI.get(prefix, {"isim": "Diğer", "renk": "#95a5a6", "ikon": "❓"})
            h_listesi.append({
                "kod": kod,
                "tr": tr,
                "kategori": kat["isim"],
                "renk": kat["renk"],
                "ikon": kat["ikon"],
            })

        pikt_listesi = []
        for pg in piktogramlar:
            if pg in GHS_PIKTOGRAM:
                p = GHS_PIKTOGRAM[pg]
                pikt_listesi.append({
                    "isim": p["isim"],
                    "sembol": p["sembol"],
                    "renk": p["renk"],
                })

        formul = formul_alt_indis(hill_sirala(c.molecular_formula))
        agirlik = str(c.molecular_weight)
        h_kodlari_json = json.dumps(h_listesi, ensure_ascii=False)
        piktogramlar_json = json.dumps(pikt_listesi, ensure_ascii=False)

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Hem Türkçe hem İngilizce aramalar için indeks ekleme
        for anahtar, gorunen_ad in [(tr_ad.lower(), tr_ad.title()), (en_ad.lower(), tr_ad.title())]:
            cur.execute("""
                INSERT OR REPLACE INTO kimyasallar 
                (arama_adi, isim, formul, agirlik, cid, yapi_url, h_kodlari, piktogramlar)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (anahtar, gorunen_ad, formul, agirlik, str(cid), yapi_url, h_kodlari_json, piktogramlar_json))
        
        conn.commit()
        conn.close()
        print(f"✓ Başarıyla kaydedildi: {tr_ad}")
    except Exception as e:
        print(f"Hata ({tr_ad}): {e}")

if __name__ == "__main__":
    veritabani_kur()
    print("Veri tabanı indirme süreci başlıyor...")
    for tr, en in ON_TANIMLI_KIMYASALLAR:
        veri_cek_ve_kaydet(tr, en)
        time.sleep(0.3)  # PubChem istek kotasına takılmamak için kısa bekleme
    print("\nİşlem tamamlandı! 'kimyasal_veritabani.db' dosyanız hazır.")