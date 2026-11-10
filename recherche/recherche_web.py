#!/usr/bin/env python3
"""
Recherche web pour compléter les fiches CDSG.

Pour chaque fiche de data/classes.js :
  1. cherche sur le web (DuckDuckGo) « établissement + ville + classe défense » ;
  2. lit les premières pages trouvées ;
  3. demande au modèle (Albert API ou tout service compatible OpenAI) d'en extraire
     ce qui concerne la classe défense : activité récente, référent, unité marraine ;
  4. écrit le résultat dans data/recherche.js (affiché dans chaque fiche).

Aucune dépendance : uniquement la bibliothèque standard Python 3.9+.

Variables d'environnement :
  ALBERT_API_KEY   clé de l'API (obligatoire)
  API_BASE_URL     par défaut https://albert.api.etalab.gouv.fr/v1
                   (Mistral : https://api.mistral.ai/v1)
  API_MODEL        facultatif : sinon choisi automatiquement dans /models

Utilisation :
  export ALBERT_API_KEY="..."
  python3 recherche/recherche_web.py                 # toutes les fiches
  python3 recherche/recherche_web.py --statut dormante
  python3 recherche/recherche_web.py --verifier      # seulement les fiches « à vérifier »
  python3 recherche/recherche_web.py --fiche lycee-thiers-marseille
  python3 recherche/recherche_web.py --question "Quelles classes ont participé au rallye citoyen 2026 ?"
"""
import argparse, datetime, html, json, os, re, sys, time, unicodedata
import urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER_CLASSES = RACINE / "data" / "classes.js"
FICHIER_SORTIE = RACINE / "data" / "recherche.js"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

BASE = os.environ.get("API_BASE_URL", "https://albert.api.etalab.gouv.fr/v1").rstrip("/")
CLE = os.environ.get("ALBERT_API_KEY") or os.environ.get("API_KEY")
MODELE = os.environ.get("API_MODEL", "")


# ───────────────────────── outils ─────────────────────────
def slug(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def lire_classes():
    """Lit data/classes.js (tableau JS) et le convertit en liste Python."""
    src = FICHIER_CLASSES.read_text(encoding="utf-8")
    debut = src.index("window.CDSG = [") + len("window.CDSG = ")
    bloc = src[debut:src.rindex("]") + 1]
    bloc = re.sub(r"//[^\n]*", "", bloc)                       # commentaires
    bloc = re.sub(r'([{,]\s*)([a-zA-Z_]+)\s*:', r'\1"\2":', bloc)  # clés sans guillemets
    bloc = re.sub(r",\s*([}\]])", r"\1", bloc)                 # virgules finales
    bloc = bloc.replace(":true", ":true").replace(":false", ":false")
    classes = json.loads(bloc)
    for c in classes:
        c["id"] = slug(c["etab"] + " " + c["ville"])
    return classes


def lire_existant():
    if not FICHIER_SORTIE.exists():
        return {}
    src = FICHIER_SORTIE.read_text(encoding="utf-8")
    m = re.search(r"window\.CDSG_WEB\s*=\s*(\{.*\});", src, re.S)
    return json.loads(m.group(1)) if m else {}


def ecrire(resultats):
    FICHIER_SORTIE.write_text(
        "// Compléments trouvés en ligne — fichier généré par recherche/recherche_web.py\n"
        "// Ne pas modifier à la main : relancer le script (ou l'action GitHub « Recherche web »).\n"
        "window.CDSG_WEB = " + json.dumps(resultats, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8")


def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        brut = r.read(600_000)
        enc = r.headers.get_content_charset() or "utf-8"
        return brut.decode(enc, errors="replace")


class Texte(HTMLParser):
    def __init__(self):
        super().__init__(); self.out = []; self.skip = 0
    def handle_starttag(self, tag, a):
        if tag in ("script", "style", "noscript", "svg", "nav", "footer"): self.skip += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "nav", "footer") and self.skip: self.skip -= 1
    def handle_data(self, d):
        if not self.skip and d.strip(): self.out.append(d.strip())


def texte_page(url, maxi=6000):
    try:
        p = Texte(); p.feed(http_get(url)); t = " ".join(p.out)
        return re.sub(r"\s+", " ", t)[:maxi]
    except Exception as e:
        return ""


def recherche_web(requete, n=4):
    """Résultats DuckDuckGo (version HTML, sans clé)."""
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": requete, "kl": "fr-fr"})
    try:
        page = http_get(url)
    except Exception as e:
        print(f"   ! recherche impossible : {e}", file=sys.stderr); return []
    liens = re.findall(r'class="result__a"[^>]*href="([^"]+)"', page)
    propres = []
    for l in liens:
        l = html.unescape(l)
        if "uddg=" in l:
            l = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlparse(l).query).get("uddg", [l])[0])
        if l.startswith("http") and "duckduckgo.com" not in l and l not in propres:
            propres.append(l)
    return propres[:n]


# ───────────────────────── modèle ─────────────────────────
def api(chemin, corps=None):
    req = urllib.request.Request(BASE + chemin, method="POST" if corps else "GET",
        data=json.dumps(corps).encode() if corps else None,
        headers={"Authorization": "Bearer " + CLE, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def choisir_modele():
    global MODELE
    if MODELE: return MODELE
    ids = [m["id"] for m in api("/models").get("data", [])
           if not m.get("type") or re.search(r"text-generation|chat", m.get("type", ""))]
    for motif in (r"mistral-medium", r"mistral-small", r"large", r"llama-3\.3", r"70b"):
        for i in ids:
            if re.search(motif, i, re.I): MODELE = i; return MODELE
    MODELE = ids[0]; return MODELE


def demander(systeme, utilisateur, jsonmode=True):
    corps = {"model": choisir_modele(), "temperature": 0.1, "max_tokens": 700,
             "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": utilisateur}]}
    for essai in range(3):
        try:
            rep = api("/chat/completions", corps)["choices"][0]["message"]["content"]
            if not jsonmode: return rep
            m = re.search(r"\{.*\}", rep, re.S)
            return json.loads(m.group(0)) if m else None
        except Exception as e:
            print(f"   ! appel modèle ({e}), nouvel essai…", file=sys.stderr); time.sleep(4 * (essai + 1))
    return None


SYSTEME_FICHE = """Tu complètes la fiche d'une classe défense et sécurité globales (CDSG) de l'académie d'Aix-Marseille.
On te donne la fiche actuelle et le texte de pages web. Ne retiens que ce qui concerne CET établissement et sa classe défense.
N'invente rien. Réponds uniquement en JSON :
{"pertinent": true|false,
 "resume": "2 à 3 phrases factuelles en français : activités récentes, dates, partenaires, référents cités",
 "activite_recente": "année la plus récente où une activité de la classe est attestée, ou null",
 "unite": "unité marraine citée ou null",
 "referents": "noms de professeurs cités ou null",
 "sources": ["url des pages réellement utilisées"]}"""


def traiter_fiche(c):
    requetes = [f'"{c["etab"]}" {c["ville"]} classe défense',
                f'{c["etab"]} {c["ville"]} CDSG {c["unite"] if c["unite"] not in ("—", "") else ""}'.strip()]
    urls = []
    for q in requetes:
        for u in recherche_web(q):
            if u not in urls: urls.append(u)
        time.sleep(1.5)
    urls = urls[:5]
    pages = []
    for u in urls:
        t = texte_page(u)
        if t: pages.append(f"--- {u}\n{t}")
    if not pages:
        return None
    fiche = {k: c.get(k) for k in ("etab", "ville", "dep", "statut", "ce", "ref", "unite", "conv", "note")}
    r = demander(SYSTEME_FICHE, "Fiche :\n" + json.dumps(fiche, ensure_ascii=False) + "\n\nPages :\n" + "\n\n".join(pages)[:24000])
    if not r or not r.get("pertinent"):
        return None
    r["sources"] = [s for s in r.get("sources", []) if s in urls] or urls[:2]
    r["date"] = datetime.date.today().strftime("%d/%m/%Y")
    return r


def question_libre(question, classes, resultats):
    """Répond à une question sur l'ensemble du dossier et indique les fiches concernées."""
    lignes = []
    for c in classes:
        w = resultats.get(c["id"], {})
        lignes.append(f'[{c["id"]}] {c["etab"]} | {c["ville"]} | {c["dep"]} | {c["statut"]}{" (à vérifier)" if c.get("verifier") else ""} '
                      f'| CE {c["ce"]} | réf. {c["ref"]} | unité {c["unite"]} | conv. {c["conv"]} | {c.get("note","")} '
                      f'{"| en ligne : " + w.get("resume","") if w else ""}')
    rep = demander("Tu réponds à un inspecteur sur le dossier des CDSG de l'académie d'Aix-Marseille, uniquement à partir des fiches. "
                   "Réponds en français, brièvement. Termine par une ligne 'FICHES: id1, id2'.",
                   "Fiches :\n" + "\n".join(lignes) + "\n\nQuestion : " + question, jsonmode=False)
    print(rep or "Pas de réponse du service.")


# ───────────────────────── programme ─────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Recherche web pour compléter les fiches CDSG")
    ap.add_argument("--statut", choices=["active", "dormante", "projet"])
    ap.add_argument("--verifier", action="store_true", help="seulement les fiches « à vérifier »")
    ap.add_argument("--fiche", help="identifiant d'une fiche (ex. lycee-thiers-marseille)")
    ap.add_argument("--max", type=int, default=0, help="nombre maximum de fiches à traiter")
    ap.add_argument("--refaire", action="store_true", help="refaire aussi les fiches déjà complétées")
    ap.add_argument("--question", help="poser une question sur le dossier au lieu de chercher")
    a = ap.parse_args()

    if not CLE:
        sys.exit("Clé absente : export ALBERT_API_KEY=\"…\" (ou secret GitHub ALBERT_API_KEY).")

    classes = lire_classes()
    resultats = lire_existant()
    print(f"{len(classes)} fiches · service {BASE} · modèle {choisir_modele()}")

    if a.question:
        question_libre(a.question, classes, resultats); return

    cible = [c for c in classes
             if (not a.statut or c["statut"] == a.statut)
             and (not a.verifier or c.get("verifier"))
             and (not a.fiche or c["id"] == a.fiche)
             and (a.refaire or a.fiche or c["id"] not in resultats)]
    if a.max: cible = cible[:a.max]
    print(f"{len(cible)} fiche(s) à traiter")

    for i, c in enumerate(cible, 1):
        print(f"[{i}/{len(cible)}] {c['etab']} ({c['ville']})")
        r = traiter_fiche(c)
        if r:
            resultats[c["id"]] = r
            ecrire(resultats)  # sauvegarde au fil de l'eau
            print("   ✓", r.get("resume", "")[:110])
        else:
            print("   – rien de pertinent")
    ecrire(resultats)
    print(f"Terminé : {FICHIER_SORTIE.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
