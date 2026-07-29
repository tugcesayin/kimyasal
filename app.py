from flask import Flask, render_template, request, jsonify
import pubchempy as pcp
import requests
import re

app = Flask(__name__)

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
    # Önce kendi listemize bak
    if temiz in TURKCE_KIMYASAL:
        return TURKCE_KIMYASAL[temiz]
    # Listede yoksa deep-translator ile çevir
    try:
        from deep_translator import GoogleTranslator
        cevirilen = GoogleTranslator(source='tr', target='en').translate(ad)
        return cevirilen if cevirilen else ad
    except Exception:
        return ad

def hill_sirala(formul):
    import re
    # Elementleri parse et
    elementler = re.findall(r'([A-Z][a-z]?)(\d*)', formul)
    sayac = {}
    for el, sayi in elementler:
        if el:
            sayac[el] = sayac.get(el, 0) + (int(sayi) if sayi else 1)
    
    # Hill sırası: C önce, H sonra, geri kalanlar alfabetik
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
    "Explosive": {"sembol": "", "renk": "#ff6b35", "isim": "Patlayici"},
    "Flammable": {"sembol": "", "renk": "#ff4500", "isim": "Yanici"},
    "Oxidizer": {"sembol": "", "renk": "#ffa500", "isim": "Oksitleyici"},
    "Compressed Gas": {"sembol": "", "renk": "#4a90d9", "isim": "Basinçli Gaz"},
    "Corrosive": {"sembol": "", "renk": "#8b4513", "isim": "Asindirici"},
    "Toxic": {"sembol": "", "renk": "#800080", "isim": "Zehirli"},
    "Harmful": {"sembol": "", "renk": "#ffd700", "isim": "Zararli"},
    "Health Hazard": {"sembol": "", "renk": "#dc143c", "isim": "Saglik Tehlikesi"},
    "Environmental Hazard": {"sembol": "", "renk": "#228b22", "isim": "Cevre Tehlikesi"},
}

H_KATEGORI = {
    "H2": {"isim": "Fiziksel Tehlike", "renk": "#ff6b35", "ikon": "!"},
    "H3": {"isim": "Saglik Tehlikesi", "renk": "#e74c3c", "ikon": "+"},
    "H4": {"isim": "Cevre Tehlikesi", "renk": "#27ae60", "ikon": "*"},
}


def kategori_bul(h_kodu):
    prefix = h_kodu[:2]
    return H_KATEGORI.get(prefix, {"isim": "Diğer", "renk": "#95a5a6", "ikon": "❓"})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ara", methods=["POST"])
def ara():
    kimyasal_girdi = request.json.get("kimyasal", "").strip()
    if not kimyasal_girdi:
        return jsonify({"hata": "Kimyasal adı boş olamaz."})

    kimyasal = turkce_cevir(kimyasal_girdi)

    compounds = pcp.get_compounds(kimyasal, "name")
    if not compounds:
        return jsonify({"hata": f"'{kimyasal_girdi}' bulunamadı. Farklı bir yazım deneyebilirsiniz."})

    c = compounds[0]

    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{requests.utils.quote(kimyasal)}/cids/JSON"
    res = requests.get(url)
    if res.status_code != 200 or "IdentifierList" not in res.json():
        return jsonify({"hata": "CID alınamadı."})

    cid = res.json()["IdentifierList"]["CID"][0]

    yapi_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG?record_type=2d&image_size=600x600"

    data_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON"
    data = requests.get(data_url).json()

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
        return jsonify({"hata": "Veri alınamadı."})

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

    return jsonify({
        "isim": kimyasal_girdi.title(),
        "formul": formul_alt_indis(hill_sirala(c.molecular_formula)),
        "agirlik": str(c.molecular_weight),
        "cid": cid,
        "yapi_url": yapi_url,
        "h_kodlari": h_listesi,
        "piktogramlar": pikt_listesi,
    })



@app.route("/pdf", methods=["POST"])
def pdf_rapor():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import io

    import os as _os
    BASE_DIR = _os.path.dirname(_os.path.abspath(__file__))
    font_path = _os.path.join(BASE_DIR, 'DejaVuSans.ttf')
    font_bold_path = _os.path.join(BASE_DIR, 'DejaVuSans-Bold.ttf')
    if _os.path.exists(font_path):
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

    # Başlık
    baslik_style = ParagraphStyle('baslik', parent=styles['Title'],
                                   fontSize=22, spaceAfter=6,
                                   textColor=colors.HexColor('#1a1a2e'))
    story.append(Paragraph(f"KimyaSal — Tehlike Raporu", baslik_style))

    alt_baslik_style = ParagraphStyle('altbaslik', parent=styles['Normal'],
                                       fontSize=13, spaceAfter=16,
                                       textColor=colors.HexColor('#5ce1e6'))
    story.append(Paragraph(isim, alt_baslik_style))

    # Mol bilgisi tablosu
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

    # Molekül yapı resmi
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

    # Piktogramlar
    if piktogramlar:
        story.append(Paragraph("<b>GHS Piktogramları</b>", styles['Heading2']))
        pikt_text = "  |  ".join([p['isim'] for p in piktogramlar])
        story.append(Paragraph(pikt_text, styles['Normal']))
        story.append(Spacer(1, 0.5*cm))

    # H Kodları
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
    story.append(Paragraph(f"Kaynak: PubChem (pubchem.ncbi.nlm.nih.gov) | kimyasal.onrender.com", footer_style))

    doc.build(story)
    buffer.seek(0)

    from flask import send_file
    return send_file(buffer, mimetype='application/pdf',
                     as_attachment=True,
                     download_name=f"{isim.replace(' ', '_')}_tehlike_raporu.pdf")



@app.route("/ai", methods=["POST"])
def ai_sohbet():
    import os
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return jsonify({"hata": "API key bulunamadi."})

    veri = request.json
    mesajlar = veri.get("mesajlar", [])

    sistem = (
        "Sen KimyaSal platformunun kimya asistanisin. Adin KimyaBot. "
        "Kimya, kimyasal guvenlik, GHS tehlike bilgileri, laboratuvar guvenligi, "
        "molekuler yapilar ve kimyasal reaksiyonlar hakkinda uzman bilgiye sahipsin. "
        "Turkce konus. Kisa ve net cevaplar ver. Tehlikeli kullanimlara yonlendirme. "
        "Guvenlik konularinda her zaman dikkatli ol ve uyari ver."
    )

    gecmis = []
    for m in mesajlar[:-1]:
        rol = "user" if m["rol"] == "user" else "model"
        gecmis.append({"role": rol, "parts": [{"text": m["icerik"]}]})

    son_mesaj = mesajlar[-1]["icerik"] if mesajlar else ""

    try:
        res = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {"parts": [{"text": sistem}]},
                "contents": gecmis + [{"role": "user", "parts": [{"text": son_mesaj}]}],
                "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.7}
            }
        )
        data = res.json()
        cevap = data["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"cevap": cevap})
    except Exception as e:
        return jsonify({"hata": str(e)})


if __name__ == "__main__":
    app.run(debug=False)
