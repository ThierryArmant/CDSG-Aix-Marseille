#!/usr/bin/env python3
"""
Veille web des classes défense (CDSG) — académie d'Aix-Marseille.

Pour une fiche (ou plusieurs), le script :
  1. cherche sur le web : classe défense, sorties, cérémonies, convention, unité marraine,
     articles de presse ; explore aussi le site de l'établissement s'il est renseigné ;
  2. lit les pages trouvées (et les liens donnés à la main) ;
  3. demande au modèle (Albert API ou autre service compatible OpenAI) d'en extraire
     chaque élément utile : sortie, cérémonie, convention, article, rapport, projet… ;
  4. range tout dans le dossier de la classe : classes/<identifiant>/veille.json
     (cumulatif : on ne perd rien d'une recherche à l'autre) ;
  5. met à jour data/recherche.js (résumé + « dernière sortie / convention / article »)
     que le site affiche et que l'assistant utilise pour répondre.

Bibliothèque standard uniquement (Python 3.9+).

Variables d'environnement :
  ALBERT_API_KEY   clé (obligatoire)
  API_BASE_URL     défaut https://albert.api.etalab.gouv.fr/v1 (Mistral : https://api.mistral.ai/v1)
  API_MODEL        facultatif

Exemples :
  python3 recherche/recherche_web.py --fiche college-jean-giono-orange
  python3 recherche/recherche_web.py --fiche college-jean-giono-orange --liens "https://…article1 https://…article2"
  python3 recherche/recherche_web.py --verifier
  python3 recherche/recherche_web.py --question "Quelle classe a fait la dernière sortie à la BA 115 ?"
"""
import argparse, base64, datetime, html, json, os, re, shutil, subprocess, sys, tempfile, time, unicodedata
import urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER_CLASSES = RACINE / "data" / "classes.js"
FICHIER_RESUME = RACINE / "data" / "recherche.js"
FICHIER_ACTUS = RACINE / "data" / "actualites.js"
FICHIER_A_LIRE = RACINE / "data" / "a_lire.json"
DOSSIER_CLASSES = RACINE / "classes"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

BASE = os.environ.get("API_BASE_URL", "https://albert.api.etalab.gouv.fr/v1").rstrip("/")
CLE = os.environ.get("ALBERT_API_KEY") or os.environ.get("API_KEY")
MODELE = os.environ.get("API_MODEL", "") or ("openweight-large" if "etalab.gouv.fr" in BASE else "")
# Un modèle par spécialité (même clé). Vide = modèle principal ci-dessus.
SPECIALITES = {
    "tri":        os.environ.get("MODELE_TRI")        or ("openweight-small" if "etalab.gouv.fr" in BASE else ""),  # la page parle-t-elle de la classe ?
    "extraction": os.environ.get("MODELE_EXTRACTION") or "",   # sorties, conventions, articles…
    "synthese":   os.environ.get("MODELE_SYNTHESE")   or "",   # observations de la fiche
    "question":   os.environ.get("MODELE_QUESTION")   or "",   # réponses aux questions
    "vision":     os.environ.get("MODELE_VISION")     or ("gemma-4-31b-it" if "etalab.gouv.fr" in BASE else ""),  # lecture des PDF scannés ou mal encodés
}
TYPES = ["distinction", "sortie", "ceremonie", "convention", "article", "rapport", "projet", "partenaire", "autre"]
# Concours et prix cherchés pour CHAQUE établissement (ajouter ici tout nouveau concours)
CONCOURS = ["prix de l'éducation citoyenne", "prix Armées zone Sud", "prix inter-armées", "concours national de la Résistance et de la Déportation",
            "concours Clemenceau", "Bulles de mémoire", "Petits artistes de la mémoire", "Féminisons l'aéronautique",
            "prix Trinôme", "prix Louis Quinio", "Union-IHEDN", "AR-IHEDN", "IHEDN", "label CDSG", "Souvenir français", "ANMONM", "médaille de la jeunesse"]
ANNEES = list(range(2018, datetime.date.today().year + 1))
PREFECTURES = {"13": "bouches-du-rhone.gouv.fr", "84": "vaucluse.gouv.fr", "04": "alpes-de-haute-provence.gouv.fr", "05": "hautes-alpes.gouv.fr"}
# Concours et prix où les classes défense sont souvent récompensées (recherche « palmarès »)
PALMARES = ["prix Armées zone Sud lauréats", "prix Armées zone Sud collège classe défense", "prix inter-armées classe défense lauréat",
            "concours Clemenceau lauréats collège", "concours national de la Résistance et de la Déportation lauréats Vaucluse",
            "concours national de la Résistance et de la Déportation lauréats Bouches-du-Rhône", "Bulles de mémoire ONACVG lauréats",
            "prix de l'éducation citoyenne ANMONM lauréats", "trophées classes défense lauréats", "prix trinôme académique Aix-Marseille",
            "classe défense récompensée préfet", "site:vaucluse.gouv.fr classe défense collège",
            "site:bouches-du-rhone.gouv.fr classe défense collège", "site:alpes-de-haute-provence.gouv.fr classe défense",
            "site:hautes-alpes.gouv.fr classe défense", "base aérienne 115 Orange collège classe défense",
            "base aérienne 125 Istres classe défense collège", "marins-pompiers Marseille classe défense collège",
            "1er régiment étranger de cavalerie classe défense collège", "4e régiment de chasseurs Gap classe défense",
            "2e régiment étranger de génie classe défense collège", "site:facebook.com classe défense collège Vaucluse",
            "site:facebook.com classe défense Bouches-du-Rhône collège prix", "classe défense prix Provence collège", "labellisation classe défense et sécurité globales Aix-Marseille",
            "prix Louis Quinio lauréats", "site:union-ihedn.org Presentation Prix Louis QUINIO pdf", "prix Louis Quinio collège classe défense", "site:union-ihedn.org prix Louis Quinio",
            "AR-IHEDN Provence prix classe défense", "prix Louis Quinio Aix-Marseille trinôme"]
MOTS_DEFENSE = re.compile(r"d[ée]fense|cdsg|prix|laur[ée]at|concours|r[ée]compens|distinction|m[ée]daille|troph[ée]e|militaire|arm[ée]e|base a[ée]rienne|r[ée]giment|gendarmerie|pompier|marine|"
                          r"l[ée]gion|c[ée]r[ée]monie|comm[ée]mor|m[ée]moire|11 novembre|8 mai|rallye|trin[ôo]me|convention", re.I)


MOTS_DISTINCTION = re.compile(r"prix|laur[ée]at|concours|r[ée]compens|distinction|m[ée]daille|troph[ée]e|palmar[eè]s|1er|premier prix|class[ée]|drapeau|fanion|label", re.I)

# ───────────────────────── fichiers ─────────────────────────
def slug(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def lire_classes():
    src = FICHIER_CLASSES.read_text(encoding="utf-8")
    debut = src.index("window.CDSG = [") + len("window.CDSG = ")
    bloc = src[debut:src.rindex("]") + 1]
    bloc = re.sub(r"(?m)^\s*//[^\n]*", "", bloc)
    try:
        classes = json.loads(bloc)
    except json.JSONDecodeError:
        bloc = re.sub(r'([{,]\s*)([a-zA-Z_]+)\s*:', r'\1"\2":', bloc)
        bloc = re.sub(r",\s*([}\]])", r"\1", bloc)
        classes = json.loads(bloc)
    for c in classes:
        c["id"] = c.get("id") or slug(c["etab"] + " " + c["ville"])
    return classes


def lire_resumes():
    if not FICHIER_RESUME.exists(): return {}
    m = re.search(r"window\.CDSG_WEB\s*=\s*(\{.*\});", FICHIER_RESUME.read_text(encoding="utf-8"), re.S)
    return json.loads(m.group(1)) if m else {}


def ecrire_resumes(r):
    FICHIER_RESUME.write_text(
        "// Résumés de la veille web — généré par recherche/recherche_web.py (détail : classes/<fiche>/veille.json)\n"
        "window.CDSG_WEB = " + json.dumps(r, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")


def lire_veille(cid):
    f = DOSSIER_CLASSES / cid / "veille.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"fiche": cid, "elements": [], "recherches": []}


def ecrire_veille(cid, v):
    d = DOSSIER_CLASSES / cid
    d.mkdir(parents=True, exist_ok=True)
    (d / "veille.json").write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")


# ───────────────────────── web ─────────────────────────
def adresse_sure(url):
    """Encode les accents et espaces de l'adresse (sinon la lecture échoue)."""
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme, p.netloc.encode("idna").decode() if p.netloc else p.netloc,
        urllib.parse.quote(p.path, safe="/%:@!$&'()*+,;=-._~"),
        urllib.parse.quote(p.query, safe="=&%:/?+,;@-._~"), ""))


def http_get(url, timeout=20):
    url = adresse_sure(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        brut = r.read(25_000_000 if url.lower().split("?")[0].endswith(".pdf") else 800_000)
        DERNIER["type"] = r.headers.get_content_type(); DERNIER["octets"] = brut
        return brut.decode(r.headers.get_content_charset() or "utf-8", errors="replace"), r.geturl()


DERNIER = {"type": "", "octets": b""}


def texte_lisible(t):
    """Vrai si le texte ressemble à du français (et non à une police mal encodée)."""
    mots = re.findall(r"[a-zàâçéèêëîïôûùüÿœ]+", t.lower())
    if len(mots) < 30: return False
    courants = {"le", "la", "les", "de", "des", "du", "et", "en", "un", "une", "pour", "au", "aux", "dans", "par", "sur", "est", "qui"}
    return sum(1 for m in mots if m in courants) / len(mots) > 0.06


def lire_pdf(octets, maxi_pages=10):
    """Texte d'un PDF : extraction directe, sinon lecture des pages en images par le modèle de vision."""
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "doc.pdf"); open(f, "wb").write(octets)
        texte = ""
        if shutil.which("pdftotext"):
            subprocess.run(["pdftotext", "-l", str(maxi_pages * 2), "-layout", f, f + ".txt"], capture_output=True, timeout=60)
            if os.path.exists(f + ".txt"): texte = open(f + ".txt", encoding="utf-8", errors="replace").read()
        if texte_lisible(texte): return texte
        if not (shutil.which("pdftoppm") and CLE and SPECIALITES.get("vision")): return texte
        subprocess.run(["pdftoppm", "-r", "90", "-png", "-l", str(maxi_pages), f, os.path.join(d, "p")], capture_output=True, timeout=180)
        morceaux = []
        for img in sorted(x for x in os.listdir(d) if x.startswith("p") and x.endswith(".png")):
            b64 = base64.b64encode(open(os.path.join(d, img), "rb").read()).decode()
            try:
                rep = api("/chat/completions", {"model": SPECIALITES["vision"], "temperature": 0, "max_tokens": 1500,
                    "messages": [{"role": "user", "content": [
                        {"type": "text", "text": "Recopie fidèlement tout le texte de cette page (titres, noms d'établissements, villes, rangs, prix, années). Texte brut uniquement."},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}}]}]})
                morceaux.append(rep["choices"][0]["message"]["content"])
            except Exception as e:
                print(f"     ! lecture image impossible ({e})"); break
        print(f"     PDF lu en images : {len(morceaux)} page(s)")
        return "\n".join(morceaux) or texte


class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.txt = []; self.liens = []; self.skip = 0; self.titre = ""; self._t = False; self._a = None
        self.meta = {}
    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag in ("script", "style", "noscript", "svg"): self.skip += 1
        if tag == "title": self._t = True
        if tag == "a" and a.get("href"): self._a = [a["href"], ""]
        if tag == "meta":
            k = (a.get("property") or a.get("name") or "").lower()
            if k in ("og:image", "twitter:image", "og:title", "og:site_name", "article:published_time",
                     "og:description", "date", "dc.date", "pubdate") and a.get("content") and k not in self.meta:
                self.meta[k] = a["content"].strip()
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip: self.skip -= 1
        if tag == "title": self._t = False
        if tag == "a" and self._a: self.liens.append(tuple(self._a)); self._a = None
    def handle_data(self, d):
        if self._t: self.titre += d.strip()
        if self._a is not None: self._a[1] += " " + d.strip()
        if not self.skip and d.strip(): self.txt.append(d.strip())


def lire_page(url, maxi=16000):
    if RESEAUX.search(url) and url in EXTRAITS:
        t, x = EXTRAITS[url]
        return {"url": url, "titre": t, "texte": f"{t}. {x}", "liens": [], "image": None, "date_pub": None,
                "site": urllib.parse.urlsplit(url).netloc.replace("www.", "") + " (extrait public)"}
    try:
        brut, final = http_get(url)
        if "pdf" in DERNIER["type"] or DERNIER["octets"][:5] == b"%PDF-":
            t = re.sub(r"[ \t]+", " ", lire_pdf(DERNIER["octets"]))
            return {"url": final, "titre": urllib.parse.unquote(final.rsplit("/", 1)[-1]), "texte": t[:maxi * 2], "liens": [],
                    "image": None, "date_pub": None, "site": urllib.parse.urlsplit(final).netloc.replace("www.", "") + " (PDF)"}
        p = Page(); p.feed(brut)
        texte = re.sub(r"\s+", " ", " ".join(p.txt))
        liens = [(urllib.parse.urljoin(final, h), t.strip()) for h, t in p.liens]
        m = p.meta
        image = m.get("og:image") or m.get("twitter:image")
        if image: image = urllib.parse.urljoin(final, image)
        if image and re.search(r"logo|favicon|default|placeholder", image, re.I): image = None
        date = (m.get("article:published_time") or m.get("date") or m.get("dc.date") or m.get("pubdate") or "")[:10] or None
        return {"url": final, "titre": (m.get("og:title") or p.titre)[:200], "texte": texte[:maxi], "liens": liens,
                "image": image, "date_pub": date, "site": m.get("og:site_name") or urllib.parse.urlsplit(final).netloc.replace("www.", "")}
    except Exception:
        return None


STATS = {"requetes": 0, "vides": 0}
EXTRAITS = {}   # url -> (titre, extrait) tels qu'affichés par le moteur de recherche
RESEAUX = re.compile(r"facebook\.com|instagram\.com|linkedin\.com|(^|//)(www\.)?x\.com|twitter\.com|tiktok\.com|youtube\.com", re.I)


def recherche_web(requete, n=5):
    """DuckDuckGo (HTML puis version lite), sans clé. Garde aussi titre et extrait de chaque résultat."""
    trouves = []
    for base in ("https://html.duckduckgo.com/html/?", "https://lite.duckduckgo.com/lite/?"):
        try:
            page, _ = http_get(base + urllib.parse.urlencode({"q": requete, "kl": "fr-fr"}))
        except Exception:
            continue
        # titre + extrait de chaque résultat (version HTML)
        for bloc in re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>', page, re.S):
            u = html.unescape(bloc[0])
            if "uddg=" in u:
                u = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlparse(u).query).get("uddg", [u])[0])
            nettoie = lambda x: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", x))).strip()
            EXTRAITS[u] = (nettoie(bloc[1]), nettoie(bloc[2]))
        for l in re.findall(r'href="([^"]+)"', page):
            l = html.unescape(l)
            if "uddg=" in l:
                l = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlparse(l).query).get("uddg", [l])[0])
            if l.startswith("http") and "duckduckgo" not in l and l not in trouves:
                trouves.append(l)
        if trouves: break
    if not trouves:   # moteur de secours
        try:
            page, _ = http_get("https://www.bing.com/search?" + urllib.parse.urlencode({"q": requete, "setlang": "fr", "cc": "FR"}))
            for u, t, x in re.findall(r'<li class="b_algo".*?<h2[^>]*><a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>.*?(?:<p[^>]*>(.*?)</p>|</li>)', page, re.S):
                u = html.unescape(u)
                if "bing.com" in u or u in trouves: continue
                nettoie = lambda y: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", y or ""))).strip()
                EXTRAITS[u] = (nettoie(t), nettoie(x)); trouves.append(u)
        except Exception:
            pass
    STATS["requetes"] += 1; STATS["vides"] += 0 if trouves else 1
    return trouves[:n]


HOTES_ETAB = ("site.ac-aix-marseille.fr", "web.ac-aix-marseille.fr", "pedagogie.ac-aix-marseille.fr")


def racine_site(u):
    """https://www.site.ac-aix-marseille.fr/clg-giono-orange/spip/x.html -> …/clg-giono-orange/"""
    p = urllib.parse.urlsplit(u)
    if not any(p.netloc.endswith(h) for h in HOTES_ETAB): return None
    seg = [x for x in p.path.split("/") if x]
    return f"{p.scheme}://{p.netloc}/{seg[0]}/" if seg else None


def explorer_site(site, maxi=30):
    """Fouille le site de l'établissement : page d'accueil, rubriques liées à la défense,
    moteur de recherche interne (sites SPIP de l'académie), puis les articles trouvés (2 niveaux)."""
    if not site: return []
    if not site.startswith("http"): site = "https://" + site
    site = site if site.endswith("/") else site + "/"
    hote = urllib.parse.urlsplit(site).netloc
    chemin = urllib.parse.urlsplit(site).path
    def interne(u):
        pu = urllib.parse.urlsplit(u)
        return pu.netloc == hote and pu.path.startswith(chemin) and not re.search(
            r"\.(jpg|jpeg|png|gif|zip|doc|docx|mp4)$|page=recherche|page=backend|lang=|/ecrire/|#", u, re.I)
    def pertinent(u, t): return bool(MOTS_DEFENSE.search(u + " " + t) or MOTS_DISTINCTION.search(u + " " + t))
    cand, rubriques = [], []
    def ajouter(u):
        if u not in cand: cand.append(u)
    for base in (site, site + "spip/"):
        acc = lire_page(base)
        if not acc: continue
        ajouter(acc["url"])  # la page d'accueil annonce souvent les prix
        for u, t in acc["liens"]:
            if interne(u) and pertinent(u, t):
                ajouter(u)
                if re.search(r"/-[^/]+-\.html$|rubrique", u): rubriques.append(u)   # rubriques SPIP : -CDSG-.html
        for mot in ("classe défense", "CDSG", "défense", "prix", "concours", "lauréat", "éducation citoyenne",
                    "cérémonie", "mémoire", "drapeau", "base aérienne", "sortie"):
            r = lire_page(base + "spip.php?" + urllib.parse.urlencode({"page": "recherche", "recherche": mot}))
            if r:
                for u, t in r["liens"]:
                    if interne(u) and re.search(r"\.html$|article", u) and u != r["url"]: ajouter(u)
        break
    # 2e niveau : contenu des rubriques (avec pagination SPIP debut_articles=)
    for rub in rubriques[:6]:
        for page_n in range(0, 4):
            u = rub if page_n == 0 else rub + ("&" if "?" in rub else "?") + f"debut_articles={page_n * 10}"
            r = lire_page(u)
            if not r: break
            avant = len(cand)
            for l, t in r["liens"]:
                if interne(l) and re.search(r"\.html$|article", l): ajouter(l)
            if len(cand) == avant: break
    print(f"   site de l'établissement {site} : {len(cand)} page(s) candidates")
    return cand[:maxi]


# ───────────────────────── modèle ─────────────────────────
def api(chemin, corps=None):
    req = urllib.request.Request(BASE + chemin, method="POST" if corps else "GET",
        data=json.dumps(corps).encode() if corps else None,
        headers={"Authorization": "Bearer " + CLE, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def choisir_modele():
    global MODELE
    if MODELE: return MODELE
    ids = [m["id"] for m in api("/models").get("data", [])
           if not m.get("type") or re.search(r"text-generation|chat", m.get("type", ""))]
    for motif in (r"openweight-large", r"gpt-oss-120b", r"mistral-large", r"mistral-medium", r"large"):
        for i in ids:
            if re.search(motif, i, re.I): MODELE = i; return MODELE
    MODELE = ids[0]; return MODELE


def demander(systeme, utilisateur, jsonmode=True, max_tokens=2500, specialite=""):
    corps = {"model": SPECIALITES.get(specialite) or choisir_modele(), "temperature": 0.1, "max_tokens": max_tokens,
             "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": utilisateur}]}
    for essai in range(3):
        try:
            rep = api("/chat/completions", corps)["choices"][0]["message"]["content"]
            if not jsonmode: return rep
            m = re.search(r"\{.*\}", rep, re.S)
            return json.loads(m.group(0)) if m else None
        except Exception as e:
            print(f"   ! modèle : {e} — nouvel essai", file=sys.stderr); time.sleep(5 * (essai + 1))
    return None


SYSTEME_EXTRACTION = """Tu fais la veille d'une classe défense et sécurité globales (CDSG) de l'académie d'Aix-Marseille.
On te donne la fiche de la classe et le texte d'UNE page web.
Relève TOUT ce qui concerne la classe défense (ou atelier défense) de CET établissement (pas un homonyme, pas un autre collège),
y compris une simple brève ou un titre d'actualité, et toutes les années citées (pas seulement la plus récente).
Un prix obtenu par l'établissement pour un projet citoyen ou de mémoire mené par la classe défense compte comme distinction :
DISTINCTIONS en priorité : prix, concours (prix Armées zone Sud, prix inter-armées, concours Clemenceau, CNRD, Bulles de mémoire,
prix ANMONM…), récompenses, lauréats, mentions, labels, médailles, décorations, remises de fanion ou de diplôme, félicitations du préfet ;
puis sorties, visites de base ou de régiment, cérémonies (11 novembre, 8 mai…), signature ou renouvellement de convention,
unité marraine, rallye citoyen, concours, projets, articles de presse, rapports ou bilans, noms des professeurs référents.
N'invente rien : uniquement ce qui est écrit dans la page.
Réponds en JSON :
{"concerne": true|false,
 "elements": [
   {"type": "distinction|sortie|ceremonie|convention|article|rapport|projet|partenaire|autre",
    "date": "AAAA-MM-JJ, AAAA-MM ou AAAA (date de l'événement ; sinon de la publication) ou null",
    "titre": "titre court en français",
    "extrait": "courte citation exacte de la page (25 mots maximum)",
    "resume": "1 à 2 phrases en français avec les faits utiles (qui, quoi, où, avec quelle unité)"}],
 "referents": "noms de professeurs cités ou null",
 "unite": "unité marraine citée ou null"}"""


def analyser_page(c, page):
    fiche = {k: c.get(k) for k in ("etab", "ville", "dep", "ce", "ref", "unite", "conv")}
    r = demander(SYSTEME_EXTRACTION,
                 "Fiche :\n" + json.dumps(fiche, ensure_ascii=False) +
                 f"\n\nPage : {page['url']}\nTitre : {page['titre']}\n\n{page['texte']}", specialite="extraction")
    if not r or not r.get("concerne"): return None
    aujourd_hui = datetime.date.today().isoformat()
    for e in r.get("elements", []):
        if e.get("date") and str(e["date"])[:10] > aujourd_hui[:len(str(e["date"])[:10])]:
            e["date"] = None   # date dans le futur : erreur de lecture
        e["source"] = page["url"]; e["page"] = page["titre"]; e["site"] = page.get("site")
        if page.get("image"): e["image"] = page["image"]
        if not e.get("date") and page.get("date_pub"): e["date"] = page["date_pub"]
        if e.get("type") not in TYPES: e["type"] = "autre"
        e["extrait"] = " ".join((e.get("extrait") or "").split()[:25])
    return r


def trier(c, page):
    """Petit modèle : la page concerne-t-elle la classe défense de cet établissement ?"""
    r = demander("Réponds uniquement par OUI ou NON.",
                 f"La page suivante mentionne-t-elle, même brièvement, la classe défense (CDSG) ou l'atelier défense, un prix, un concours, "
                 f"une distinction, une sortie, une cérémonie ou un partenariat militaire des élèves de « {c['etab']} » à {c['ville']} ?\n\nTitre : {page['titre']}\n{page['texte'][:2500]}",
                 jsonmode=False, max_tokens=5, specialite="tri")
    return r is None or "OUI" in r.upper()   # en cas de panne du tri, on laisse passer


def cle_element(e):
    """Un même événement cité sur plusieurs pages = un seul élément.
    Pour les distinctions : même concours (mots significatifs du titre), quelle que soit la page."""
    t = slug(e.get("titre", ""))
    if e.get("type") == "distinction":
        vides = {"prix", "de", "du", "la", "le", "des", "et", "edition", "college", "jean", "giono", "orange", "avec", "remise", "d", "l", "les", "au", "a"}
        mots = sorted(m for m in t.split("-") if len(m) > 2 and m not in vides and not m.isdigit())
        return ("distinction", "-".join(mots[:4]))
    return (e.get("type"), t[:50])


def fusionner(existant, e):
    """Complète un élément déjà connu (date manquante, autres sources)."""
    if not existant.get("date") and e.get("date"): existant["date"] = e["date"]
    if not existant.get("image") and e.get("image"): existant["image"] = e["image"]
    if e.get("source") and e["source"] != existant.get("source"):
        autres = existant.setdefault("autres_sources", [])
        if e["source"] not in autres: autres.append(e["source"])


def date_tri(e):
    d = (e.get("date") or "0000")[:10]
    return d + "-00-00"[len(d) - 4:] if len(d) < 10 else d


def infos_resume(v):
    """Partie du résumé calculée sans modèle (dernières activités, distinctions…)."""
    els = sorted(v["elements"], key=date_tri, reverse=True)
    derniers = {}
    for t in ("distinction", "sortie", "ceremonie", "convention", "article", "rapport", "projet"):
        e = next((x for x in els if x["type"] == t), None)
        if e: derniers[t] = {k: e.get(k) for k in ("date", "titre", "resume", "source")}
    return {"nb": len(els), "derniere_activite": els[0].get("date") if els else None, "derniers": derniers,
            "distinctions": [{"date": e.get("date"), "titre": e.get("resume") if e.get("manuel") else e.get("titre"),
                              "resume": e.get("resume"), "source": e.get("source")} for e in els if e["type"] == "distinction"],
            "sources": list(dict.fromkeys(e["source"] for e in els))[:8]}


def fusionner_dossiers(dossier_run):
    """Fusionne les résultats d'une recherche (copiés dans dossier_run) avec la version actuelle du dépôt,
    sans perdre les modifications faites entre-temps (retraits, ajouts manuels, autres recherches)."""
    run = Path(dossier_run)
    res_run = {}
    f = run / "recherche.js"
    if f.exists():
        m = re.search(r"window\.CDSG_WEB\s*=\s*(\{.*\});", f.read_text(encoding="utf-8"), re.S)
        res_run = json.loads(m.group(1)) if m else {}
    resumes = lire_resumes()
    for vf in (run / "classes").glob("*/veille.json"):
        cid = vf.parent.name
        a = json.loads(vf.read_text(encoding="utf-8"))
        b = lire_veille(cid)
        exclus = {(x.get("source"), x.get("cle")) for x in b.get("exclus", []) + a.get("exclus", [])}
        ex_src = {x.get("source") for x in b.get("exclus", []) if not x.get("cle")}
        tous = {}
        for e in b.get("elements", []) + a.get("elements", []):
            if (e.get("source"), slug(e.get("titre", ""))[:50]) in exclus or e.get("source") in ex_src: continue
            k = cle_element(e)
            if k in tous: fusionner(tous[k], e)
            else: tous[k] = e
        # un élément retiré sur le site depuis le lancement : il n'est plus dans b mais est dans b.exclus -> déjà filtré
        b["elements"] = sorted(tous.values(), key=date_tri, reverse=True)
        b["exclus"] = list({(x.get("source"), x.get("cle")): x for x in b.get("exclus", []) + a.get("exclus", [])}.values())
        b["pages_lues"] = sorted(set(b.get("pages_lues", [])) | set(a.get("pages_lues", [])))
        vues = {json.dumps(r, sort_keys=True) for r in b.get("recherches", [])}
        b["recherches"] = b.get("recherches", []) + [r for r in a.get("recherches", []) if json.dumps(r, sort_keys=True) not in vues]
        for k in ("fiche", "etablissement", "referents_cites", "unite_citee"):
            if a.get(k): b[k] = a[k]
        ecrire_veille(cid, b)
        r = dict(res_run.get(cid) or resumes.get(cid) or {})
        r.update(infos_resume(b))
        resumes[cid] = r
    fb = run / "a_lire.json"
    if fb.exists():
        traitee = json.loads(fb.read_text(encoding="utf-8"))
        actuelle = json.loads(FICHIER_A_LIRE.read_text(encoding="utf-8")) if FICHIER_A_LIRE.exists() else {}
        faits = {x["url"] for x in traitee.get("traites", [])}
        actuelle["a_lire"] = [x for x in actuelle.get("a_lire", []) if x["url"] not in faits]
        vus = set(); actuelle["traites"] = [x for x in traitee.get("traites", []) + actuelle.get("traites", []) if not (x["url"], x.get("traite_le")) in vus and not vus.add((x["url"], x.get("traite_le")))][:200]
        FICHIER_A_LIRE.write_text(json.dumps(actuelle, ensure_ascii=False, indent=1), encoding="utf-8")
    ecrire_resumes(resumes)
    ecrire_actualites(lire_classes())
    print(f"Fusion : {len(list((run / 'classes').glob('*/veille.json')))} dossier(s) fusionné(s)")


def faire_resume(c, v):
    els = sorted(v["elements"], key=date_tri, reverse=True)
    derniers = {}
    for t in ("distinction", "sortie", "ceremonie", "convention", "article", "rapport", "projet"):
        e = next((x for x in els if x["type"] == t), None)
        if e: derniers[t] = {k: e.get(k) for k in ("date", "titre", "resume", "source")}
    synthese = None
    if els:
        lignes = "\n".join(f"- [{e['type']}] {e.get('date') or '?'} — {e.get('titre')} : {e.get('resume')}" for e in els[:40])
        synthese = demander("Tu rédiges en français, en 3 phrases factuelles maximum, l'état de la classe défense "
                            "à partir des éléments de veille : activité la plus récente, distinctions et prix obtenus, partenaires, faits marquants. "
                            "N'invente rien. Réponds en texte simple.",
                            f"Classe : {c['etab']} ({c['ville']})\nÉléments :\n{lignes}", jsonmode=False, max_tokens=300, specialite="synthese")
    return {"date": datetime.date.today().strftime("%d/%m/%Y"),
            "resume": (synthese or "").strip(),
            "nb": len(els),
            "derniere_activite": els[0].get("date") if els else None,
            "derniers": derniers,
            "distinctions": [{"date": e.get("date"), "titre": e.get("resume") if e.get("manuel") else e.get("titre"), "resume": e.get("resume"), "source": e.get("source")} for e in els if e["type"] == "distinction"],
            "sources": list(dict.fromkeys(e["source"] for e in els))[:8]}


# ───────────────────────── traitement d'une fiche ─────────────────────────
def traiter_fiche(c, liens_manuels=(), profondeur=25):
    nom, ville = c["etab"], c["ville"]
    unite = c.get("unite") if c.get("unite") not in (None, "", "—") else ""
    # nom court tel qu'employé par la presse : « collège Giono », « lycée Mistral »
    genre = "lycée" if re.search(r"lyc[ée]e|LP|LPP|LPO", nom) else "collège"
    mots = [m for m in re.sub(r"\(.*?\)", "", nom).split() if m[:1].isupper() and m.lower() not in ("collège", "lycée", "college", "lycee", "lpp", "lp", "lpo", "des", "de", "du", "la", "le", "les")]
    court = f"{genre} {mots[-1]}" if mots else nom
    presse = ["laprovence.com", "ledauphine.com", "lamarseillaise.fr", "france3-regions.francetvinfo.fr",
              "francebleu.fr", "actu.fr", "varmatin.com", "lepoint.fr", "20minutes.fr"]
    requetes = [
        f'"{nom}" {ville} classe défense',
        f'"{court}" {ville} classe défense',
        f'"{court}" {ville} élèves prix OR concours OR lauréat',
        f'"{court}" {ville} cérémonie élèves commémoration',
        f'"{court}" {ville} {unite} élèves' if unite else f'"{court}" {ville} militaires élèves',
        f'site:{ville.split()[0].lower().replace("é","e").replace("è","e")}.fr "{court}"',
        f'{nom} {ville} CDSG',
        f'{nom} {ville} sortie {unite or "base militaire"}',
        f'{nom} {ville} cérémonie 11 novembre élèves',
        f'{nom} {ville} convention classe défense {unite}',
        f'{nom} {ville} classe défense La Provence OR Vaucluse Matin OR Dauphiné',
        f'collège OR lycée {ville} "classe défense" élèves',
        *[f'site:{d} "{court}" {ville}' for d in presse[:5]],
        *[f'site:{d} {court} {ville} défense' for d in presse[5:]],
        f'site:defense.gouv.fr {nom} {ville}',
        f'{nom} {ville} prix OR lauréat OR concours OR récompense classe défense',
        f'"prix Armées zone Sud" OR "prix inter-armées" OR "concours Clemenceau" {nom} {ville}',
        f'site:{PREFECTURES.get(c.get("dep"), "gouv.fr")} {nom} {ville}',
        f'site:onac-vg.fr {nom} {ville}',
        # concours un par un
        *[f'"{court}" {ville} "{k}"' for k in CONCOURS],
        # balayage des années depuis 2018 (prix, lauréats)
        *[f'"{court}" {ville} prix OR lauréat OR concours {" OR ".join(map(str, ANNEES[i:i+3]))}' for i in range(0, len(ANNEES), 3)],
        # radios locales
        f'site:frequencemistral.com OR site:francebleu.fr "{court}" {ville}',
        # actualités des bases et unités marraines
        f'site:defense.gouv.fr "{court}" {ville}',
        f'{unite} actualités élèves "{court}"' if unite else f'base militaire élèves "{court}" {ville}',
        f'site:gendarmerie.interieur.gouv.fr "{court}" {ville}',
        f'site:{PREFECTURES.get(c.get("dep"), "gouv.fr")} "{court}"',
        # réseaux sociaux (extraits publics)
        f'site:facebook.com "{court}" {ville} défense OR militaires OR cérémonie OR prix',
        f'site:facebook.com {unite} "{court}"' if unite else f'site:facebook.com "{court}" {ville} classe défense',
        f'site:instagram.com "{court}" {ville} défense',
        f'site:linkedin.com "{court}" {ville} classe défense',
        f'site:x.com OR site:twitter.com "{court}" {ville} défense',
        f'site:pedagogie.ac-aix-marseille.fr {nom} {ville} défense',
        f'site:pedagogie.ac-aix-marseille.fr classe défense {ville}',
        f'{nom} {ville} "prix" "éducation citoyenne"',
        f'{nom} {ville} lauréat concours mémoire',
        f'site:ac-aix-marseille.fr {nom} {ville} classe défense',
        f'{ville} {unite} élèves classe défense' if unite else f'{ville} classe défense élèves {nom}',
    ]
    urls_web = []
    for q in requetes:
        for u in recherche_web(q.strip()):
            if u not in urls_web: urls_web.append(u)
        time.sleep(1.0 + (hash(q) % 10) / 10)
    # site de l'établissement : celui de la fiche, sinon celui repéré dans les résultats
    sites = [c.get("site")] if c.get("site") else []
    for u in urls_web:
        r = racine_site(u)
        if r and r not in sites and len(sites) < 2: sites.append(r)
    urls_site = []
    for st in sites:
        urls_site += [u for u in explorer_site(st) if u not in urls_site]
    def score(u):
        t, x = EXTRAITS.get(u, ("", ""))
        return 0 if MOTS_DISTINCTION.search(u + " " + t + " " + x) else 1
    urls_web.sort(key=score)
    urls = list(liens_manuels) + [u for u in urls_site + urls_web if u not in liens_manuels]
    v = lire_veille(c["id"])
    # dédoublonne aussi ce qui a été trouvé lors des recherches précédentes
    uniques = {}
    for e in v["elements"]:
        k = cle_element(e)
        if k in uniques: fusionner(uniques[k], e)
        else: uniques[k] = e
    v["elements"] = list(uniques.values())
    deja = {cle_element(e): e for e in v["elements"]}
    # articles retirés à la main depuis le site : ne jamais les remettre
    exclus_src = {x.get("source") for x in v.get("exclus", [])}
    exclus_cle = {(x.get("type"), x.get("cle")) for x in v.get("exclus", [])}
    vues = set(v.get("pages_lues", []))
    exclus_pages = {x.get("source") for x in v.get("exclus", [])}
    urls = [u for u in urls if u in liens_manuels or u not in exclus_pages]
    a_lire = [u for u in urls if u in liens_manuels or u in urls_site or u not in vues][: profondeur + len(liens_manuels) + len(urls_site)]
    print(f"   moteurs : {STATS['requetes']} requêtes, {STATS['vides']} sans résultat")
    print(f"   {len(urls)} pages trouvées ({len(urls_site)} sur le site de l'établissement), {len(a_lire)} à lire")
    nouveaux = 0
    for u in a_lire:
        page = lire_page(u)
        vues.add(u)
        if not page or len(page["texte"]) < (40 if RESEAUX.search(u) else 200):
            print(f"     · illisible      {u[:100]}"); continue
        t = slug(page["texte"])
        if u not in liens_manuels and not RESEAUX.search(u) and not (MOTS_DEFENSE.search(page["texte"]) and (u in urls_site or slug(ville) in t)):
            print(f"     · hors sujet     {u[:100]}"); continue
        if u not in liens_manuels and u not in urls_site and not MOTS_DISTINCTION.search(page["texte"]) and not trier(c, page):
            print(f"     · écartée (tri)  {u[:100]}"); continue
        r = analyser_page(c, page)
        if not r:
            print(f"     · rien d'utile   {u[:100]}"); continue
        print(f"     ✓ {len(r.get('elements', []))} élément(s)  {u[:100]}")
        for e in r.get("elements", []):
            e["trouve_le"] = datetime.date.today().isoformat()
            k = cle_element(e)
            if e.get("source") in exclus_src or k in exclus_cle:
                continue
            if k in deja:
                fusionner(deja[k], e)
            else:
                v["elements"].append(e); deja[k] = e; nouveaux += 1
        if r.get("referents"): v["referents_cites"] = r["referents"]
        if r.get("unite"): v["unite_citee"] = r["unite"]
    v["elements"].sort(key=date_tri, reverse=True)
    v["pages_lues"] = sorted(vues)
    v["recherches"].append({"date": datetime.date.today().isoformat(), "pages": len(a_lire), "nouveaux": nouveaux})
    v["fiche"] = c["id"]; v["etablissement"] = f"{nom} ({ville})"
    ecrire_veille(c["id"], v)
    print(f"   + {nouveaux} élément(s) nouveau(x), {len(v['elements'])} au total")
    return v


def question_libre(question, classes, resumes):
    lignes = []
    for c in classes:
        w = resumes.get(c["id"], {})
        der = "; ".join(f"dernier(e) {t}: {d.get('date')} {d.get('titre')}" for t, d in w.get("derniers", {}).items())
        lignes.append(f'[{c["id"]}] {c["etab"]} | {c["ville"]} | {c["dep"]} | {c["statut"]} | CE {c.get("ce")} | réf. {c.get("ref")} '
                      f'| unité {c.get("unite")} | conv. {c.get("conv")} | {c.get("note","")} | veille: {w.get("resume","")} {der}')
    print(demander("Tu réponds à un inspecteur sur le dossier des CDSG de l'académie d'Aix-Marseille, uniquement à partir des fiches. "
                   "Réponds en français, brièvement. Termine par une ligne 'FICHES: id1, id2'.",
                   "Fiches :\n" + "\n".join(lignes) + "\n\nQuestion : " + question, jsonmode=False, specialite="question") or "Pas de réponse.")


def fiches_citees(classes, page):
    """Fiches dont l'établissement (nom distinctif + ville) apparaît dans la page."""
    t = slug(page["titre"] + " " + page["texte"])
    out = []
    for c in classes:
        mots = [m for m in slug(c["etab"]).split("-") if len(m) > 3 and m not in ("college", "lycee", "prive", "professionnel", "metiers", "jean", "saint")]
        if not mots or slug(c["ville"]).split("-")[0] not in t: continue
        if all(m in t for m in mots[-1:]): out.append(c)
    return out


def ranger_page(c, page, resumes):
    """Analyse une page pour une fiche et range les éléments dans son dossier. Renvoie le nombre de nouveautés."""
    r = analyser_page(c, page)
    if not r: return 0
    v = lire_veille(c["id"])
    if page["url"] in {x.get("source") for x in v.get("exclus", [])}: return 0
    connus = {cle_element(e): e for e in v["elements"]}
    n = 0
    for e in r.get("elements", []):
        k = cle_element(e)
        if k in connus: fusionner(connus[k], e)
        else: e["trouve_le"] = datetime.date.today().isoformat(); v["elements"].append(e); connus[k] = e; n += 1
    v["elements"].sort(key=date_tri, reverse=True)
    v["pages_lues"] = sorted(set(v.get("pages_lues", [])) | {page["url"]})
    ecrire_veille(c["id"], v)
    resumes[c["id"]] = faire_resume(c, v)
    return n


def traiter_a_lire(classes, resumes):
    """Boîte « Articles à lire » : liens déposés depuis le site, rangés dans la ou les bonnes fiches."""
    if not FICHIER_A_LIRE.exists(): return
    boite = json.loads(FICHIER_A_LIRE.read_text(encoding="utf-8") or "{}")
    a_faire = boite.get("a_lire", [])
    if not a_faire: return
    par_id = {c["id"]: c for c in classes}
    print(f"Boîte « Articles à lire » : {len(a_faire)} lien(s)")
    for item in a_faire:
        u = item["url"]
        page = lire_page(u, maxi=16000)
        if not page or len(page["texte"]) < 80:
            item["resultat"] = "illisible (page protégée ou vide)"
        else:
            cibles = [par_id[item["fiche"]]] if item.get("fiche") in par_id else fiches_citees(classes, page)
            if not cibles:
                item["resultat"] = "aucune classe du réseau reconnue dans la page"
            else:
                bilan = []
                for c in cibles:
                    n = ranger_page(c, page, resumes)
                    bilan.append(f"{c['etab']} ({c['ville']}) : {n} élément(s)")
                item["resultat"] = " ; ".join(bilan)
        item["traite_le"] = datetime.date.today().isoformat()
        print(f"   {u[:90]} → {item['resultat']}")
    boite["traites"] = (a_faire + boite.get("traites", []))[:200]
    boite["a_lire"] = []
    FICHIER_A_LIRE.write_text(json.dumps(boite, ensure_ascii=False, indent=1), encoding="utf-8")
    ecrire_resumes(resumes); ecrire_actualites(classes)


def palmares(classes, resumes, maxi_pages=25):
    """Cherche les palmarès des concours et prix, puis rattache chaque page aux classes qu'elle cite."""
    urls = []
    for q in PALMARES:
        for u in recherche_web(q, n=4):
            if u not in urls: urls.append(u)
        time.sleep(1.2)
    print(f"Palmarès : {len(urls)} pages à examiner")
    touchees = set()
    for u in urls[:maxi_pages]:
        page = lire_page(u, maxi=12000)
        if not page or len(page["texte"]) < 200: continue
        t = slug(page["texte"])
        for c in classes:
            mots = [m for m in slug(c["etab"]).split("-") if len(m) > 3 and m not in ("college", "lycee", "prive", "professionnel", "metiers")]
            if not mots or slug(c["ville"]).split("-")[0] not in t: continue
            if not all(m in t for m in mots[-2:]): continue
            r = analyser_page(c, page)
            if not r: continue
            v = lire_veille(c["id"])
            exclus = {x.get("source") for x in v.get("exclus", [])}
            if u in exclus: continue
            connus = {cle_element(e): e for e in v["elements"]}
            n = 0
            for e in r.get("elements", []):
                k = cle_element(e)
                if k in connus: fusionner(connus[k], e)
                else: e["trouve_le"] = datetime.date.today().isoformat(); v["elements"].append(e); connus[k] = e; n += 1
            if n:
                v["elements"].sort(key=date_tri, reverse=True); ecrire_veille(c["id"], v)
                resumes[c["id"]] = faire_resume(c, v); touchees.add(c["id"])
                print(f"   ✓ {c['etab']} ({c['ville']}) : {n} élément(s) — {u[:90]}")
    ecrire_resumes(resumes); ecrire_actualites(classes)
    print(f"Palmarès : {len(touchees)} classe(s) complétée(s)")


def ecrire_actualites(classes, n=24):
    """Les derniers éléments trouvés sur tout le réseau (page d'accueil)."""
    tous = []
    for c in classes:
        f = DOSSIER_CLASSES / c["id"] / "veille.json"
        if not f.exists(): continue
        for e in json.loads(f.read_text(encoding="utf-8")).get("elements", []):
            if e.get("type") == "autre" and not e.get("image"): continue
            tous.append(dict({k: e.get(k) for k in ("date", "type", "titre", "resume", "source", "image", "site")},
                             fiche=c["id"], etab=c["etab"], ville=c["ville"]))
    tous.sort(key=date_tri, reverse=True)
    FICHIER_ACTUS.write_text("// Dernières nouvelles du réseau — généré par recherche/recherche_web.py\n"
        "window.CDSG_ACTUS = " + json.dumps(tous[:n], ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")


def derniere_recherche(cid):
    f = DOSSIER_CLASSES / cid / "veille.json"
    if not f.exists(): return ""
    r = json.loads(f.read_text(encoding="utf-8")).get("recherches", [])
    return r[-1]["date"] if r else ""


def main():
    ap = argparse.ArgumentParser(description="Veille web des CDSG")
    ap.add_argument("--fiche", help="identifiant d'une fiche (ex. college-jean-giono-orange)")
    ap.add_argument("--liens", default="", help="liens d'articles à lire en priorité (séparés par des espaces)")
    ap.add_argument("--statut", choices=["active", "dormante", "projet"])
    ap.add_argument("--verifier", action="store_true")
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--profondeur", type=int, default=25, help="pages lues par fiche (hors site de l'établissement)")
    ap.add_argument("--question")
    ap.add_argument("--fusionner", help="fusionne les résultats copiés dans ce dossier avec le dépôt (usage interne)")
    ap.add_argument("--palmares", action="store_true", help="cherche les palmarès des concours et prix pour tout le réseau")
    ap.add_argument("--rotation", type=int, default=0,
                    help="veille automatique : traite les N fiches vérifiées il y a le plus longtemps")
    a = ap.parse_args()
    if a.fusionner:
        fusionner_dossiers(a.fusionner); return
    if not CLE:
        sys.exit("Clé absente : export ALBERT_API_KEY=\"…\" (ou secret GitHub ALBERT_API_KEY).")

    classes = lire_classes()
    resumes = lire_resumes()
    try:
        test = demander("Réponds OK.", "Test", jsonmode=False, max_tokens=5, specialite="tri")
        print("Connexion au modèle :", "OK" if test else "ÉCHEC")
    except Exception as e:
        print("Connexion au modèle : ÉCHEC", e)
    print(f"{len(classes)} fiches · {BASE} · modèle principal {choisir_modele()} · " + ", ".join(f"{k}={v or choisir_modele()}" for k, v in SPECIALITES.items()))
    if a.question:
        question_libre(a.question, classes, resumes); return
    traiter_a_lire(classes, resumes)
    if a.palmares:
        palmares(classes, resumes)
        if not (a.rotation or a.fiche or a.statut or a.verifier): return

    cible = [c for c in classes
             if (not a.fiche or c["id"] == a.fiche)
             and (not a.statut or c["statut"] == a.statut)
             and (not a.verifier or c.get("verifier"))]
    if a.fiche and not cible: sys.exit(f"Fiche inconnue : {a.fiche}")
    if a.rotation:
        cible = sorted(cible, key=lambda c: (derniere_recherche(c["id"]), {"active": 0, "dormante": 1, "projet": 2}[c["statut"]]))[:a.rotation]
    if a.max: cible = cible[:a.max]
    liens = [l for l in re.split(r"[\s,]+", a.liens) if l.startswith("http")]
    print(f"{len(cible)} fiche(s) à traiter")
    for i, c in enumerate(cible, 1):
        print(f"[{i}/{len(cible)}] {c['etab']} ({c['ville']})")
        v = traiter_fiche(c, liens if a.fiche else (), a.profondeur)
        resumes[c["id"]] = faire_resume(c, v)
        ecrire_resumes(resumes)
        ecrire_actualites(classes)
    print("Terminé.")


if __name__ == "__main__":
    main()
