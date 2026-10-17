"""
Karışım güvenliği kontrolü.

İki kimyasalı önce bilinen isimlerden (Türkçe/İngilizce, ev ürünleri dahil) sınıflara ayırır,
tanınmazsa yerel kimyasal veritabanındaki GHS H kodlarından sınıf çıkarır, sonra bilinen
tehlikeli tepkime kurallarını uygular.

Bu bir eğitim aracıdır; kesin bilgi için her zaman kimyasalın Güvenlik Bilgi Formu (SDS)
kontrol edilmelidir.
"""
import re

# --------------------------------------------------------------------------------------
# Sınıflar
# --------------------------------------------------------------------------------------
HIPOKLORIT = "hipoklorit"
GUCLU_ASIT = "guclu_asit"
ZAYIF_ASIT = "zayif_asit"
GUCLU_BAZ = "guclu_baz"
ZAYIF_BAZ = "zayif_baz"
AMONYAK = "amonyak"
OKSITLEYICI = "oksitleyici"
PEROKSIT = "peroksit"
PERMANGANAT = "permanganat"
YANICI = "yanici"
SU_REAKTIF = "su_reaktif"
AKTIF_METAL = "aktif_metal"
SIYANUR = "siyanur"
SULFUR = "sulfur"
SU = "su"
NOTR = "notr"

SINIF_ADLARI = {
    HIPOKLORIT: "klorlu ağartıcı",
    GUCLU_ASIT: "güçlü asit",
    ZAYIF_ASIT: "zayıf asit",
    GUCLU_BAZ: "güçlü baz",
    ZAYIF_BAZ: "zayıf baz / karbonat",
    AMONYAK: "amonyak",
    OKSITLEYICI: "oksitleyici",
    PEROKSIT: "peroksit",
    PERMANGANAT: "permanganat",
    YANICI: "yanıcı",
    SU_REAKTIF: "su ile tehlikeli tepkime veren",
    AKTIF_METAL: "aktif metal",
    SIYANUR: "siyanür",
    SULFUR: "sülfür",
    SU: "su",
    NOTR: "tepkimesi düşük",
}

# İçinde su bulunan / sulu çözelti olarak satılan sınıflar (su ile tepkime verenler için)
SULU = {SU, HIPOKLORIT, GUCLU_ASIT, ZAYIF_ASIT, GUCLU_BAZ, AMONYAK, PEROKSIT}
HER_ASIT = {GUCLU_ASIT, ZAYIF_ASIT}

# --------------------------------------------------------------------------------------
# Bilinen kimyasallar: (görünen ad, sınıflar, isimler/eş anlamlılar)
# --------------------------------------------------------------------------------------
KIMYASALLAR = [
    ("Çamaşır suyu (sodyum hipoklorit)", {HIPOKLORIT},
     ["çamaşır suyu", "sodyum hipoklorit", "hipoklorit", "naocl", "ağartıcı", "bleach", "sodium hypochlorite"]),
    ("Klorlu havuz/tablet kimyasalı", {HIPOKLORIT, OKSITLEYICI},
     ["havuz kloru", "klor tablet", "klor tableti", "kalsiyum hipoklorit", "trikloroizosiyanürik asit",
      "calcium hypochlorite", "pool chlorine"]),
    ("Tuz ruhu (hidroklorik asit)", {GUCLU_ASIT},
     ["tuz ruhu", "hidroklorik asit", "hidroklorik asid", "hcl", "muriatik asit", "hydrochloric acid"]),
    ("Kireç çözücü (asitli)", {GUCLU_ASIT}, ["kireç çözücü", "kireç sökücü", "pas sökücü"]),
    ("Sülfürik asit", {GUCLU_ASIT},
     ["sülfürik asit", "sulfürik asit", "h2so4", "akü asidi", "zaç yağı", "sulfuric acid"]),
    ("Nitrik asit (kezzap)", {GUCLU_ASIT, OKSITLEYICI}, ["nitrik asit", "kezzap", "hno3", "nitric acid"]),
    ("Fosforik asit", {GUCLU_ASIT}, ["fosforik asit", "h3po4", "phosphoric acid"]),
    ("Hidroflorik asit", {GUCLU_ASIT}, ["hidroflorik asit", "hf", "hydrofluoric acid"]),
    ("Formik asit", {GUCLU_ASIT}, ["formik asit", "karınca asidi", "formic acid"]),
    ("Sirke (asetik asit)", {ZAYIF_ASIT}, ["sirke", "asetik asit", "ch3cooh", "acetic acid", "vinegar"]),
    ("Sitrik asit (limon tuzu)", {ZAYIF_ASIT},
     ["limon tuzu", "sitrik asit", "limon suyu", "citric acid"]),
    ("Oksalik asit", {ZAYIF_ASIT}, ["oksalik asit", "okzalik asit", "oxalic acid"]),
    ("Borik asit", {ZAYIF_ASIT}, ["borik asit", "boric acid"]),
    ("Sodyum hidroksit (kostik)", {GUCLU_BAZ},
     ["sodyum hidroksit", "kostik", "kostik soda", "naoh", "lavabo açıcı", "sodium hydroxide", "lye"]),
    ("Potasyum hidroksit", {GUCLU_BAZ}, ["potasyum hidroksit", "koh", "potassium hydroxide"]),
    ("Sönmüş kireç (kalsiyum hidroksit)", {GUCLU_BAZ},
     ["kalsiyum hidroksit", "sönmüş kireç", "kireç", "calcium hydroxide"]),
    ("Amonyak", {AMONYAK},
     ["amonyak", "amonyum hidroksit", "nh3", "amonyaklı temizleyici", "ammonia", "ammonium hydroxide"]),
    ("Karbonat (sodyum bikarbonat)", {ZAYIF_BAZ},
     ["karbonat", "sodyum bikarbonat", "yemek sodası", "nahco3", "sodium bicarbonate", "baking soda"]),
    ("Çamaşır sodası (sodyum karbonat)", {ZAYIF_BAZ},
     ["çamaşır sodası", "sodyum karbonat", "na2co3", "sodium carbonate"]),
    ("Hidrojen peroksit (oksijenli su)", {OKSITLEYICI, PEROKSIT},
     ["hidrojen peroksit", "oksijenli su", "perhidrol", "h2o2", "hydrogen peroxide"]),
    ("Potasyum permanganat", {OKSITLEYICI, PERMANGANAT},
     ["potasyum permanganat", "permanganat", "kmno4", "potassium permanganate"]),
    ("Potasyum nitrat (güherçile)", {OKSITLEYICI},
     ["potasyum nitrat", "güherçile", "kno3", "potassium nitrate"]),
    ("Klorat", {OKSITLEYICI},
     ["sodyum klorat", "potasyum klorat", "sodium chlorate", "potassium chlorate"]),
    ("Etanol (alkol)", {YANICI},
     ["etanol", "etil alkol", "alkol", "kolonya", "ethanol", "ethyl alcohol"]),
    ("Metanol", {YANICI}, ["metanol", "metil alkol", "methanol"]),
    ("İzopropil alkol", {YANICI},
     ["izopropanol", "izopropil alkol", "isopropanol", "isopropyl alcohol"]),
    ("Aseton", {YANICI}, ["aseton", "oje çıkarıcı", "acetone"]),
    ("Benzin", {YANICI}, ["benzin", "gasoline", "petrol"]),
    ("Tiner", {YANICI}, ["tiner", "thinner"]),
    ("Gazyağı / mazot", {YANICI}, ["gazyağı", "mazot", "dizel", "kerosene", "diesel"]),
    ("Dietil eter", {YANICI}, ["dietil eter", "eter", "diethyl ether", "ether"]),
    ("Toluen", {YANICI}, ["toluen", "toluene"]),
    ("Ksilen", {YANICI}, ["ksilen", "xylene"]),
    ("Hekzan", {YANICI}, ["hekzan", "heksan", "hexane"]),
    ("Benzen", {YANICI}, ["benzen", "benzene"]),
    ("Sodyum (metal)", {SU_REAKTIF}, ["sodyum metal", "metalik sodyum", "sodyum", "sodium metal"]),
    ("Potasyum (metal)", {SU_REAKTIF}, ["potasyum metal", "metalik potasyum", "potasyum", "potassium metal"]),
    ("Lityum (metal)", {SU_REAKTIF}, ["lityum", "lithium"]),
    ("Kalsiyum karbür", {SU_REAKTIF}, ["kalsiyum karbür", "karbür", "calcium carbide"]),
    ("Alüminyum", {AKTIF_METAL}, ["alüminyum", "alüminyum folyo", "aluminium", "aluminum"]),
    ("Çinko", {AKTIF_METAL}, ["çinko", "zinc"]),
    ("Magnezyum", {AKTIF_METAL}, ["magnezyum", "magnesium"]),
    ("Siyanür tuzu", {SIYANUR},
     ["sodyum siyanür", "potasyum siyanür", "siyanür", "sodium cyanide", "potassium cyanide"]),
    ("Sodyum sülfür", {SULFUR}, ["sodyum sülfür", "sodyum sülfit", "sodium sulfide"]),
    ("Su", {SU}, ["su", "saf su", "distile su", "h2o", "water"]),
    ("Sofra tuzu (sodyum klorür)", {NOTR}, ["tuz", "sofra tuzu", "sodyum klorür", "nacl", "sodium chloride"]),
    ("Şeker", {NOTR}, ["şeker", "sakkaroz", "glikoz", "sugar", "glucose"]),
]

# --------------------------------------------------------------------------------------
# Kurallar: (1. sınıflar, 2. sınıflar, seviye, başlık, açıklama)
# Seviye: 3 = tehlikeli, 2 = dikkat, 1 = bilgi
# --------------------------------------------------------------------------------------
TEHLIKELI, DIKKAT, BILGI = 3, 2, 1

KURALLAR = [
    ({HIPOKLORIT}, HER_ASIT, TEHLIKELI, "Zehirli klor gazı",
     "Klorlu ağartıcılar asitlerle karışınca zehirli klor gazı (Cl₂) açığa çıkar. "
     "Solunması öksürük, nefes darlığı ve ciddi akciğer hasarına yol açabilir."),
    ({HIPOKLORIT}, {AMONYAK}, TEHLIKELI, "Zehirli kloramin gazları",
     "Çamaşır suyu ile amonyak karışınca zehirli kloramin gazları oluşur. "
     "Kapalı alanda solunması hayati tehlike yaratabilir."),
    ({HIPOKLORIT}, {YANICI}, TEHLIKELI, "Zehirli klorlu bileşikler",
     "Klorlu ağartıcılar alkol veya aseton gibi organik çözücülerle tepkimeye girerek "
     "kloroform gibi zehirli bileşikler oluşturabilir."),
    ({HIPOKLORIT}, {PEROKSIT}, DIKKAT, "Şiddetli köpürme ve gaz çıkışı",
     "Hipoklorit ile hidrojen peroksit şiddetli tepkimeye girer ve hızla oksijen gazı açığa çıkar. "
     "Kapalı kapta basınç oluşup patlamaya neden olabilir."),
    ({SIYANUR}, HER_ASIT, TEHLIKELI, "Ölümcül hidrojen siyanür gazı",
     "Siyanür tuzları asitlerle temas edince son derece zehirli hidrojen siyanür (HCN) gazı açığa çıkar."),
    ({SULFUR}, HER_ASIT, TEHLIKELI, "Zehirli hidrojen sülfür gazı",
     "Sülfür tuzları asitlerle temas edince zehirli hidrojen sülfür (H₂S, çürük yumurta kokulu) gazı oluşur."),
    ({PERMANGANAT}, {GUCLU_ASIT}, TEHLIKELI, "Patlayıcı ürün oluşabilir",
     "Potasyum permanganat derişik asitlerle (özellikle sülfürik asit) patlayıcı ve "
     "son derece reaktif ürünler oluşturabilir."),
    ({OKSITLEYICI}, {YANICI}, TEHLIKELI, "Yangın ve patlama riski",
     "Oksitleyiciler yanıcı maddelerin tutuşmasını kolaylaştırır; karışım kendiliğinden alev "
     "alabilir veya patlayabilir."),
    ({SU_REAKTIF}, SULU, TEHLIKELI, "Yanıcı hidrojen gazı ve alev",
     "Bu madde suyla (veya sulu çözeltilerle) şiddetli tepkimeye girer; açığa çıkan yanıcı gaz "
     "alev alabilir veya patlayabilir."),
    ({SU_REAKTIF}, {YANICI, OKSITLEYICI}, DIKKAT, "Yangın riski",
     "Su ile tepkime veren metaller yanıcı veya oksitleyici maddelerle birlikte yangın riskini artırır."),
    ({PEROKSIT}, {ZAYIF_ASIT}, DIKKAT, "Aşındırıcı perasetik asit",
     "Hidrojen peroksit ile sirke aynı kapta karıştırılınca cilde, göze ve solunum yollarına "
     "zarar veren aşındırıcı perasetik asit oluşabilir."),
    ({GUCLU_ASIT}, {GUCLU_BAZ}, DIKKAT, "Şiddetli ısı ve sıçrama",
     "Güçlü asit ile güçlü baz nötrleşirken çok fazla ısı açığa çıkar; karışım kaynayıp sıçrayabilir."),
    ({GUCLU_ASIT}, {AMONYAK}, DIKKAT, "Isı ve tahriş edici duman",
     "Güçlü asitler amonyakla şiddetli tepkime verir; ısı ve tahriş edici beyaz duman oluşur."),
    ({GUCLU_ASIT}, {YANICI}, DIKKAT, "Isı ve istenmeyen tepkimeler",
     "Derişik güçlü asitler alkol ve diğer organik çözücülerle ısı açığa çıkararak tepkimeye girebilir; "
     "sıçrama, zehirli buhar veya yanıcı ürünler oluşabilir."),
    ({AKTIF_METAL}, {GUCLU_ASIT}, DIKKAT, "Yanıcı hidrojen gazı",
     "Aktif metaller asitlerle tepkimeye girerek yanıcı hidrojen gazı açığa çıkarır."),
    ({AKTIF_METAL}, {GUCLU_BAZ}, DIKKAT, "Yanıcı hidrojen gazı",
     "Alüminyum ve çinko güçlü bazlarla (ör. lavabo açıcı) tepkimeye girerek yanıcı hidrojen gazı "
     "açığa çıkarır."),
    ({AKTIF_METAL}, {OKSITLEYICI}, DIKKAT, "Yangın riski",
     "Toz haldeki metaller oksitleyicilerle birlikte kolayca tutuşabilir."),
    ({GUCLU_ASIT}, {SU}, DIKKAT, "Önce su, sonra asit!",
     "Derişik asit seyreltilirken çok ısı açığa çıkar. Daima asidi yavaşça suya ekleyin, "
     "asla suyu asidin üzerine dökmeyin."),
    ({GUCLU_BAZ}, {SU}, BILGI, "Isı açığa çıkar",
     "Katı kostik suda çözünürken çok ısınır; yavaşça ve karıştırarak ekleyin."),
    (HER_ASIT, {ZAYIF_BAZ}, BILGI, "Köpürme (CO₂ gazı)",
     "Asitler karbonatlarla tepkimeye girerek karbondioksit gazı oluşturur; köpürür. "
     "Kapalı kapta basınç birikebilir."),
]

GENEL_UYARI = (
    "Bu kontrol yaygın ve bilinen tepkimelere dayanır; her durumu kapsamaz. "
    "Kimyasalları birbirine karıştırmadan önce mutlaka ürün etiketini ve Güvenlik Bilgi Formunu (SDS) okuyun."
)

# GHS H kodlarından sınıf çıkarımı (listede olmayan kimyasallar için)
H_KODU_SINIFLARI = {
    "H270": OKSITLEYICI, "H271": OKSITLEYICI, "H272": OKSITLEYICI,
    "H220": YANICI, "H221": YANICI, "H222": YANICI, "H223": YANICI, "H224": YANICI,
    "H225": YANICI, "H226": YANICI, "H228": YANICI, "H250": YANICI,
    "H260": SU_REAKTIF, "H261": SU_REAKTIF,
}


# --------------------------------------------------------------------------------------
# Yardımcılar
# --------------------------------------------------------------------------------------
def normallestir(metin):
    """Türkçe karakterleri sadeleştirip küçük harfe çevirir: 'Çamaşır Suyu' -> 'camasir suyu'."""
    metin = metin.replace("I", "ı").replace("İ", "i").lower()
    for tr, en in zip("çğıöşüâî", "cgiosuai"):
        metin = metin.replace(tr, en)
    metin = re.sub(r"[^a-z0-9 ]+", " ", metin)
    return re.sub(r"\s+", " ", metin).strip()


# normalleştirilmiş isim -> kimyasal kaydı (uzun isimler önce denenir)
_ISIM_TABLOSU = sorted(
    ((normallestir(isim), kayit) for kayit in KIMYASALLAR for isim in kayit[2]),
    key=lambda x: -len(x[0]),
)


def tani(girdi, yerel_getir=None):
    """Kimyasalı tanır. {'girdi','ad','siniflar','kaynak'} veya tanınamazsa siniflar boş döner."""
    n = normallestir(girdi)
    if n:
        for isim, (ad, siniflar, _) in _ISIM_TABLOSU:
            if re.search(rf"(^| ){re.escape(isim)}( |$)", n):
                return {"girdi": girdi, "ad": ad, "siniflar": set(siniflar), "kaynak": "liste"}

    # Listede yoksa yerel kimyasal veritabanındaki GHS H kodlarına bak
    if yerel_getir:
        veri = yerel_getir(girdi)
        if veri:
            siniflar = {H_KODU_SINIFLARI[h["kod"]] for h in veri.get("h_kodlari", []) if h.get("kod") in H_KODU_SINIFLARI}
            return {"girdi": girdi, "ad": veri.get("isim") or girdi, "siniflar": siniflar or {NOTR},
                    "kaynak": "ghs" if siniflar else "ghs_yok"}

    return {"girdi": girdi, "ad": girdi, "siniflar": set(), "kaynak": None}


def kontrol(girdi1, girdi2, yerel_getir=None):
    k1, k2 = tani(girdi1, yerel_getir), tani(girdi2, yerel_getir)

    def kimyasal_ozeti(k):
        return {
            "girdi": k["girdi"],
            "ad": k["ad"],
            "tanindi": bool(k["siniflar"]),
            "siniflar": sorted(SINIF_ADLARI[s] for s in k["siniflar"] if s != NOTR),
        }

    sonuc = {"kimyasallar": [kimyasal_ozeti(k1), kimyasal_ozeti(k2)], "uyari": GENEL_UYARI}

    tanınmayan = [k["girdi"] for k in (k1, k2) if not k["siniflar"]]
    if tanınmayan:
        sonuc.update(
            seviye="bilinmiyor",
            baslik="Kimyasal tanınamadı",
            bulgular=[],
            mesaj=f"{', '.join(tanınmayan)} için kayıtlı bilgimiz yok. Farklı bir isim (ör. Türkçe veya "
                  f"İngilizce adı) deneyebilir ya da KimyaGPT'ye sorabilirsiniz.",
        )
        return sonuc

    bulgular = []
    for s1, s2, seviye, baslik, aciklama in KURALLAR:
        if (k1["siniflar"] & s1 and k2["siniflar"] & s2) or (k2["siniflar"] & s1 and k1["siniflar"] & s2):
            if not any(b["baslik"] == baslik for b in bulgular):
                bulgular.append({"seviye": seviye, "baslik": baslik, "aciklama": aciklama})
    bulgular.sort(key=lambda b: -b["seviye"])

    ad = {TEHLIKELI: "tehlikeli", DIKKAT: "dikkat", BILGI: "bilgi"}
    for b in bulgular:
        b["seviye"] = ad[b["seviye"]]

    if k1["ad"] == k2["ad"]:
        sonuc.update(seviye="bilgi", baslik="Aynı kimyasal", bulgular=bulgular,
                     mesaj="İki kutuya da aynı kimyasalı yazdınız.")
    elif bulgular:
        sonuc.update(
            seviye=bulgular[0]["seviye"],
            baslik={"tehlikeli": "TEHLİKELİ — Asla karıştırmayın!",
                    "dikkat": "Dikkat gerektirir",
                    "bilgi": "Dikkat edilecek noktalar var"}[bulgular[0]["seviye"]],
            bulgular=bulgular,
            mesaj="",
        )
    else:
        sonuc.update(
            seviye="bulunamadi",
            baslik="Bilinen tehlikeli bir tepkime bulunamadı",
            bulgular=[],
            mesaj="Kayıtlarımızda bu iki kimyasal arasında bilinen tehlikeli bir tepkime yok. "
                  "Bu, karışımın kesinlikle güvenli olduğu anlamına gelmez.",
        )
    return sonuc


def oneri_listesi():
    """Arayüzdeki öneri kutusu için her kimyasalın ilk (en bilinen) adı."""
    return [kayit[2][0] for kayit in KIMYASALLAR]
