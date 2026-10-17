from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash, session, Response, stream_with_context
import pubchempy as pcp
import requests
import re
import os
import json
import sqlite3
import io
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

def env_dosyasi_yukle():
    """Proje klasöründeki .env dosyasındaki ayarları (ör. GEMINI_API_KEY) okur."""
    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(yol):
        return
    with open(yol, encoding="utf-8-sig") as f:
        for satir in f:
            satir = satir.strip()
            if not satir or satir.startswith("#") or "=" not in satir:
                continue
            anahtar, deger = satir.split("=", 1)
            os.environ.setdefault(anahtar.strip(), deger.strip().strip('"').strip("'"))

env_dosyasi_yukle()

# .env okunduktan sonra yüklenmeli (DATABASE_URL oradan da gelebilir)
import veritabani as db
import karisim

app = Flask(__name__)

# ==============================================================================
# 1. HIZLI YEREL VERİTABANI (SQLITE CACHE) SİSTEMİ
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "kimyasal_veritabani.db")

def veritabani_hazirla():
    """Uygulama açılışında yerel önbellek tablosunu oluşturur."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
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

def yerelden_getir(ad):
    """Daha önce aranan kimyasalı yerel diskten milisaniyeler içinde getirir."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT isim, formul, agirlik, cid, yapi_url, h_kodlari, piktogramlar FROM kimyasallar WHERE arama_adi = ?",
            (ad.lower().strip(),)
        )
        satir = cursor.fetchone()
        conn.close()

        if satir:
            formul = formul_gosterim_duzenle(satir[1])
            return {
                "isim": satir[0],
                "formul": formul,
                "agirlik": satir[2],
                "cid": satir[3],
                "yapi_url": satir[4],
                "h_kodlari": json.loads(satir[5]),
                "piktogramlar": json.loads(satir[6])
            }
    except Exception as e:
        print(f"Yerel okuma hatası: {e}")
    return None

def yerele_kaydet(arama_adi, veri):
    """PubChem'den yeni çekilen bilgiyi sonraki aramalar için anında yerele yazar."""
    try:
        veri = dict(veri)
        veri["formul"] = formul_gosterim_duzenle(veri.get("formul", ""))
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO kimyasallar 
            (arama_adi, isim, formul, agirlik, cid, yapi_url, h_kodlari, piktogramlar)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            arama_adi.lower().strip(),
            veri["isim"],
            veri["formul"],
            veri["agirlik"],
            str(veri["cid"]),
            veri["yapi_url"],
            json.dumps(veri["h_kodlari"], ensure_ascii=False),
            json.dumps(veri["piktogramlar"], ensure_ascii=False)
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Yerel kayıt hatası: {e}")

veritabani_hazirla()

# ==============================================================================
# 2. SÖZLÜKLER VE YARDIMCI KİMYA FONKSİYONLARI
# ==============================================================================
TURKCE_KIMYASAL = {
    # Asitler
    "nitrik asit": "nitric acid",
    "sülfürik asit": "sulfuric acid",
    "hidroklorik asit": "hydrochloric acid",
    "asetik asit": "acetic acid",
    "fosforik asit": "phosphoric acid",
    "sitrik asit": "citric acid",
    "okzalik asit": "oxalic acid",
    "formik asit": "formic acid",
    "laktik asit": "lactic acid",
    "tartarik asit": "tartaric acid",
    "malik asit": "malic acid",
    "borik asit": "boric acid",
    "hidroflorik asit": "hydrofluoric acid",
    "perklorik asit": "perchloric acid",
    "nitröz asit": "nitrous acid",
    "sülfüroz asit": "sulfurous acid",
    "kromik asit": "chromic acid",
    "asetilsalisilik asit": "acetylsalicylic acid",
    "benzoik asit": "benzoic acid",
    "propiyonik asit": "propionic acid",
    "bütirik asit": "butyric acid",
    "salisillik asit": "salicylic acid",
    "maleik asit": "maleic acid",
    "fumarik asit": "fumaric acid",
    "akrilik asit": "acrylic acid",
    # Bazlar
    "sodyum hidroksit": "sodium hydroxide",
    "potasyum hidroksit": "potassium hydroxide",
    "kalsiyum hidroksit": "calcium hydroxide",
    "magnezyum hidroksit": "magnesium hydroxide",
    "amonyum hidroksit": "ammonium hydroxide",
    "baryum hidroksit": "barium hydroxide",
    # Alkoller
    "etanol": "ethanol",
    "metanol": "methanol",
    "propanol": "propanol",
    "izopropanol": "isopropanol",
    "izopropil alkol": "isopropanol",
    "bütanol": "butanol",
    "gliserin": "glycerol",
    "gliserol": "glycerol",
    "etilen glikol": "ethylene glycol",
    "propilen glikol": "propylene glycol",
    "benzil alkol": "benzyl alcohol",
    "sikloheksanol": "cyclohexanol",
    "fenol": "phenol",
    # Ketonlar & Aldehitler
    "aseton": "acetone",
    "metil etil keton": "methyl ethyl ketone",
    "sikloheksanon": "cyclohexanone",
    "formaldehit": "formaldehyde",
    "asetaldehit": "acetaldehyde",
    "benzaldehit": "benzaldehyde",
    "glutaraldehit": "glutaraldehyde",
    # Aromatikler
    "benzen": "benzene",
    "toluen": "toluene",
    "ksilen": "xylene",
    "stiren": "styrene",
    "naftalin": "naphthalene",
    "anilin": "aniline",
    "nitrobenzen": "nitrobenzene",
    "klorobenzen": "chlorobenzene",
    "anisol": "anisole",
    "piridin": "pyridine",
    # Halojenli bileşikler
    "kloroform": "chloroform",
    "karbon tetraklorür": "carbon tetrachloride",
    "diklorometan": "dichloromethane",
    "metilen klorür": "dichloromethane",
    "tetrakloroetilen": "tetrachloroethylene",
    "trikloroetilen": "trichloroethylene",
    "vinil klorür": "vinyl chloride",
    "metil klorür": "methyl chloride",
    "etil klorür": "ethyl chloride",
    # Eterler & Esterler
    "eter": "diethyl ether",
    "dietil eter": "diethyl ether",
    "tetrahidrofuran": "tetrahydrofuran",
    "thf": "tetrahydrofuran",
    "dioksan": "dioxane",
    "etil asetat": "ethyl acetate",
    "metil asetat": "methyl acetate",
    "butil asetat": "butyl acetate",
    "izoamil asetat": "isoamyl acetate",
    # Gazlar
    "amonyak": "ammonia",
    "hidrojen": "hydrogen",
    "oksijen": "oxygen",
    "azot": "nitrogen",
    "klor": "chlorine",
    "flor": "fluorine",
    "brom": "bromine",
    "iyot": "iodine",
    "karbon dioksit": "carbon dioxide",
    "kükürt dioksit": "sulfur dioxide",
    "azot dioksit": "nitrogen dioxide",
    "karbon monoksit": "carbon monoxide",
    "hidrojen sülfür": "hydrogen sulfide",
    "hidrojen klorür": "hydrogen chloride",
    "hidrojen florür": "hydrogen fluoride",
    "ozon": "ozone",
    "fosgen": "phosgene",
    # Tuzlar & İnorganikler
    "sodyum klorür": "sodium chloride",
    "potasyum klorür": "potassium chloride",
    "kalsiyum karbonat": "calcium carbonate",
    "sodyum bikarbonat": "sodium bicarbonate",
    "sodyum karbonat": "sodium carbonate",
    "potasyum permanganat": "potassium permanganate",
    "sodyum hipoklorit": "sodium hypochlorite",
    "sodyum sülfat": "sodium sulfate",
    "sodyum nitrat": "sodium nitrate",
    "potasyum nitrat": "potassium nitrate",
    "amonyum nitrat": "ammonium nitrate",
    "amonyum klorür": "ammonium chloride",
    "amonyum sülfat": "ammonium sulfate",
    "kalsiyum klorür": "calcium chloride",
    "magnezyum sülfat": "magnesium sulfate",
    "bakır sülfat": "copper sulfate",
    "demir klorür": "iron chloride",
    "demir sülfat": "iron sulfate",
    "çinko sülfat": "zinc sulfate",
    "alüminyum sülfat": "aluminum sulfate",
    "sodyum florür": "sodium fluoride",
    "potasyum siyanür": "potassium cyanide",
    "sodyum siyanür": "sodium cyanide",
    "baryum klorür": "barium chloride",
    "kurşun nitrat": "lead nitrate",
    "kurşun asetat": "lead acetate",
    "civa klorür": "mercury chloride",
    "gümüş nitrat": "silver nitrate",
    "hidrojen peroksit": "hydrogen peroxide",
    # Elementler
    "demir": "iron",
    "bakır": "copper",
    "çinko": "zinc",
    "alüminyum": "aluminum",
    "kurşun": "lead",
    "civa": "mercury",
    "arsenik": "arsenic",
    "siyanür": "cyanide",
    "kükürt": "sulfur",
    "fosfor": "phosphorus",
    "karbon": "carbon",
    "silisyum": "silicon",
    "kalay": "tin",
    "nikel": "nickel",
    "krom": "chromium",
    "mangan": "manganese",
    "kobalt": "cobalt",
    "gümüş": "silver",
    "altın": "gold",
    "platin": "platinum",
    "titanyum": "titanium",
    "baryum": "barium",
    "kalsiyum": "calcium",
    "magnezyum": "magnesium",
    "sodyum": "sodium",
    "potasyum": "potassium",
    "lityum": "lithium",
    # Çözücüler
    "hekzan": "hexane",
    "heptan": "heptane",
    "oktan": "octane",
    "pentan": "pentane",
    "sikloheksan": "cyclohexane",
    "dimetil sülfoksit": "dimethyl sulfoxide",
    "dmso": "dimethyl sulfoxide",
    "dimetilformamid": "dimethylformamide",
    "dmf": "dimethylformamide",
    "asetonitril": "acetonitrile",
    # Biyokimyasal
    "glikoz": "glucose",
    "fruktoz": "fructose",
    "sakkaroz": "sucrose",
    "laktoz": "lactose",
    "üre": "urea",
    "kafein": "caffeine",
    "kolesterol": "cholesterol",
    # İlaç & Diğer
    "aspirin": "aspirin",
    "parasetamol": "paracetamol",
    "ibuprofen": "ibuprofen",
    "etilen": "ethylene",
    "propilen": "propylene",
    "asetilen": "acetylene",
    "antrasen": "anthracene",
    "indol": "indole",
    "imidazol": "imidazole",
}

def turkce_cevir(ad):
    temiz = ad.strip().lower()
    if temiz in TURKCE_KIMYASAL:
        return TURKCE_KIMYASAL[temiz]
    try:
        from deep_translator import GoogleTranslator
        cevirilen = GoogleTranslator(source='tr', target='en').translate(ad)
        return cevirilen if cevirilen else ad
    except Exception:
        return ad
    
def formul_alt_indis(formul):
    return re.sub(r'(\d+)', lambda m: ''.join(chr(0x2080 + int(d)) for d in m.group()), formul)


def formul_gosterim_duzenle(formul):
    """PubChem'in Hill notasyonu formüllerini daha yaygın kimyasal görünümde gösterir."""
    if not formul:
        return formul

    form = str(formul).strip()
    if not form:
        return form

    subscript_map = str.maketrans({
        '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
        '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9'
    })
    form = form.translate(subscript_map)

    ozel_donustur = {
        'H3N': 'NH₃',
        'NH3': 'NH₃',
        'ClH': 'HCl',
        'HCl': 'HCl',
        'FH': 'HF',
        'HF': 'HF',
        'BrH': 'HBr',
        'HBr': 'HBr',
        'IH': 'HI',
        'HI': 'HI',
        'H2O4S': 'H₂SO₄',
        'H2SO4': 'H₂SO₄',
        'H2O3S': 'H₂SO₃',
        'H2SO3': 'H₂SO₃'
    }

    if form in ozel_donustur:
        return ozel_donustur[form]

    matches = re.findall(r'([A-Z][a-z]?)(\d*)', form)
    if not matches:
        return form

    atomlar = {el: int(cnt) if cnt else 1 for el, cnt in matches}

    if len(atomlar) == 2 and 'H' in atomlar:
        diger = next(el for el in atomlar if el != 'H')

        if diger in {'F', 'Cl', 'Br', 'I'}:
            h_say = atomlar['H']
            diger_say = atomlar[diger]
            result = f"H{'' if h_say == 1 else h_say}{diger}{'' if diger_say == 1 else diger_say}"
            return re.sub(r'(\d+)', lambda m: ''.join(chr(0x2080 + int(d)) for d in m.group()), result)

        if diger in {'N', 'P', 'As', 'Sb'}:
            h_say = atomlar['H']
            diger_say = atomlar[diger]
            result = f"{diger}{'' if diger_say == 1 else diger_say}H{'' if h_say == 1 else h_say}"
            return re.sub(r'(\d+)', lambda m: ''.join(chr(0x2080 + int(d)) for d in m.group()), result)

    if 'H' in atomlar and 'S' in atomlar and 'O' in atomlar:
        h_say = atomlar['H']
        o_say = atomlar['O']
        return f"H{'' if h_say == 1 else h_say}SO{'' if o_say == 1 else o_say}".replace('1', '')

    return re.sub(r'(\d+)', lambda m: ''.join(chr(0x2080 + int(d)) for d in m.group()), form)

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
    "H230": "Hava olmadan patlayarak reaksiyon verebilir",
    "H231": "Yüksek basınç ve/veya sıcaklıkta hava olmadan patlayarak reaksiyon verebilir",
    "H240": "Isıtma patlamaya neden olabilir",
    "H241": "Isıtma yangına veya patlamaya neden olabilir",
    "H242": "Isıtma yangına neden olabilir",
    "H250": "Havayla temas ettiğinde kendiliğinden tutuşur",
    "H251": "Kendiliğinden ısınır; kitleler halinde alev alabilir",
    "H252": "Büyük miktarlarda kendiliğinden ısınır; kitleler halinde alev alabilir",
    "H260": "Su ile temas ettiğinde kendiliğinden tutuşan yanıcı gazlar açığa çıkar",
    "H261": "Su ile temas ettiğinde yanıcı gazlar açığa çıkar",
    "H270": "Yangına neden olabilir veya yoğunlaştırabilir; oksitleyici",
    "H271": "Patlama veya yangına neden olabilir; güçlü oksitleyici",
    "H272": "Yangını yoğunlaştırabilir; oksitleyici",
    "H280": "Basınçlı gaz içerir; ısıtılırsa patlayabilir",
    "H281": "Soğutulmuş gaz içerir; soğuk yanıklara veya yaralanmalara neden olabilir",
    "H290": "Metallere karşı aşındırıcı olabilir",
    "H300": "Yutulması halinde öldürücü",
    "H301": "Yutulması halinde zehirli",
    "H302": "Yutulması halinde zararlı",
    "H303": "Yutulması halinde zararlı olabilir",
    "H304": "Yutulması ve soluk yollarına kaçması halinde öldürücü olabilir",
    "H305": "Yutulması ve soluk yollarına kaçması halinde zararlı olabilir",
    "H310": "Deri ile temasında öldürücü",
    "H311": "Deri ile temasında zehirli",
    "H312": "Deri ile temasında zararlı",
    "H313": "Deri ile temasında zararlı olabilir",
    "H314": "Ciddi deri yanıklarına ve göz hasarına neden olur",
    "H315": "Deri tahrişine neden olur",
    "H316": "Hafif deri tahrişine neden olabilir",
    "H317": "Alerjik deri reaksiyonuna neden olabilir",
    "H318": "Ciddi göz hasarına neden olur",
    "H319": "Ciddi göz tahrişine neden olur",
    "H320": "Göz tahrişine neden olabilir",
    "H330": "Solunması halinde öldürücü",
    "H331": "Solunması halinde zehirli",
    "H332": "Solunması halinde zararlı",
    "H333": "Solunması halinde zararlı olabilir",
    "H334": "Solunması halinde alerji, astım belirtilerine veya soluma güçlüğüne neden olabilir",
    "H335": "Solunum yolu tahrişine neden olabilir",
    "H336": "Uyuşukluğa veya sersemliğe neden olabilir",
    "H340": "Genetik hasara neden olabilir",
    "H341": "Genetik hasara neden olabileceğinden şüphelenilmektedir",
    "H350": "Kansere neden olabilir",
    "H351": "Kansere neden olabileceğinden şüphelenilmektedir",
    "H360": "Doğurganlığa veya doğmamış çocuğa zarar verebilir",
    "H361": "Doğurganlığa veya doğmamış çocuğa zarar verebileceğinden şüphelenilmektedir",
    "H362": "Emzirilen çocuklara zarar verebilir",
    "H370": "Organlara zarar verir",
    "H371": "Organlara zarar verebilir",
    "H372": "Uzun süreli veya tekrarlanan maruziyette organlara zarar verir",
    "H373": "Uzun süreli veya tekrarlanan maruziyette organlara zarar verebilir",
    "H400": "Sucul organizmalar için çok zehirli",
    "H401": "Sucul organizmalar için zehirli",
    "H402": "Sucul organizmalar için zararlı",
    "H410": "Uzun süre kalıcı etkiyle sucul organizmalar için çok zehirli",
    "H411": "Uzun süre kalıcı etkiyle sucul organizmalar için zehirli",
    "H412": "Uzun süre kalıcı etkiyle sucul organizmalar için zararlı",
    "H413": "Sucul organizmalar üzerinde uzun süre kalıcı zararlı etkiler doğurabilir",
    "H420": "Ozon tabakasını tahrip ederek halk sağlığı ve çevreye zarar verir",
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

def kategori_bul(h_kodu):
    prefix = h_kodu[:2]
    return H_KATEGORI.get(prefix, {"isim": "Diğer", "renk": "#95a5a6", "ikon": "❓"})

# ==============================================================================
# 3. KULLANICI SİSTEMİ (KAYIT / GİRİŞ / PROFİL)
# ==============================================================================
SECRET_KEY_PATH = os.path.join(BASE_DIR, ".secret_key")

def gizli_anahtar_al():
    """Oturum anahtarını ortam değişkeninden, yoksa yerel dosyadan alır (yoksa üretir)."""
    anahtar = os.environ.get("SECRET_KEY")
    if anahtar:
        return anahtar
    if os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH) as f:
            return f.read().strip()
    anahtar = secrets.token_hex(32)
    with open(SECRET_KEY_PATH, "w") as f:
        f.write(anahtar)
    return anahtar

app.secret_key = gizli_anahtar_al()

# Uygulama başlarken kullanıcı / favori / blog tabloları yoksa oluşturulur
# (Render'da DATABASE_URL varsa PostgreSQL, yoksa yerel kullanici.db kullanılır)
db.tablolari_olustur()

def giris_gerekli(f):
    """JSON API'leri için: giriş yapılmamışsa 401 döndürür."""
    @wraps(f)
    def sarmal(*args, **kwargs):
        if not session.get('kullanici_id'):
            return jsonify({'hata': 'Bu işlem için giriş yapmalısınız.', 'giris_gerekli': True}), 401
        return f(*args, **kwargs)
    return sarmal

@app.route('/kayit', methods=['GET', 'POST'])
def kayit_sayfasi():
    if session.get('kullanici_id'):
        return redirect(url_for('profil_sayfasi'))

    if request.method == 'POST':
        isim = request.form.get('isim', '').strip()
        soyisim = request.form.get('soyisim', '').strip()
        email = request.form.get('email', '').strip().lower()
        sifre = request.form.get('sifre', '')

        if not isim or not email or not sifre:
            return jsonify({'durum': 'hata', 'mesaj': 'Lütfen zorunlu alanları doldurun.'})
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return jsonify({'durum': 'hata', 'mesaj': 'Geçerli bir email adresi girin.'})
        if len(sifre) < 6:
            return jsonify({'durum': 'hata', 'mesaj': 'Şifre en az 6 karakter olmalı.'})

        try:
            db.calistir(
                "INSERT INTO kullanicilar (isim, soyisim, email, sifre) VALUES (?, ?, ?, ?)",
                (isim, soyisim, email, generate_password_hash(sifre))
            )
        except db.BUTUNLUK_HATASI:
            return jsonify({'durum': 'hata', 'mesaj': 'Bu email adresi zaten sisteme kayıtlı.'})

        flash('Kayıt başarılı! Şimdi giriş yapabilirsiniz.', 'success')
        return jsonify({'durum': 'basarili', 'yonlendir': url_for('giris_yap')})

    return render_template('kayit.html')


@app.route('/giris', methods=['GET', 'POST'])
def giris_yap():
    if session.get('kullanici_id'):
        return redirect(url_for('profil_sayfasi'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        sifre = request.form.get('sifre', '')

        kullanici = db.calistir('SELECT * FROM kullanicilar WHERE email = ?', (email,), tek=True)

        if kullanici and check_password_hash(kullanici['sifre'], sifre):
            session.clear()
            session['kullanici_id'] = kullanici['id']
            session['isim'] = kullanici['isim']
            
            soyisim = kullanici['soyisim'].strip() if kullanici['soyisim'] else ''
            ilk_harf = f" {soyisim[0].upper()}." if soyisim else ''
            session['gosterim_adi'] = f"{kullanici['isim']}{ilk_harf}"
            
            flash('Giriş yapıldı', 'success') 
            return redirect(url_for('index')) 
        else:
            flash('Giriş başarısız. Lütfen email ve şifrenizi kontrol edin.', 'danger')
            return render_template('giris.html', email=email)

    return render_template('giris.html')

@app.route('/profil')
def profil_sayfasi():
    if not session.get('kullanici_id'):
        return redirect(url_for('giris_yap'))
    kullanici = db.calistir(
        'SELECT isim, soyisim, email FROM kullanicilar WHERE id = ?', (session['kullanici_id'],), tek=True
    )
    if not kullanici:
        session.clear()
        return redirect(url_for('giris_yap'))
    favoriler = db.calistir(
        'SELECT isim, formul FROM favoriler WHERE kullanici_id = ? ORDER BY eklenme DESC, id DESC',
        (session['kullanici_id'],), hepsi=True
    )
    return render_template('profil.html', kullanici=kullanici, favoriler=favoriler)

# ---------------- FAVORİLER ----------------
@app.route('/api/favoriler', methods=['GET'])
@giris_gerekli
def favorileri_listele():
    favoriler = db.calistir(
        'SELECT isim, formul, cid FROM favoriler WHERE kullanici_id = ? ORDER BY eklenme DESC, id DESC',
        (session['kullanici_id'],), hepsi=True
    )
    return jsonify({'favoriler': favoriler})

@app.route('/api/favoriler', methods=['POST'])
@giris_gerekli
def favori_ekle():
    veri = request.get_json(silent=True) or {}
    isim = str(veri.get('isim', '')).strip()[:200]
    if not isim:
        return jsonify({'hata': 'Kimyasal adı eksik.'}), 400
    formul = str(veri.get('formul') or '')[:100]
    try:
        cid = int(veri['cid']) if veri.get('cid') else None
    except (TypeError, ValueError):
        cid = None
    try:
        db.calistir(
            'INSERT INTO favoriler (kullanici_id, isim, formul, cid, eklenme) VALUES (?, ?, ?, ?, ?)',
            (session['kullanici_id'], isim, formul, cid, db.simdi())
        )
    except db.BUTUNLUK_HATASI:
        return jsonify({'durum': 'zaten_var', 'mesaj': f'{isim} zaten favorilerinde.'})
    return jsonify({'durum': 'eklendi', 'mesaj': f'{isim} favorilere eklendi! ♡'})

@app.route('/api/favoriler/sil', methods=['POST'])
@giris_gerekli
def favori_sil():
    veri = request.get_json(silent=True) or {}
    db.calistir(
        'DELETE FROM favoriler WHERE kullanici_id = ? AND isim = ?',
        (session['kullanici_id'], str(veri.get('isim', '')).strip())
    )
    return jsonify({'durum': 'silindi'})

# ---------------- BLOG ----------------
def blog_formu_oku():
    veri = request.get_json(silent=True) or {}
    baslik = str(veri.get('baslik', '')).strip()[:200]
    etiket = str(veri.get('etiket', '')).strip()[:60] or 'Kimya'
    icerik = str(veri.get('icerik', '')).strip()[:20000]
    return baslik, etiket, icerik

@app.route('/api/blog', methods=['GET'])
def bloglari_listele():
    yazilar = db.calistir(
        'SELECT id, kullanici_id, yazar, baslik, etiket, icerik, tarih FROM blog_yazilari ORDER BY tarih DESC, id DESC',
        hepsi=True
    )
    benim_id = session.get('kullanici_id')
    for y in yazilar:
        sahip_id = y.pop('kullanici_id')
        y['sahibi_mi'] = benim_id is not None and sahip_id == benim_id
        y['tarih'] = y['tarih'][:10]
    return jsonify({'yazilar': yazilar, 'giris_yapildi': benim_id is not None})

@app.route('/api/blog', methods=['POST'])
@giris_gerekli
def blog_ekle():
    baslik, etiket, icerik = blog_formu_oku()
    if not baslik or not icerik:
        return jsonify({'hata': 'Lütfen en azından bir başlık ve yazı içeriği girin.'}), 400
    db.calistir(
        'INSERT INTO blog_yazilari (kullanici_id, yazar, baslik, etiket, icerik, tarih) VALUES (?, ?, ?, ?, ?, ?)',
        (session['kullanici_id'], session.get('gosterim_adi', 'Anonim'), baslik, etiket, icerik, db.simdi())
    )
    return jsonify({'durum': 'eklendi'})

def yazi_sahibi_kontrol(yazi_id):
    yazi = db.calistir('SELECT kullanici_id FROM blog_yazilari WHERE id = ?', (yazi_id,), tek=True)
    if not yazi:
        return jsonify({'hata': 'Yazı bulunamadı.'}), 404
    if yazi['kullanici_id'] != session['kullanici_id']:
        return jsonify({'hata': 'Sadece kendi yazılarınızı değiştirebilirsiniz.'}), 403
    return None

@app.route('/api/blog/<int:yazi_id>', methods=['PUT'])
@giris_gerekli
def blog_duzenle(yazi_id):
    hata = yazi_sahibi_kontrol(yazi_id)
    if hata:
        return hata
    baslik, etiket, icerik = blog_formu_oku()
    if not baslik or not icerik:
        return jsonify({'hata': 'Lütfen en azından bir başlık ve yazı içeriği girin.'}), 400
    db.calistir(
        'UPDATE blog_yazilari SET baslik = ?, etiket = ?, icerik = ? WHERE id = ?',
        (baslik, etiket, icerik, yazi_id)
    )
    return jsonify({'durum': 'guncellendi'})

@app.route('/api/blog/<int:yazi_id>', methods=['DELETE'])
@giris_gerekli
def blog_sil(yazi_id):
    hata = yazi_sahibi_kontrol(yazi_id)
    if hata:
        return hata
    db.calistir('DELETE FROM blog_yazilari WHERE id = ?', (yazi_id,))
    return jsonify({'durum': 'silindi'})

@app.route('/cikis')
def cikis_yap():
    session.clear()
    flash('Çıkış yapıldı', 'success')
    return redirect(url_for('index'))


# ==============================================================================
# 4. UYGULAMA ROTALARI (ROUTES)
# ==============================================================================
@app.route("/saglik")
def saglik():
    """Uyanık tutma servisleri (ör. UptimeRobot) için hafif kontrol adresi."""
    return "ok"

@app.route("/")
def index():
    return render_template("index.html", karisim_onerileri=karisim.oneri_listesi())


@app.route("/ara", methods=["POST"])
def ara():
    kimyasal_girdi = request.json.get("kimyasal", "").strip()
    if not kimyasal_girdi:
        return jsonify({"hata": "Kimyasal adı boş olamaz."})

    kimyasal = kimyasal_girdi

    # --- 🛠️ SÜLFÜRİK ASİT İÇİN KESİN VE MANUEL DÜZELTME ---
    if kimyasal_girdi.lower() in ["sülfürik asit", "sulfuric acid"]:
        # Yerel veritabanına bakmadan doğrudan sülfürik asidin doğru verilerini dönüyoruz
        # 1. Önce normal yerel aramayı yapıp veriyi çekelim
        yerel_sonuc = yerelden_getir(kimyasal_girdi)
        if yerel_sonuc:
            # Sadece formül kısmını manuel olarak H₂SO₄ yapıp frontend'e gönderiyoruz
            yerel_sonuc["formul"] = "H₂SO₄"
            return jsonify(yerel_sonuc)
    # -----------------------------------------------------

    # 1. Önce doğrudan girdi ismiyle yerel veritabanına bak
    yerel_sonuc = yerelden_getir(kimyasal_girdi)
    # ... (kodun geri kalan kısmı aynen devam ediyor)

    if yerel_sonuc:
        return jsonify(yerel_sonuc)

    # 3. Yerelde bulunamazsa PubChem API üzerinden indir
    compounds = pcp.get_compounds(kimyasal, "name")
    if not compounds:
        return jsonify({"hata": f"'{kimyasal_girdi}' bulunamadı. Farklı bir yazım deneyebilirsiniz."})

    c = compounds[0]

    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{requests.utils.quote(kimyasal)}/cids/JSON"
    res = requests.get(url, timeout=10)
    if res.status_code != 200 or "IdentifierList" not in res.json():
        return jsonify({"hata": "CID alınamadı."})

    cid = res.json()["IdentifierList"]["CID"][0]
    yapi_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG?record_type=2d&image_size=600x600"
    data_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON"
    data = requests.get(data_url, timeout=10).json()

    def ghs_find(sections):
        for s in sections:
            if s.get("TOCHeading") == "GHS Classification":
                return s
            if "Section" in s:
                r = ghs_find(s["Section"])
                if r:
                    return r
        return None

    try:
        sections = data["Record"]["Section"]
    except Exception:
        return jsonify({"hata": "GHS verisi alınamadı."})

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
        kat = kategori_bul(kod)
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

    formul = formul_gosterim_duzenle(formul_alt_indis(c.molecular_formula))

    sonuc = {
        "isim": kimyasal_girdi.title(),
        "formul": formul,
        "agirlik": str(c.molecular_weight),
        "cid": cid,
        "yapi_url": yapi_url,
        "h_kodlari": h_listesi,
        "piktogramlar": pikt_listesi,
    }

    # 4. Çekilen sonucu yerel veritabanına kaydet (sonraki aramalar için anında hız)
    yerele_kaydet(kimyasal_girdi, sonuc)
    if kimyasal.lower() != kimyasal_girdi.lower():
        yerele_kaydet(kimyasal, sonuc)

    return jsonify(sonuc)


@app.route("/api/karisim", methods=["POST"])
def karisim_kontrol():
    veri = request.get_json(silent=True) or {}
    k1 = str(veri.get("kimyasal1", "")).strip()[:100]
    k2 = str(veri.get("kimyasal2", "")).strip()[:100]
    if not k1 or not k2:
        return jsonify({"hata": "Lütfen iki kimyasalın da adını yazın."}), 400
    return jsonify(karisim.kontrol(k1, k2, yerel_getir=yerelden_getir))


@app.route("/pdf", methods=["POST"])
def pdf_rapor():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_path = os.path.join(BASE_DIR, 'DejaVuSans.ttf')
    font_bold_path = os.path.join(BASE_DIR, 'DejaVuSans-Bold.ttf')
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('DejaVu', font_path))
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', font_bold_path))
        FONT = 'DejaVu'
        FONT_BOLD = 'DejaVu-Bold'
    else:
        FONT = 'Helvetica'
        FONT_BOLD = 'Helvetica-Bold'

    veri = request.json
    isim = veri.get("isim", "")
    formul = veri.get("formul", "")
    agirlik = veri.get("agirlik", "")
    cid = veri.get("cid", "")
    h_kodlari = veri.get("h_kodlari", [])
    piktogramlar = veri.get("piktogramlar", [])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    story = []

    baslik_style = ParagraphStyle('baslik', parent=styles['Title'],
                                   fontSize=22, spaceAfter=6,
                                   textColor=colors.HexColor('#1a1a2e'))
    story.append(Paragraph("kimyasal — Tehlike Raporu", baslik_style))

    alt_baslik_style = ParagraphStyle('altbaslik', parent=styles['Normal'],
                                       fontSize=13, spaceAfter=16,
                                       textColor=colors.HexColor('#5ce1e6'))
    story.append(Paragraph(isim, alt_baslik_style))

    mol_data = [
        ['Kimyasal Formül', formul],
        ['Mol Ağırlığı', f"{agirlik} g/mol"],
    ]
    mol_table = Table(mol_data, colWidths=[5*cm, 10*cm])
    mol_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f4f8')),
        ('FONTNAME', (0, 0), (-1, -1), FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#f0f8ff'), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(mol_table)
    story.append(Spacer(1, 0.5*cm))

    if cid:
        try:
            img_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG?record_type=2d&image_size=250x250"
            img_resp = requests.get(img_url, timeout=10)
            if img_resp.status_code == 200:
                img_buf = io.BytesIO(img_resp.content)
                mol_img = Image(img_buf, width=6*cm, height=6*cm)
                story.append(Paragraph("<b>Molekül Yapısı</b>", styles['Heading2']))
                story.append(mol_img)
                story.append(Spacer(1, 0.3*cm))
        except Exception:
            pass

    if piktogramlar:
        story.append(Paragraph("<b>GHS Piktogramları</b>", styles['Heading2']))
        pikt_text = "  |  ".join([p['isim'] for p in piktogramlar])
        story.append(Paragraph(pikt_text, styles['Normal']))
        story.append(Spacer(1, 0.5*cm))

    if h_kodlari:
        story.append(Paragraph("<b>Tehlike Bildirimleri (H Kodları)</b>", styles['Heading2']))
        story.append(Spacer(1, 0.2*cm))

        h_data = [['Kod', 'Açıklama', 'Kategori']]
        for h in h_kodlari:
            h_data.append([h['kod'], h['tr'], h['kategori']])

        h_table = Table(h_data, colWidths=[2*cm, 10*cm, 4*cm])
        h_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9f9f9'), colors.white]),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#dddddd')),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('FONTNAME', (0, 1), (0, -1), FONT),
        ]))
        story.append(h_table)

    story.append(Spacer(1, 1*cm))
    footer_style = ParagraphStyle('footer', parent=styles['Normal'],
                                   fontSize=8, textColor=colors.grey)
    story.append(Paragraph("Kaynak: PubChem (pubchem.ncbi.nlm.nih.gov) | kimyasal.onrender.com", footer_style))

    doc.build(story)
    buffer.seek(0)

    return send_file(buffer, mimetype='application/pdf',
                     as_attachment=True,
                     download_name=f"{isim.replace(' ', '_')}_tehlike_raporu.pdf")


# "gemini-flash-lite-latest" Google'ın en hızlı güncel Flash modelini gösteren takma addır;
# varsayılan olarak "düşünme" adımı olmadığı için cevaplar çok daha çabuk gelir.
# Daha güçlü (ama daha yavaş) cevaplar için .env içinde GEMINI_MODEL=gemini-flash-latest yazılabilir.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")

@app.route("/ai", methods=["POST"])
def ai_sohbet():
    # Render gibi panellere yapıştırırken anahtarın sonuna eklenen boşluk/Enter'ı temizle
    api_key = os.environ.get("GEMINI_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        return jsonify({"hata": "Yapay zeka anahtarı ayarlanmamış (GEMINI_API_KEY)."})

    veri = request.get_json(silent=True) or {}
    mesajlar = veri.get("mesajlar", [])[-20:]
    if not mesajlar:
        return jsonify({"hata": "Mesaj boş olamaz."})

    sistem = (
        "Sen KimyaSal platformunun kimya asistanisin. Adin KimyaBot. "
        "Kimya, kimyasal guvenlik, GHS tehlike bilgileri, laboratuvar guvenligi, "
        "molekuler yapilar ve kimyasal reaksiyonlar hakkinda uzman bilgiye sahipsin. "
        "Turkce konus. Kisa ve net cevaplar ver. Tehlikeli kullanimlara yonlendirme. "
        "Guvenlik konularinda her zaman dikkatli ol ve uyari ver. "
        "Kimyasal formulleri LaTeX ($...$) KULLANMADAN, Unicode alt/ust simgelerle yaz: "
        "ornegin H₂SO₄, CO₂, Fe³⁺, SO₄²⁻, 2H₂ + O₂ → 2H₂O."
    )

    icerik = [
        {"role": "user" if m["rol"] == "user" else "model", "parts": [{"text": m["icerik"]}]}
        for m in mesajlar
    ]

    # Cevabı parça parça (akış halinde) iste; ilk kelimeler hemen ekrana gelsin
    try:
        res = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:streamGenerateContent?alt=sse",
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json={
                "system_instruction": {"parts": [{"text": sistem}]},
                "contents": icerik,
                "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.7}
            },
            stream=True,
            timeout=(10, 60)
        )
    except requests.Timeout:
        return jsonify({"hata": "Yapay zekaya bağlanılamadı, lütfen tekrar deneyin."})
    except Exception as e:
        # Hata metninde API anahtarı geçebilir; kullanıcıya gösterme, sadece sunucu loguna yaz
        app.logger.error("Gemini isteği başarısız: %s", str(e).replace(api_key, "***"))
        return jsonify({"hata": "Yapay zekaya bağlanırken bir sorun oluştu, lütfen tekrar deneyin."})

    if res.status_code != 200:
        try:
            mesaj = res.json()["error"].get("message", "Bilinmeyen hata")
        except Exception:
            mesaj = f"Yapay zeka hatası (kod {res.status_code})"
        res.close()
        return jsonify({"hata": mesaj})

    def akis():
        bos = True
        try:
            # Satırları ham bayt olarak alıp UTF-8 ile çözüyoruz; aksi halde
            # requests Türkçe karakterleri yanlış kodlamayla okur (ı -> Ä±)
            for satir in res.iter_lines():
                satir = satir.decode("utf-8")
                if not satir.startswith("data:"):
                    continue
                parca = json.loads(satir[5:])
                parcalar = (parca.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
                metin = "".join(p.get("text", "") for p in parcalar)
                if metin:
                    bos = False
                    yield metin
            if bos:
                yield "Yapay zekadan cevap alınamadı, lütfen tekrar deneyin."
        except Exception:
            yield "\n\n(Bağlantı koptu, cevap yarım kalmış olabilir.)"
        finally:
            res.close()

    # "text/event-stream" türü, Render'ın önündeki Cloudflare gibi ara sunucuların
    # cevabı biriktirmeden (kelime kelime) iletmesini sağlar; "no-transform" sıkıştırmayı kapatır.
    return Response(stream_with_context(akis()), content_type="text/event-stream; charset=utf-8",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache, no-transform"})

if __name__ == "__main__":
    app.run(debug=False)
