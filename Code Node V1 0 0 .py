"""
Éditeur de code Python à blocs — version 2 (projets multi-programmes).

Installation :  py -m pip install PySide6
Lancement    :  py editeur_code_blocs_v2.py

Nouveautés :
  - Projet = un dossier contenant plusieurs programmes (blocs) et des documents
  - Explorateur de projet : programmes, documents (txt, csv, json…), dossiers
  - Un programme peut en appeler un autre (bloc « Appeler un programme »)
  - Blocs « Importer » (bibliothèques), « Lire / Écrire un fichier » (documents)
  - Gestionnaire de bibliothèques (installation avec pip)
  - Blocs rangés dans des dossiers, dossiers personnalisables pour vos modèles
  - Export : un programme, tout le projet (dossier), TOUT EN UN SEUL FICHIER, ou .exe
"""

import importlib.util
import json
import keyword
import os
import re
import shutil
import sys
import tempfile
import textwrap
from pathlib import Path

from PySide6.QtCore import (
    QLineF, QMimeData, QPointF, QProcess, QProcessEnvironment, QRectF,
    QSettings, QSize, Qt, QTimer, QUrl, Signal,
)
from PySide6.QtGui import (
    QAction, QColor, QCursor, QDesktopServices, QFont, QFontDatabase,
    QFontMetrics, QIcon, QKeySequence, QPainter, QPainterPath,
    QPainterPathStroker, QPalette, QPen, QPixmap, QSyntaxHighlighter,
    QTextCharFormat, QTextCursor,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QColorDialog, QComboBox, QDialog,
    QDialogButtonBox, QDockWidget, QFileDialog, QFormLayout, QGraphicsItem,
    QGraphicsPathItem, QGraphicsScene, QGraphicsView, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu,
    QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy, QStyle,
    QTableWidget, QTableWidgetItem, QTabWidget, QToolBar, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

# PURE-START ================================================================ #
#  PARTIE SANS INTERFACE : définition des blocs + génération du code Python
# =========================================================================== #
BLOCKS = {
    # Flux
    "start":   dict(label="Début",              color="#22c55e", outs=["Suite"], has_in=False, folder="Flux"),
    "end":     dict(label="Fin / Retour",       color="#ef4444", outs=[], folder="Flux"),
    "if":      dict(label="Si / Sinon",         color="#f59e0b", outs=["Vrai", "Faux"], folder="Flux"),
    "repeat":  dict(label="Répéter",            color="#ec4899", outs=["Corps", "Après"], folder="Flux"),
    "while":   dict(label="Tant que",           color="#f43f5e", outs=["Corps", "Après"], folder="Flux"),
    "foreach": dict(label="Pour chaque",        color="#d946ef", outs=["Corps", "Après"], folder="Flux"),
    "sleep":   dict(label="Attendre",           color="#64748b", outs=["Suite"], folder="Flux"),
    # Données
    "var":     dict(label="Variable",           color="#a855f7", outs=["Suite"], folder="Données"),
    "input":   dict(label="Saisie",             color="#06b6d4", outs=["Suite"], folder="Données"),
    "print":   dict(label="Afficher",           color="#3b82f6", outs=["Suite"], folder="Données"),
    "append":  dict(label="Ajouter à une liste", color="#8b5cf6", outs=["Suite"], folder="Données"),
    "random":  dict(label="Nombre aléatoire",   color="#14b8a6", outs=["Suite"], folder="Données"),
    "now":     dict(label="Date et heure",      color="#0ea5e9", outs=["Suite"], folder="Données"),
    # Fichiers
    "readfile":  dict(label="Lire un document",    color="#84cc16", outs=["Suite"], folder="Fichiers"),
    "writefile": dict(label="Écrire un document",  color="#f97316", outs=["Suite"], folder="Fichiers"),
    # Bibliothèques & programmes
    "import":  dict(label="Importer",           color="#6366f1", outs=["Suite"], folder="Bibliothèques & programmes"),
    "call":    dict(label="Appeler un programme", color="#0f766e", outs=["Suite"], folder="Bibliothèques & programmes"),
    # Code
    "code":    dict(label="Code Python",        color="#10b981", outs=["Suite"], folder="Code"),
}
FOLDER_ORDER = ["Flux", "Données", "Fichiers", "Bibliothèques & programmes", "Code"]
DEFAULT_FOLDER = "Mes modèles"
PORT_COLORS = {"Vrai": "#22c55e", "Faux": "#ef4444", "Corps": "#ec4899", "Après": "#f59e0b"}

DEFAULTS = {
    "start": {"params": ""}, "end": {"value": ""},
    "print": {"expr": '"Bonjour !"'},
    "var": {"name": "x", "expr": "0"},
    "input": {"name": "reponse", "prompt": "Votre réponse : "},
    "append": {"list": "liste", "value": "1"},
    "random": {"name": "de", "min": "1", "max": "6"},
    "now": {"name": "maintenant", "fmt": "%d/%m/%Y %H:%M:%S"},
    "if": {"cond": "x > 0"},
    "repeat": {"count": "5"},
    "while": {"cond": "x < 10"},
    "foreach": {"var": "element", "iterable": "liste"},
    "sleep": {"seconds": "1"},
    "readfile": {"path": "documents/notes.txt", "name": "contenu", "mode": "Tout le texte"},
    "writefile": {"path": "documents/sortie.txt", "expr": '"Bonjour"', "mode": "Écraser"},
    "import": {"module": "random", "alias": "", "names": ""},
    "call": {"program": "", "args": "", "result": ""},
    "code": {"code": "# Écrivez votre code Python ici\nprint('Hello')"},
}
# (clé, libellé, type de champ[, options])  — types : line, code, doc, prog, lib, choice
FIELDS = {
    "start": [("params", "Paramètres du programme (ex : nom, age)", "line")],
    "end": [("value", "Valeur retournée (optionnel)", "line")],
    "print": [("expr", 'Expression à afficher (ex : "texte" ou x)', "line")],
    "var": [("name", "Nom de la variable", "line"), ("expr", "Valeur (expression Python)", "line")],
    "input": [("name", "Variable qui reçoit la réponse", "line"), ("prompt", "Message affiché", "line")],
    "append": [("list", "Liste", "line"), ("value", "Valeur à ajouter", "line")],
    "random": [("name", "Variable", "line"), ("min", "Minimum", "line"), ("max", "Maximum", "line")],
    "now": [("name", "Variable", "line"), ("fmt", "Format (ex : %d/%m/%Y %H:%M)", "line")],
    "if": [("cond", "Condition (ex : x > 5)", "line")],
    "repeat": [("count", "Nombre de répétitions", "line")],
    "while": [("cond", "Condition (ex : x < 10)", "line")],
    "foreach": [("var", "Variable de l'élément", "line"), ("iterable", "Liste / texte à parcourir", "line")],
    "sleep": [("seconds", "Durée en secondes", "line")],
    "readfile": [("path", "Document (chemin dans le projet)", "doc"), ("name", "Variable qui reçoit le contenu", "line"),
                 ("mode", "Lire comme", "choice", ["Tout le texte", "Liste de lignes"])],
    "writefile": [("path", "Document (chemin dans le projet)", "doc"), ("expr", "Contenu à écrire (expression)", "line"),
                  ("mode", "Écriture", "choice", ["Écraser", "Ajouter à la fin"])],
    "import": [("module", "Bibliothèque (ex : random, numpy)", "lib"),
               ("alias", "Alias optionnel (import … as …)", "line"),
               ("names", "Noms précis optionnels (from … import …)", "line")],
    "call": [("program", "Programme à appeler", "prog"), ("args", "Arguments (ex : nom, 3)", "line"),
             ("result", "Variable qui reçoit le résultat (optionnel)", "line")],
    "code": [("code", "Code Python", "code")],
}
COMMON_LIBS = ["random", "math", "os", "sys", "json", "csv", "datetime", "time", "re", "pathlib",
               "itertools", "collections", "statistics", "shutil", "subprocess", "urllib.request",
               "requests", "numpy", "pandas", "matplotlib", "tkinter"]
PIP_NAMES = {"cv2": "opencv-python", "PIL": "pillow", "sklearn": "scikit-learn", "yaml": "pyyaml",
             "bs4": "beautifulsoup4", "dateutil": "python-dateutil", "serial": "pyserial",
             "Crypto": "pycryptodome", "skimage": "scikit-image"}
DOC_HELPER = [
    "# Dossier de travail : les chemins des blocs « Document » sont relatifs à ce dossier.",
    '_BASE = os.environ.get("BLOCS_BASE") or (',
    '    os.path.dirname(sys.executable) if getattr(sys, "frozen", False)',
    "    else os.path.dirname(os.path.abspath(__file__))",
    ")",
    "",
    "",
    "def _doc(chemin):",
    '    return os.path.join(_BASE, *chemin.split("/"))',
]


def py_name(stem):
    """Nom de programme -> nom de module Python valide (sans conflit avec la bibliothèque standard)."""
    n = re.sub(r"\W", "_", str(stem).strip()) or "programme"
    if n[0].isdigit():
        n = "p_" + n
    if keyword.iskeyword(n) or n in getattr(sys, "stdlib_module_names", ()):
        n += "_prog"
    if not n.isidentifier():
        n = "p_" + "".join(c if (c.isascii() and (c.isalnum() or c == "_")) else "_" for c in n)
    return n


def unique_py_names(stems):
    used, out = set(), {}
    for s in stems:
        base = py_name(s)
        n, i = base, 2
        while n in used:
            n = f"{base}_{i}"
            i += 1
        used.add(n)
        out[s] = n
    return out


def ind(lines):
    return [("    " + ln) if ln else ln for ln in lines]


class Graph:
    """Graphe d'un programme, construit depuis les données JSON (sans interface)."""

    def __init__(self, data):
        self.nodes = {}
        for d in data.get("nodes", []):
            if d.get("kind") in BLOCKS and "id" in d:
                self.nodes[d["id"]] = d
        self.out = {}
        for a, idx, b in data.get("edges", []):
            if a not in self.nodes or b not in self.nodes or a == b:
                continue
            if idx >= len(BLOCKS[self.nodes[a]["kind"]]["outs"]):
                continue
            if not BLOCKS[self.nodes[b]["kind"]].get("has_in", True):
                continue
            if a in self.reach(b):  # créerait une boucle
                continue
            self.out[(a, idx)] = b

    def kind(self, nid):
        return self.nodes[nid]["kind"]

    def params(self, nid):
        d = self.nodes[nid]
        p = dict(DEFAULTS.get(d["kind"], {}))
        p.update(d.get("params") or {})
        return p

    def nxt(self, nid, i=0):
        return self.out.get((nid, i)) if nid is not None else None

    def succ(self, nid):
        n = len(BLOCKS[self.kind(nid)]["outs"])
        return [self.out[(nid, i)] for i in range(n) if (nid, i) in self.out]

    def reach(self, nid):
        seen, stack = set(), [nid]
        while stack:
            n = stack.pop()
            if n is None or n in seen:
                continue
            seen.add(n)
            stack.extend(self.succ(n))
        return seen

    def start(self):
        ids = sorted(i for i, d in self.nodes.items() if d["kind"] == "start")
        return ids[0] if ids else None


def generate_body(data, call_expr):
    """Transforme un programme (dict JSON) en corps de fonction Python.

    call_expr(nom_programme) -> expression Python qui appelle ce programme.
    Retourne un dict : body, params, imports, modules, needs_doc, calls, warnings.
    """
    g = Graph(data)
    res = dict(body=[], params=[], imports=set(), modules=set(), needs_doc=False,
               calls=set(), warnings=[])
    start = g.start()
    if start is None:
        res["warnings"].append("Aucun bloc « Début ».")
        return res
    if sum(1 for d in g.nodes.values() if d["kind"] == "start") > 1:
        res["warnings"].append("Plusieurs blocs « Début » : seul le premier est utilisé.")
    reach = g.reach(start)
    ignored = [n for n in g.nodes if n not in reach]
    if ignored:
        res["warnings"].append(f"{len(ignored)} bloc(s) non relié(s) au Début : ignoré(s).")

    for part in g.params(start).get("params", "").split(","):
        name = part.strip()
        if not name:
            continue
        if name.isidentifier():
            res["params"].append(name)
        else:
            res["warnings"].append(f"Paramètre invalide dans « Début » : « {name} ».")

    def lib(mod):
        if mod:
            res["modules"].add(mod.split(".")[0])

    def ident(name, kind):
        name = (name or "").strip()
        if not name.isidentifier():
            res["warnings"].append(f"Nom de variable invalide dans « {BLOCKS[kind]['label']} » : « {name} ».")
        return name or "_"

    def first_common(a, b):
        rb = g.reach(b)
        queue, seen = [a], set()
        while queue:
            x = queue.pop(0)
            if x in seen:
                continue
            seen.add(x)
            if x in rb:
                return x
            queue.extend(g.succ(x))
        return None

    def gen(node, stop, depth):
        out = []
        while node is not None and node not in stop:
            k, p = g.kind(node), g.params(node)
            if k not in ("import",) and (p.get("comment") or "").strip():
                out.append("# " + " ".join(p["comment"].split()))
            cont = g.nxt(node)
            if k == "print":
                out.append(f"print({p.get('expr', '').strip()})")
            elif k == "var":
                out.append(f"{ident(p.get('name'), k)} = {p.get('expr', '').strip() or 'None'}")
            elif k == "input":
                out.append(f"{ident(p.get('name'), k)} = input({p.get('prompt', '')!r})")
            elif k == "append":
                out.append(f"{p.get('list', '').strip() or 'liste'}.append({p.get('value', '').strip() or 'None'})")
            elif k == "random":
                res["imports"].add("import random")
                lib("random")
                out.append(f"{ident(p.get('name'), k)} = random.randint("
                           f"{p.get('min', '').strip() or '1'}, {p.get('max', '').strip() or '6'})")
            elif k == "now":
                res["imports"].add("import datetime")
                lib("datetime")
                out.append(f"{ident(p.get('name'), k)} = datetime.datetime.now()"
                           f".strftime({p.get('fmt', '') or '%d/%m/%Y %H:%M:%S'!r})")
            elif k == "sleep":
                res["imports"].add("import time")
                lib("time")
                out.append(f"time.sleep({p.get('seconds', '').strip() or '0'})")
            elif k == "import":
                mod = p.get("module", "").strip()
                alias, names = p.get("alias", "").strip(), p.get("names", "").strip()
                if not mod:
                    res["warnings"].append("Un bloc « Importer » n'a pas de bibliothèque.")
                else:
                    lib(mod)
                    if names:
                        res["imports"].add(f"from {mod} import {names}")
                    elif alias:
                        res["imports"].add(f"import {mod} as {alias}")
                    else:
                        res["imports"].add(f"import {mod}")
            elif k == "call":
                target = p.get("program", "").strip()
                if not target:
                    res["warnings"].append("Un bloc « Appeler un programme » n'a pas de programme choisi.")
                    out.append("pass")
                else:
                    res["calls"].add(target)
                    expr = f"{call_expr(target)}({p.get('args', '').strip()})"
                    rv = p.get("result", "").strip()
                    out.append(f"{ident(rv, k)} = {expr}" if rv else expr)
            elif k == "readfile":
                res["needs_doc"] = True
                path = p.get("path", "").strip()
                if not path:
                    res["warnings"].append("Un bloc « Lire un document » n'a pas de chemin.")
                name = ident(p.get("name"), k)
                out.append('with open(_doc(%r), encoding="utf-8") as _f:' % path)
                if p.get("mode", "").startswith("Liste"):
                    out.append(f"    {name} = _f.read().splitlines()")
                else:
                    out.append(f"    {name} = _f.read()")
            elif k == "writefile":
                res["needs_doc"] = True
                path = p.get("path", "").strip()
                if not path:
                    res["warnings"].append("Un bloc « Écrire un document » n'a pas de chemin.")
                mode = "a" if p.get("mode", "").startswith("Ajouter") else "w"
                out.append("os.makedirs(os.path.dirname(_doc(%r)), exist_ok=True)" % path)
                out.append('with open(_doc(%r), %r, encoding="utf-8") as _f:' % (path, mode))
                out.append(f"    _f.write(str({p.get('expr', '').strip() or chr(34) * 2}))")
            elif k == "code":
                code = textwrap.dedent(p.get("code", "")).strip("\n")
                for m in re.finditer(r"^\s*(?:from|import)\s+([A-Za-z_]\w*)", code, re.M):
                    lib(m.group(1))
                out.extend(code.splitlines() or ["pass"])
            elif k == "end":
                val = p.get("value", "").strip()
                out.append(f"return {val}" if val else "return")
                cont = None
            elif k == "if":
                t, f = g.nxt(node, 0), g.nxt(node, 1)
                merge = first_common(t, f) if (t is not None and f is not None) else None
                st = (stop | {merge}) if merge is not None else stop
                out.append(f"if {p.get('cond', '').strip() or 'True'}:")
                out.extend(ind(gen(t, st, depth) or ["pass"]))
                other = gen(f, st, depth)
                if other:
                    out.append("else:")
                    out.extend(ind(other))
                cont = merge
            elif k in ("repeat", "while", "foreach"):
                body, after = g.nxt(node, 0), g.nxt(node, 1)
                st = (stop | g.reach(after)) if after is not None else stop
                if k == "repeat":
                    out.append(f"for _i{depth} in range({p.get('count', '').strip() or '1'}):")
                elif k == "while":
                    out.append(f"while {p.get('cond', '').strip() or 'True'}:")
                else:
                    out.append(f"for {ident(p.get('var'), k)} in {p.get('iterable', '').strip() or '[]'}:")
                out.extend(ind(gen(body, st, depth + 1) or ["pass"]))
                cont = after
            node = cont
        return out

    res["body"] = gen(start, set(), 0)
    return res


def signature(res):
    return ", ".join(f"{n}=None" for n in res["params"])


def assemble_module(name, res, names):
    """Un programme -> un fichier .py autonome (appelle les autres programmes par import)."""
    imports = set(res["imports"])
    if res["needs_doc"]:
        imports |= {"import os", "import sys"}
    head = [f"# Programme « {name} » — généré par l'Éditeur de blocs"] + sorted(imports)
    for c in sorted(res["calls"]):
        if c != name:
            head.append(f"import {names.get(c) or py_name(c)}")
    sections = ["\n".join(head)]
    if res["needs_doc"]:
        sections.append("\n".join(DOC_HELPER))
    sections.append("\n".join([f"def main({signature(res)}):"] + ind(res["body"] or ["pass"])))
    sections.append('if __name__ == "__main__":\n    main()')
    return "\n\n\n".join(sections) + "\n"


def module_source(name, data, names):
    def call_expr(target):
        return "main" if target == name else f"{names.get(target) or py_name(target)}.main"

    res = generate_body(data, call_expr)
    return assemble_module(name, res, names), res


def compile_modules(entry_name, entry_data, get_data, names):
    """Génère le programme d'entrée + tous les programmes qu'il appelle (un fichier chacun)."""
    files, warnings, seen = {}, [], set()
    queue = [(entry_name, entry_data)]
    while queue:
        n, data = queue.pop()
        if n in seen:
            continue
        seen.add(n)
        code, res = module_source(n, data, names)
        files[(names.get(n) or py_name(n)) + ".py"] = code
        warnings += [f"[{n}] {w}" for w in res["warnings"]]
        for c in sorted(res["calls"]):
            if c in seen:
                continue
            d = get_data(c)
            if d is None:
                warnings.append(f"[{n}] Programme « {c} » introuvable.")
            else:
                queue.append((c, d))
    return files, warnings, (names.get(entry_name) or py_name(entry_name)) + ".py"


def compile_bundle(main_name, get_data, names):
    """Fusionne le programme principal et tous ceux qu'il appelle en UN SEUL fichier .py."""
    warnings, results, missing = [], {}, []
    stack = [main_name]

    def call_expr(target):
        return "prog_" + (names.get(target) or py_name(target))

    while stack:
        n = stack.pop()
        if n in results or n in missing:
            continue
        data = get_data(n)
        if data is None:
            missing.append(n)
            warnings.append(f"Programme « {n} » introuvable : appel désactivé.")
            continue
        res = generate_body(data, call_expr)
        results[n] = res
        warnings += [f"[{n}] {w}" for w in res["warnings"]]
        stack.extend(sorted(res["calls"], reverse=True))
    order = [n for n in results if n != main_name] + ([main_name] if main_name in results else [])
    imports, needs_doc = set(), False
    for n in order:
        imports |= results[n]["imports"]
        needs_doc = needs_doc or results[n]["needs_doc"]
    if needs_doc:
        imports |= {"import os", "import sys"}
    sections = ["\n".join(["# Projet complet : tous les programmes fusionnés en un seul fichier",
                           "# Généré par l'Éditeur de blocs"] + sorted(imports))]
    if needs_doc:
        sections.append("\n".join(DOC_HELPER))
    for n in missing:
        fn = call_expr(n)
        sections.append(f"def {fn}(*args, **kwargs):\n    raise NotImplementedError({('Programme ' + n + ' introuvable')!r})")
    for n in order:
        r = results[n]
        fn = call_expr(n)
        sections.append("\n".join([f"# --- Programme « {n} » ---", f"def {fn}({signature(r)}):"]
                                  + ind(r["body"] or ["pass"])))
    if main_name in results:
        sections.append(f'if __name__ == "__main__":\n    {call_expr(main_name)}()')
    return "\n\n\n".join(sections) + "\n", warnings


def make_graph(spec, edges):
    """spec : [(type, paramètres, x, y)], edges : [(index source, sortie, index destination)]."""
    return {
        "version": 2,
        "nodes": [dict(id=i + 1, kind=k, params=p, label=None, color=None, x=x, y=y)
                  for i, (k, p, x, y) in enumerate(spec)],
        "edges": [[a + 1, o, b + 1] for a, o, b in edges],
    }


def blank_program():
    return make_graph([("start", {}, 0, 0), ("end", {}, 280, 0)], [(0, 0, 1)])


def example_graph():
    spec = [
        ("start", {}, 0, 0),
        ("input", dict(name="nom", prompt="Votre prénom : "), 280, 0),
        ("if", dict(cond='nom.strip() != ""'), 560, 0),
        ("print", dict(expr='f"Bonjour {nom} !"'), 860, -100),
        ("print", dict(expr='"Bonjour inconnu !"'), 860, 100),
        ("repeat", dict(count="3"), 1160, 0),
        ("random", dict(name="de", min="1", max="6", comment="Lancer un dé"), 1460, -100),
        ("end", {}, 1460, 100),
    ]
    return make_graph(spec, [(0, 0, 1), (1, 0, 2), (2, 0, 3), (2, 1, 4), (3, 0, 5), (4, 0, 5),
                             (5, 0, 6), (5, 1, 7)])


def sample_project(root):
    """Crée un petit projet d'exemple : 2 programmes + 1 document."""
    root = Path(root)
    for sub in ("programmes", "documents", "sortie"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    principal = make_graph([
        ("start", {}, 0, 0),
        ("input", dict(name="nom", prompt="Votre prénom : "), 280, 0),
        ("call", dict(program="utilitaires", args="nom", result="salut"), 560, 0),
        ("print", dict(expr="salut"), 840, 0),
        ("readfile", dict(path="documents/notes.txt", name="notes", mode="Tout le texte"), 1120, 0),
        ("print", dict(expr='"Notes du projet : " + notes'), 1400, 0),
        ("writefile", dict(path="documents/journal.txt", expr='salut + "\\n"', mode="Ajouter à la fin"), 1680, 0),
        ("end", {}, 1960, 0),
    ], [(0, 0, 1), (1, 0, 2), (2, 0, 3), (3, 0, 4), (4, 0, 5), (5, 0, 6), (6, 0, 7)])
    utilitaires = make_graph([
        ("start", dict(params="nom"), 0, 0),
        ("var", dict(name="message", expr='"Bonjour " + str(nom) + " !"'), 280, 0),
        ("end", dict(value="message"), 560, 0),
    ], [(0, 0, 1), (1, 0, 2)])
    for name, graph in (("principal", principal), ("utilitaires", utilitaires)):
        (root / "programmes" / f"{name}.json").write_text(
            json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    (root / "documents" / "notes.txt").write_text(
        "Ceci est un document du projet.\nIl peut être lu et modifié par les blocs.\n", encoding="utf-8")
    (root / "projet.json").write_text(json.dumps({"version": 1, "main": "principal"}, indent=2),
                                      encoding="utf-8")


def module_status(mod):
    if mod in getattr(sys, "stdlib_module_names", ()):
        return "intégrée"
    try:
        return "installée" if importlib.util.find_spec(mod) is not None else "manquante"
    except (ImportError, ValueError, AttributeError):
        return "manquante"
# PURE-END ================================================================== #


THEMES = {
    "Sombre": dict(bg="#1b1c23", surface="#262833", surface2="#31344a",
                   text="#e8e9f0", muted="#8b8fa8", accent="#4c8dff", border="#3a3d52"),
    "Clair": dict(bg="#f2f4fa", surface="#ffffff", surface2="#e8ecf6",
                  text="#1f2430", muted="#6b7385", accent="#2f6bff", border="#d5dbea"),
    "Océan": dict(bg="#0a1f2c", surface="#0f3247", surface2="#164761",
                  text="#e3f4fb", muted="#7fb2c7", accent="#19c3d6", border="#1d5775"),
    "Forêt": dict(bg="#121e17", surface="#1b2f25", surface2="#264033",
                  text="#e6f2ea", muted="#8bb09a", accent="#4cc380", border="#305040"),
    "Néon": dict(bg="#0d0221", surface="#1a0b3a", surface2="#2a1259",
                 text="#f4eaff", muted="#a98bd6", accent="#ff2bd6", border="#3d1c80"),
    "Papier": dict(bg="#f7f3ec", surface="#fffdf9", surface2="#eee7da",
                   text="#2b2620", muted="#8a7f70", accent="#c26a3d", border="#ddd3c1"),
}
TEXT_EXT = {".txt", ".csv", ".json", ".md", ".py", ".ini", ".log", ".xml", ".html",
            ".yaml", ".yml", ".tsv", ".cfg", ".toml"}


def contrast_text(hex_color):
    c = QColor(hex_color)
    return "#111111" if 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue() > 170 else "#ffffff"


def color_icon(color, size=16):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), 4, 4)
    p.end()
    return QIcon(pix)


def bezier(a, b):
    dx = max(60.0, abs(b.x() - a.x()) * 0.5)
    path = QPainterPath(a)
    path.cubicTo(QPointF(a.x() + dx, a.y()), QPointF(b.x() - dx, b.y()), b)
    return path


def find_node(item):
    while item is not None and not isinstance(item, Node):
        item = item.parentItem()
    return item


def summary(kind, p):
    g = lambda k: str(p.get(k, "")).strip()
    if kind == "start":
        return f"def main({g('params')})" if g("params") else "Point de départ du programme"
    if kind == "end":
        return f"retourner {g('value')}" if g("value") else "Termine le programme"
    if kind == "print":
        return f"print({g('expr')})"
    if kind == "var":
        return f"{g('name')} = {g('expr')}"
    if kind == "input":
        return f"{g('name')} = input(…)"
    if kind == "append":
        return f"{g('list')}.append({g('value')})"
    if kind == "random":
        return f"{g('name')} = aléatoire({g('min')} à {g('max')})"
    if kind == "now":
        return f"{g('name')} = date et heure"
    if kind == "if":
        return f"si {g('cond')}"
    if kind == "repeat":
        return f"répéter {g('count')} fois"
    if kind == "while":
        return f"tant que {g('cond')}"
    if kind == "foreach":
        return f"pour {g('var')} dans {g('iterable')}"
    if kind == "sleep":
        return f"attendre {g('seconds')} s"
    if kind == "readfile":
        return f"{g('name')} ← {g('path')}"
    if kind == "writefile":
        return f"{g('path')} ← {g('expr')}"
    if kind == "import":
        mod = g("module")
        if g("names"):
            return f"from {mod} import {g('names')}"
        return f"import {mod}" + (f" as {g('alias')}" if g("alias") else "")
    if kind == "call":
        return (f"{g('result')} = " if g("result") else "") + f"{g('program') or '?'}({g('args')})"
    return p.get("code", "")


# =========================================================================== #
#  Éléments graphiques : Port, Bloc, Liaison
# =========================================================================== #
class Port(QGraphicsItem):
    def __init__(self, node, is_output, index, label):
        super().__init__(node)
        self.node, self.is_output, self.index, self.label = node, is_output, index, label
        self.edges = []
        self.hover = False
        self.setZValue(3)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CrossCursor)

    def boundingRect(self):
        return QRectF(-11, -11, 22, 22)

    def shape(self):
        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), 11, 11)
        return path

    def hoverEnterEvent(self, event):
        self.hover = True
        self.update()

    def hoverLeaveEvent(self, event):
        self.hover = False
        self.update()

    def paint(self, p, option, widget=None):
        th = self.scene().theme
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor(PORT_COLORS.get(self.label, th["accent"]))
        r = 8.5 if self.hover else 6.5
        p.setPen(QPen(col, 2.2))
        p.setBrush(col if (self.edges or self.hover) else QColor(th["surface"]))
        p.drawEllipse(QPointF(0, 0), r, r)


class Node(QGraphicsItem):
    W = 230

    def __init__(self, kind, params, node_id, label=None, color=None):
        super().__init__()
        self.id, self.kind = node_id, kind
        self.params = dict(DEFAULTS.get(kind, {}))
        self.params.update(params or {})
        self.params.setdefault("comment", "")
        self.label, self.color = label, color
        spec = BLOCKS[kind]
        n = len(spec["outs"])
        self.H = 96 if kind == "code" else (104 if n >= 2 else 76)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable
                      | QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(1)
        in_y = 28 + (self.H - 28) / 2
        self.in_port = None
        if spec.get("has_in", True):
            self.in_port = Port(self, False, 0, "")
            self.in_port.setPos(0, in_y)
        self.out_ports = []
        for i, lab in enumerate(spec["outs"]):
            port = Port(self, True, i, lab)
            port.setPos(self.W, in_y if n == 1 else 66 + 24 * i)
            self.out_ports.append(port)

    def all_ports(self):
        return ([self.in_port] if self.in_port else []) + self.out_ports

    def boundingRect(self):
        return QRectF(-3, -3, self.W + 6, self.H + 6)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene() is not None:
            if self.scene().snap:
                g = self.scene().GRID
                return QPointF(round(value.x() / g) * g, round(value.y() / g) * g)
        elif change == QGraphicsItem.ItemPositionHasChanged:
            for port in self.all_ports():
                for e in port.edges:
                    e.update_path()
            if self.scene() is not None:
                self.scene().moved.emit()
        return super().itemChange(change, value)

    def paint(self, p, option, widget=None):
        th = self.scene().theme
        p.setRenderHint(QPainter.Antialiasing)
        sel = self.isSelected()
        body = QPainterPath()
        body.addRoundedRect(QRectF(0, 0, self.W, self.H), 12, 12)
        p.setPen(QPen(QColor(th["accent"]) if sel else QColor(th["border"]), 2.6 if sel else 1.2))
        p.setBrush(QColor(th["surface"]))
        p.drawPath(body)

        color = QColor(self.color or BLOCKS[self.kind]["color"])
        p.save()
        p.setClipPath(body)
        p.fillRect(QRectF(0, 0, self.W, 26), color)
        p.restore()

        f = QFont(p.font())
        f.setPointSize(8)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(contrast_text(color.name())))
        p.drawText(QRectF(12, 0, 110, 26), int(Qt.AlignVCenter | Qt.AlignLeft),
                   QFontMetrics(f).elidedText((self.label or BLOCKS[self.kind]["label"]).upper(),
                                              Qt.ElideRight, 108))
        comment = str(self.params.get("comment", "")).strip()
        if comment:
            f.setBold(False)
            p.setFont(f)
            text = QFontMetrics(f).elidedText("# " + comment, Qt.ElideRight, self.W - 140)
            p.drawText(QRectF(122, 0, self.W - 134, 26), int(Qt.AlignVCenter | Qt.AlignRight), text)

        p.setPen(QColor(th["text"]))
        if self.kind == "code":
            mono = QFontDatabase.systemFont(QFontDatabase.FixedFont)
            mono.setPointSize(8)
            p.setFont(mono)
            lines = [ln for ln in self.params.get("code", "").splitlines() if ln.strip()]
            fm = QFontMetrics(mono)
            for i, ln in enumerate(lines[:3]):
                p.drawText(QRectF(12, 32 + i * 16, self.W - 24, 16), int(Qt.AlignVCenter | Qt.AlignLeft),
                           fm.elidedText(ln, Qt.ElideRight, self.W - 24))
            if len(lines) > 3:
                p.setPen(QColor(th["muted"]))
                p.drawText(QRectF(12, 32 + 3 * 16 - 2, self.W - 24, 14),
                           int(Qt.AlignVCenter | Qt.AlignLeft), "…")
        else:
            f.setPointSize(10)
            f.setBold(True)
            p.setFont(f)
            text = QFontMetrics(f).elidedText(summary(self.kind, self.params).replace("\n", " "),
                                              Qt.ElideRight, self.W - 24)
            p.drawText(QRectF(12, 32, self.W - 24, 24), int(Qt.AlignVCenter | Qt.AlignLeft), text)

        if len(self.out_ports) >= 2:
            f.setPointSize(8)
            f.setBold(True)
            p.setFont(f)
            for port in self.out_ports:
                p.setPen(QColor(PORT_COLORS.get(port.label, th["muted"])))
                p.drawText(QRectF(self.W - 90, port.pos().y() - 9, 76, 18),
                           int(Qt.AlignVCenter | Qt.AlignRight), port.label)


class Edge(QGraphicsPathItem):
    def __init__(self, src, dst):
        super().__init__()
        self.src, self.dst = src, dst  # src = port de sortie, dst = port d'entrée
        src.edges.append(self)
        dst.edges.append(self)
        self.setZValue(0)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setPen(QPen(Qt.black, 8))
        self.update_path()

    def update_path(self):
        a, b = self.src.scenePos(), self.dst.scenePos()
        path = bezier(a, b)
        path.moveTo(b + QPointF(-12, -6))
        path.lineTo(b)
        path.lineTo(b + QPointF(-12, 6))
        self.setPath(path)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(16)
        return stroker.createStroke(self.path())

    def paint(self, p, option, widget=None):
        th = self.scene().theme
        p.setRenderHint(QPainter.Antialiasing)
        if self.isSelected():
            pen = QPen(QColor(th["accent"]), 3.6)
        elif self.src.label in PORT_COLORS:
            pen = QPen(QColor(PORT_COLORS[self.src.label]), 2.6)
        else:
            pen = QPen(QColor(th["muted"]), 2.4)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(self.path())


def main_start(nodes):
    starts = sorted((n for n in nodes if n.kind == "start"), key=lambda n: n.id)
    return starts[0] if starts else None


def reachable_from(node):
    seen, stack = set(), [node]
    while stack:
        n = stack.pop()
        if n is None or n in seen:
            continue
        seen.add(n)
        for port in n.out_ports:
            for e in port.edges:
                stack.append(e.dst.node)
    return seen


# =========================================================================== #
#  Coloration syntaxique et éditeur de code
# =========================================================================== #
KEYWORDS = ("and as assert async await break class continue def del elif else except False "
            "finally for from global if import in is lambda None nonlocal not or pass raise "
            "return True try while with yield").split()
BUILTINS = ("print input range len int float str list dict set tuple open sum min max abs "
            "round sorted enumerate zip map filter type isinstance bool").split()


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document, dark=True):
        super().__init__(document)
        self.rules = []
        self.set_dark(dark, rehighlight=False)

    def set_dark(self, dark, rehighlight=True):
        def fmt(color, bold=False, italic=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            f.setFontItalic(italic)
            return f

        c = (dict(kw="#c792ea", bi="#82aaff", st="#c3e88d", nu="#f78c6c", co="#7f8aa3") if dark
             else dict(kw="#7c3aed", bi="#2563eb", st="#15803d", nu="#c2410c", co="#8a93a6"))
        self.rules = [
            (re.compile(r"\b\d+(?:\.\d+)?\b"), fmt(c["nu"])),
            (re.compile(r"\b(?:" + "|".join(KEYWORDS) + r")\b"), fmt(c["kw"], bold=True)),
            (re.compile(r"\b(?:" + "|".join(BUILTINS) + r")\b"), fmt(c["bi"])),
            (re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\''), fmt(c["st"])),
            (re.compile(r"#[^\n]*"), fmt(c["co"], italic=True)),
        ]
        if rehighlight:
            self.rehighlight()

    def highlightBlock(self, text):
        for rx, f in self.rules:
            for m in rx.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), f)


class CodeEdit(QPlainTextEdit):
    """Zone de code : police fixe, Tab = 4 espaces, indentation automatique."""

    def __init__(self, text="", read_only=False):
        super().__init__()
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        font.setPointSize(10)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setReadOnly(read_only)
        if text:
            self.setPlainText(text)

    def keyPressEvent(self, ev):
        if not self.isReadOnly():
            if ev.key() == Qt.Key_Tab:
                self.insertPlainText("    ")
                return
            if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
                cur = self.textCursor()
                line = cur.block().text()[:cur.positionInBlock()]
                indent = len(line) - len(line.lstrip(" "))
                if line.rstrip().endswith(":"):
                    indent += 4
                super().keyPressEvent(ev)
                self.insertPlainText(" " * indent)
                return
        super().keyPressEvent(ev)


class DocTab(CodeEdit):
    """Onglet d'édition d'un document texte du projet."""
    dirty_changed = Signal(object)

    def __init__(self, path, text):
        super().__init__(text)
        self.path = Path(path)
        self.name = self.path.name
        self.dirty = False
        self.document().setModified(False)
        self.document().modificationChanged.connect(self._on_mod)

    def _on_mod(self, modified):
        self.dirty = modified
        self.dirty_changed.emit(self)


# =========================================================================== #
#  Scène, vue, onglet de programme
# =========================================================================== #
class NodeScene(QGraphicsScene):
    GRID = 20
    graph_changed = Signal()
    moved = Signal()
    message = Signal(str)

    def __init__(self, theme):
        super().__init__()
        self.theme = theme
        self.snap = True
        self.next_id = 1
        self.drag_port = None
        self.temp = None
        self.setSceneRect(-6000, -6000, 12000, 12000)
        self.graph_changed.connect(self.update_reachability)

    def nodes(self):
        return [i for i in self.items() if isinstance(i, Node)]

    def edges(self):
        return [i for i in self.items() if isinstance(i, Edge)]

    def drawBackground(self, p, rect):
        th = self.theme
        p.fillRect(rect, QColor(th["bg"]))
        g = self.GRID
        minor, major = QColor(th["border"]), QColor(th["border"])
        minor.setAlpha(70)
        major.setAlpha(160)
        draw_minor = rect.width() / g < 300
        x = int(rect.left() // g) * g
        while x < rect.right():
            if (x // g) % 5 == 0:
                p.setPen(QPen(major, 0))
                p.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
            elif draw_minor:
                p.setPen(QPen(minor, 0))
                p.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
            x += g
        y = int(rect.top() // g) * g
        while y < rect.bottom():
            if (y // g) % 5 == 0:
                p.setPen(QPen(major, 0))
                p.drawLine(QLineF(rect.left(), y, rect.right(), y))
            elif draw_minor:
                p.setPen(QPen(minor, 0))
                p.drawLine(QLineF(rect.left(), y, rect.right(), y))
            y += g

    def create_node(self, kind, params, pos, node_id=None, label=None, color=None):
        node = Node(kind, params, node_id or self.next_id, label, color)
        self.next_id = max(self.next_id, node.id) + 1
        self.addItem(node)
        node.setPos(pos)
        return node

    def add_edge(self, out_port, in_port):
        edge = Edge(out_port, in_port)
        self.addItem(edge)
        return edge

    def remove_edge(self, edge):
        if edge in edge.src.edges:
            edge.src.edges.remove(edge)
        if edge in edge.dst.edges:
            edge.dst.edges.remove(edge)
        if edge.scene() is self:
            self.removeItem(edge)

    def try_connect(self, a, b):
        if a.is_output == b.is_output:
            self.message.emit("Reliez une sortie (à droite) à une entrée (à gauche).")
            return
        out, inp = (a, b) if a.is_output else (b, a)
        if out.node is inp.node:
            self.message.emit("Un bloc ne peut pas être relié à lui-même.")
        elif out.edges and out.edges[0].dst is inp:
            self.message.emit("Ces blocs sont déjà reliés.")
        elif out.node in reachable_from(inp.node):
            self.message.emit("Liaison refusée : elle créerait une boucle (utilisez « Répéter »).")
        else:
            for old in list(out.edges):  # une sortie = un seul chemin : on remplace
                self.remove_edge(old)
            self.add_edge(out, inp)
            self.graph_changed.emit()

    def update_reachability(self):
        nodes = self.nodes()
        start = main_start(nodes)
        reach = reachable_from(start) if start else set()
        for n in nodes:
            n.setOpacity(1.0 if (start is None or n in reach) else 0.5)

    def port_at(self, pos):
        for it in self.items(pos):
            if isinstance(it, Port):
                return it
        return None

    def update_temp(self, pos):
        a = self.drag_port.scenePos()
        self.temp.setPath(bezier(a, pos) if self.drag_port.is_output else bezier(pos, a))

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            port = self.port_at(ev.scenePos())
            if port is not None:
                self.drag_port = port
                self.temp = QGraphicsPathItem()
                self.temp.setPen(QPen(QColor(self.theme["accent"]), 2.4, Qt.DashLine))
                self.temp.setZValue(5)
                self.addItem(self.temp)
                self.update_temp(ev.scenePos())
                ev.accept()
                return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self.drag_port is not None:
            self.update_temp(ev.scenePos())
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self.drag_port is not None:
            src, self.drag_port = self.drag_port, None
            self.removeItem(self.temp)
            self.temp = None
            target = None
            for it in self.items(ev.scenePos()):
                if isinstance(it, Port):
                    target = it
                    break
                if isinstance(it, Node):  # lâché sur le corps d'un bloc
                    if src.is_output:
                        target = it.in_port
                        if target is None:
                            self.message.emit("Le bloc « Début » n'a pas d'entrée.")
                    else:
                        target = next((p for p in it.out_ports if not p.edges),
                                      it.out_ports[0] if it.out_ports else None)
                    break
            if target is not None and target is not src:
                self.try_connect(src, target)
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def to_dict(self):
        nodes = sorted(self.nodes(), key=lambda n: n.id)
        return {
            "version": 2,
            "nodes": [dict(id=n.id, kind=n.kind, params=dict(n.params), label=n.label, color=n.color,
                           x=n.pos().x(), y=n.pos().y()) for n in nodes],
            "edges": [[e.src.node.id, e.src.index, e.dst.node.id] for e in self.edges()],
        }

    def from_dict(self, data):
        self.clear()
        self.next_id = 1
        by_id = {}
        for d in data.get("nodes", []):
            if d.get("kind") not in BLOCKS:
                continue
            by_id[d["id"]] = self.create_node(
                d["kind"], d.get("params", {}), QPointF(float(d.get("x", 0)), float(d.get("y", 0))),
                int(d["id"]), d.get("label"), d.get("color"))
        for a, idx, b in data.get("edges", []):
            if a in by_id and b in by_id and by_id[b].in_port is not None:
                src_node = by_id[a]
                if idx < len(src_node.out_ports) and src_node not in reachable_from(by_id[b]):
                    self.add_edge(src_node.out_ports[idx], by_id[b].in_port)
        self.graph_changed.emit()


class NodeView(QGraphicsView):
    node_double_clicked = Signal(object)
    block_dropped = Signal(str, QPointF)

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setAcceptDrops(True)
        self._pan = None

    def wheelEvent(self, ev):
        factor = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        if 0.2 <= self.transform().m11() * factor <= 3.0:
            self.scale(factor, factor)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MiddleButton:
            self._pan = ev.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._pan is not None:
            cur = ev.position().toPoint()
            d = cur - self._pan
            self._pan = cur
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - d.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - d.y())
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MiddleButton and self._pan is not None:
            self._pan = None
            self.unsetCursor()
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        node = find_node(self.itemAt(ev.position().toPoint()))
        if node is not None:
            self.node_double_clicked.emit(node)
            ev.accept()
            return
        super().mouseDoubleClickEvent(ev)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasText():
            ev.acceptProposedAction()
        else:
            ev.ignore()

    def dragMoveEvent(self, ev):
        if ev.mimeData().hasText():
            ev.acceptProposedAction()
        else:
            ev.ignore()

    def dropEvent(self, ev):
        text = ev.mimeData().text()
        pos = self.mapToScene(ev.position().toPoint())
        ev.acceptProposedAction()
        self.block_dropped.emit(text, pos)


class ProgramTab(QWidget):
    """Un onglet = un programme (une scène de blocs)."""

    def __init__(self, theme, name, path):
        super().__init__()
        self.name, self.path, self.dirty = name, path, False
        self.scene = NodeScene(theme)
        self.view = NodeView(self.scene)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)


class DragTree(QTreeWidget):
    """Arbre dont les éléments peuvent être glissés vers la zone de travail (copie)."""

    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setIconSize(QSize(18, 18))
        self.setIndentation(16)
        self.setAnimated(True)

    def mimeData(self, items):
        md = QMimeData()
        if items:
            md.setText(items[0].data(0, Qt.UserRole) or "")
        return md

    def startDrag(self, supportedActions):
        super().startDrag(Qt.CopyAction)  # copie : l'élément reste dans l'arbre


# =========================================================================== #
#  Dialogues
# =========================================================================== #
def is_dark():
    return QApplication.palette().color(QPalette.Base).lightness() < 128


class BlockDialog(QDialog):
    def __init__(self, parent, kind, params, label, docs, progs):
        super().__init__(parent)
        self.setWindowTitle(f"Modifier le bloc — {label}")
        self.widgets = {}
        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)
        for field in FIELDS.get(kind, []):
            key, text, ftype = field[:3]
            value = str(params.get(key, DEFAULTS.get(kind, {}).get(key, "")))
            if ftype == "code":
                w = CodeEdit(value)
                w.setMinimumSize(560, 260)
                w._hl = PythonHighlighter(w.document(), dark=is_dark())
            elif ftype in ("doc", "prog", "lib", "choice"):
                w = QComboBox()
                w.setEditable(ftype != "choice")
                w.addItems({"doc": docs, "prog": progs, "lib": COMMON_LIBS,
                            "choice": field[3] if len(field) > 3 else []}[ftype])
                w.setCurrentText(value)
                w.setMinimumWidth(400)
            else:
                w = QLineEdit(value)
                w.setMinimumWidth(400)
            self.widgets[key] = w
            form.addRow(text, w)
        self.comment = QLineEdit(str(params.get("comment", "")))
        self.comment.setPlaceholderText("Optionnel : ajouté en commentaire dans le code")
        form.addRow("Commentaire", self.comment)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Ok).setText("Valider")
        box.button(QDialogButtonBox.Cancel).setText("Annuler")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        form.addRow(box)

    def values(self):
        out = {}
        for key, w in self.widgets.items():
            if isinstance(w, QPlainTextEdit):
                out[key] = w.toPlainText()
            elif isinstance(w, QComboBox):
                out[key] = w.currentText()
            else:
                out[key] = w.text()
        out["comment"] = self.comment.text()
        return out


class TemplateDialog(QDialog):
    def __init__(self, parent, name="", code="", color="#10b981", folder=DEFAULT_FOLDER, folders=None):
        super().__init__(parent)
        self.setWindowTitle("Modèle de bloc personnalisé")
        self.color = color
        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)
        self.name = QLineEdit(name)
        self.name.setPlaceholderText("Ex : Lancer un dé")
        self.folder = QComboBox()
        self.folder.setEditable(True)
        self.folder.addItems(folders or [DEFAULT_FOLDER])
        self.folder.setCurrentText(folder)
        self.code = CodeEdit(code or "# Votre code Python ici\n")
        self.code.setMinimumSize(560, 260)
        self._hl = PythonHighlighter(self.code.document(), dark=is_dark())
        self.color_btn = QPushButton("Choisir la couleur")
        self.color_btn.clicked.connect(self.pick_color)
        self.refresh_color()
        form.addRow("Nom du bloc", self.name)
        form.addRow("Dossier de rangement", self.folder)
        form.addRow("Couleur", self.color_btn)
        form.addRow("Code Python", self.code)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Ok).setText("Enregistrer")
        box.button(QDialogButtonBox.Cancel).setText("Annuler")
        box.accepted.connect(self.validate)
        box.rejected.connect(self.reject)
        form.addRow(box)

    def refresh_color(self):
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {self.color}; color: {contrast_text(self.color)}; }}")

    def pick_color(self):
        c = QColorDialog.getColor(QColor(self.color), self)
        if c.isValid():
            self.color = c.name()
            self.refresh_color()

    def validate(self):
        if not self.name.text().strip():
            self.name.setPlaceholderText("Le nom est obligatoire")
            self.name.setStyleSheet("border: 1px solid #e74c3c;")
            return
        self.accept()

    def values(self):
        return {"name": self.name.text().strip(), "code": self.code.toPlainText(), "color": self.color,
                "folder": self.folder.currentText().strip() or DEFAULT_FOLDER}


class LibraryDialog(QDialog):
    """Liste les bibliothèques utilisées par le projet et permet de les installer (pip)."""

    def __init__(self, parent, modules):
        super().__init__(parent)
        self.setWindowTitle("Bibliothèques du projet")
        self.resize(640, 440)
        self.packages = []
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Modules importés par vos programmes (blocs « Importer », code Python…) :"))
        self.table = QTableWidget(len(modules), 3)
        self.table.setHorizontalHeaderLabels(["Module", "Statut", "Paquet pip"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        missing = []
        colors = {"installée": "#22c55e", "intégrée": "#8b8fa8", "manquante": "#ef4444"}
        for r, mod in enumerate(modules):
            status = module_status(mod)
            pip = PIP_NAMES.get(mod, mod)
            for c, text in enumerate((mod, status, "" if status == "intégrée" else pip)):
                it = QTableWidgetItem(text)
                if c == 1:
                    it.setForeground(QColor(colors[status]))
                self.table.setItem(r, c, it)
            if status == "manquante":
                missing.append(pip)
        lay.addWidget(self.table)
        if not modules:
            lay.addWidget(QLabel("Aucune bibliothèque utilisée pour l'instant."))
        row = QHBoxLayout()
        self.btn_missing = QPushButton(f"Installer les manquantes ({len(missing)})")
        self.btn_missing.setEnabled(bool(missing))
        self.btn_missing.clicked.connect(lambda: self.finish(missing))
        row.addWidget(self.btn_missing)
        row.addStretch()
        lay.addLayout(row)
        row2 = QHBoxLayout()
        self.custom = QLineEdit()
        self.custom.setPlaceholderText("Autre paquet à installer (ex : requests numpy)")
        b_custom = QPushButton("Installer")
        b_custom.clicked.connect(lambda: self.finish(self.custom.text().split()))
        row2.addWidget(self.custom)
        row2.addWidget(b_custom)
        lay.addLayout(row2)
        close = QPushButton("Fermer")
        close.setObjectName("Secondary")
        close.clicked.connect(self.reject)
        lay.addWidget(close)

    def finish(self, packages):
        if packages:
            self.packages = packages
            self.accept()


# =========================================================================== #
#  Fenêtre principale
# =========================================================================== #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("DemoPySide", "EditeurCodeBlocsV2")
        self.theme_name = self.settings.value("theme", "Sombre", type=str)
        if self.theme_name not in THEMES:
            self.theme_name = "Sombre"
        self.templates = self.load_templates()
        self.user_folders = self.load_folders()
        self.collapsed = set()
        self.ws = None
        self.manifest = {"main": None}
        self.proc = None
        self.run_tmp = None
        self.last_code, self.code_ok = "", True
        self.last_prog = None
        self.spawn_count = 0
        self.untitled_count = 0
        self.highlighters = []

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.setCentralWidget(self.tabs)

        self.build_explorer_dock()
        self.build_palette_dock()
        self.build_code_dock()
        self.build_console_dock()
        self.build_actions()

        self.setWindowTitle("Éditeur de code à blocs")
        self.resize(1600, 920)
        self.apply_theme()
        self.refresh_explorer()

        last = self.settings.value("workspace", "", type=str)
        if last and (Path(last) / "programmes").is_dir():
            self.open_workspace(Path(last))
        else:
            self.open_untitled(example_graph())

    # ------------------------------------------------ onglet courant
    @property
    def tab(self):
        w = self.tabs.currentWidget()
        if isinstance(w, ProgramTab):
            return w
        lp = self.last_prog
        return lp if (lp is not None and self.tabs.indexOf(lp) >= 0) else None

    def need_program(self):
        t = self.tab
        if t is None:
            self.statusBar().showMessage("Ouvrez ou créez d'abord un programme.", 5000)
        return t

    def msg(self, text, ms=6000):
        self.statusBar().showMessage(text, ms)

    # --------------------------------------------------------------- thème
    def theme_dict(self):
        t = dict(THEMES[self.theme_name])
        t["accent_text"] = contrast_text(t["accent"])
        t["accent_hover"] = QColor(t["accent"]).lighter(115).name()
        return t

    def apply_theme(self):
        t = self.theme_dict()
        pal = QPalette()
        for role, key in ((QPalette.Window, "bg"), (QPalette.WindowText, "text"),
                          (QPalette.Base, "surface"), (QPalette.AlternateBase, "surface2"),
                          (QPalette.Text, "text"), (QPalette.Button, "surface2"),
                          (QPalette.ButtonText, "text"), (QPalette.Highlight, "accent"),
                          (QPalette.HighlightedText, "accent_text"), (QPalette.Mid, "border"),
                          (QPalette.ToolTipBase, "surface2"), (QPalette.ToolTipText, "text"),
                          (QPalette.PlaceholderText, "muted")):
            pal.setColor(role, QColor(t[key]))
        app = QApplication.instance()
        app.setPalette(pal)
        app.setStyleSheet(f"""
QWidget {{ color: {t['text']}; font-family: "Segoe UI", Arial, sans-serif; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {t['bg']}; }}
QLabel {{ background: transparent; }}
QToolBar {{ background: {t['surface']}; border: none; border-bottom: 1px solid {t['border']}; spacing: 6px; padding: 5px 8px; }}
QToolButton {{ background: {t['surface2']}; border: 1px solid {t['border']}; border-radius: 8px; padding: 6px 12px; }}
QToolButton:hover {{ border: 1px solid {t['accent']}; }}
QToolButton:checked {{ background: {t['accent']}; color: {t['accent_text']}; }}
QPushButton {{ background: {t['accent']}; color: {t['accent_text']}; border: none; border-radius: 8px; padding: 7px 16px; font-weight: 600; }}
QPushButton:hover {{ background: {t['accent_hover']}; }}
QPushButton:disabled {{ background: {t['surface2']}; color: {t['muted']}; }}
QPushButton#Secondary {{ background: {t['surface2']}; color: {t['text']}; border: 1px solid {t['border']}; }}
QLineEdit, QComboBox {{ background: {t['surface2']}; border: 1px solid {t['border']}; border-radius: 8px; padding: 6px 10px; selection-background-color: {t['accent']}; }}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {t['accent']}; }}
QPlainTextEdit {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 8px; padding: 6px; selection-background-color: {t['accent']}; selection-color: {t['accent_text']}; }}
QTreeWidget {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 10px; outline: 0; }}
QTreeWidget::item {{ padding: 5px 6px; border-radius: 6px; }}
QTreeWidget::item:selected {{ background: {t['accent']}; color: {t['accent_text']}; }}
QTreeWidget::item:hover:!selected {{ background: {t['surface2']}; }}
QTableWidget {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 8px; gridline-color: {t['border']}; }}
QHeaderView::section {{ background: {t['surface2']}; padding: 6px; border: none; font-weight: 600; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 8px 16px; color: {t['muted']}; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {t['text']}; border-bottom: 2px solid {t['accent']}; }}
QTabBar::tab:hover:!selected {{ color: {t['text']}; }}
QComboBox QAbstractItemView {{ background: {t['surface']}; border: 1px solid {t['border']}; selection-background-color: {t['accent']}; selection-color: {t['accent_text']}; }}
QMenuBar {{ background: {t['surface']}; }}
QMenuBar::item {{ padding: 6px 12px; background: transparent; }}
QMenuBar::item:selected {{ background: {t['surface2']}; border-radius: 6px; }}
QMenu {{ background: {t['surface']}; border: 1px solid {t['border']}; padding: 6px; }}
QMenu::item {{ padding: 7px 26px; border-radius: 6px; }}
QMenu::item:selected {{ background: {t['accent']}; color: {t['accent_text']}; }}
QMenu::separator {{ height: 1px; background: {t['border']}; margin: 5px 8px; }}
QStatusBar {{ background: {t['surface']}; color: {t['muted']}; border-top: 1px solid {t['border']}; }}
QDockWidget::title {{ background: {t['surface']}; padding: 8px; border-bottom: 1px solid {t['border']}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t['border']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QToolTip {{ background: {t['surface2']}; color: {t['text']}; border: 1px solid {t['border']}; padding: 5px; }}
""")
        dark = QColor(t["surface"]).lightness() < 128
        for hl in self.highlighters:
            hl.set_dark(dark)
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, ProgramTab):
                w.scene.theme = t
                w.scene.update()
                w.view.viewport().update()

    def set_theme(self, name):
        self.theme_name = name
        self.settings.setValue("theme", name)
        self.apply_theme()

    # ---------------------------------------------------------------- docks
    def build_explorer_dock(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        self.ws_label = QLabel("Aucun projet ouvert")
        f = self.ws_label.font()
        f.setBold(True)
        self.ws_label.setFont(f)
        self.explorer = DragTree()
        self.explorer.itemDoubleClicked.connect(self.explorer_open)
        self.explorer.setContextMenuPolicy(Qt.CustomContextMenu)
        self.explorer.customContextMenuRequested.connect(self.explorer_menu)
        row = QHBoxLayout()
        b1 = QPushButton("＋ Programme")
        b1.setObjectName("Secondary")
        b1.clicked.connect(lambda: self.new_program())
        b2 = QPushButton("＋ Document")
        b2.setObjectName("Secondary")
        b2.clicked.connect(lambda: self.new_doc("documents"))
        row.addWidget(b1)
        row.addWidget(b2)
        lay.addWidget(self.ws_label)
        lay.addWidget(self.explorer)
        lay.addLayout(row)
        self.explorer_dock = QDockWidget("Projet", self)
        self.explorer_dock.setWidget(box)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.explorer_dock)

    def build_palette_dock(self):
        self.palette_tree = DragTree()
        self.palette_tree.itemDoubleClicked.connect(self.palette_activate)
        self.palette_tree.itemCollapsed.connect(lambda it: self.collapsed.add(it.text(0)))
        self.palette_tree.itemExpanded.connect(lambda it: self.collapsed.discard(it.text(0)))
        self.palette_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.palette_tree.customContextMenuRequested.connect(self.palette_menu)
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        hint = QLabel("Double-clic ou glisser un bloc vers la zone de travail.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")
        lay.addWidget(hint)
        lay.addWidget(self.palette_tree)
        row = QHBoxLayout()
        b1 = QPushButton("＋ Modèle de bloc")
        b1.clicked.connect(lambda: self.new_template())
        b2 = QPushButton("＋ Dossier")
        b2.setObjectName("Secondary")
        b2.clicked.connect(lambda: self.new_user_folder())
        row.addWidget(b1)
        row.addWidget(b2)
        lay.addLayout(row)
        self.palette_dock = QDockWidget("Blocs", self)
        self.palette_dock.setWidget(box)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.palette_dock)
        self.splitDockWidget(self.explorer_dock, self.palette_dock, Qt.Vertical)
        self.resizeDocks([self.explorer_dock, self.palette_dock], [320, 520], Qt.Vertical)
        self.resizeDocks([self.explorer_dock], [290], Qt.Horizontal)
        self.refresh_palette()

    def build_code_dock(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        self.code_status = QLabel()
        self.code_status.setWordWrap(True)
        self.code_view = CodeEdit(read_only=True)
        self.highlighters.append(PythonHighlighter(self.code_view.document()))
        row = QHBoxLayout()
        b_copy = QPushButton("Copier")
        b_copy.setObjectName("Secondary")
        b_copy.clicked.connect(self.copy_code)
        b_export = QPushButton("Exporter .py")
        b_export.clicked.connect(lambda: self.export_py())
        row.addWidget(b_copy)
        row.addWidget(b_export)
        lay.addWidget(self.code_status)
        lay.addWidget(self.code_view)
        lay.addLayout(row)
        self.code_dock = QDockWidget("Code Python généré", self)
        self.code_dock.setWidget(box)
        self.addDockWidget(Qt.RightDockWidgetArea, self.code_dock)
        self.resizeDocks([self.code_dock], [470], Qt.Horizontal)

    def build_console_dock(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        self.console = CodeEdit(read_only=True)
        self.stdin = QLineEdit()
        self.stdin.setPlaceholderText("Réponse envoyée au programme (Entrée) — pour les blocs « Saisie »")
        self.stdin.returnPressed.connect(self.send_input)
        lay.addWidget(self.console)
        lay.addWidget(self.stdin)
        self.console_dock = QDockWidget("Console", self)
        self.console_dock.setWidget(box)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.console_dock)
        self.resizeDocks([self.console_dock], [170], Qt.Vertical)
        self.append_console("La sortie du programme s'affichera ici (F5 pour exécuter).\n")

    def append_console(self, text):
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(text)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    # -------------------------------------------------------------- actions
    def act(self, text, slot, shortcut=None, checkable=False, checked=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if checkable:
            a.setCheckable(True)
            a.setChecked(checked)
            a.toggled.connect(slot)
        else:
            a.triggered.connect(lambda _=False, s=slot: s())
        return a

    def build_actions(self):
        A = self.act
        a_newproj = A("Nouveau projet…", self.new_project)
        a_openproj = A("Ouvrir un projet…", self.open_project, "Ctrl+O")
        a_newprog = A("Nouveau programme", self.new_program, "Ctrl+N")
        a_openprog = A("Ouvrir un programme (.json)…", self.open_program_file, "Ctrl+Shift+O")
        a_save = A("Enregistrer", self.save_current, "Ctrl+S")
        a_saveas = A("Enregistrer le programme sous…", self.save_as_current)
        a_saveall = A("Tout enregistrer", self.save_all, "Ctrl+Shift+S")
        a_quit = A("Quitter", self.close, "Ctrl+Q")
        a_dup = A("Dupliquer", self.duplicate_selected, "Ctrl+D")
        a_del = A("Supprimer la sélection", self.delete_selected, "Delete")
        a_all = A("Tout sélectionner", self.select_all, "Ctrl+A")
        a_run = A("▶  Exécuter", self.run_code, "F5")
        a_stop = A("■  Arrêter", self.stop_code, "Shift+F5")
        a_fit = A("Tout afficher", self.fit_current, "F")
        a_reset = A("Zoom 100 %", self.reset_zoom, "Ctrl+0")
        a_snap = A("Aimanter à la grille", self.set_snap, checkable=True, checked=True)
        a_doc = A("Nouveau document texte", lambda: self.new_doc("documents"))
        a_import = A("Importer des fichiers dans le projet…", lambda: self.import_files("documents"))
        a_main = A("Définir comme programme principal", self.set_main_current)
        a_refresh = A("Actualiser l'explorateur", self.refresh_explorer)
        a_libs = A("📚  Bibliothèques…", self.libraries_dialog)
        a_pip = A("Installer un paquet (pip)…", self.install_package)
        a_ex1 = A("Programme actuel (.py)…", self.export_py, "Ctrl+E")
        a_ex2 = A("Projet complet (dossier)…", self.export_project)
        a_ex3 = A("⇪  Tout en UN SEUL fichier (.py)…", self.export_bundle, "Ctrl+Shift+E")
        a_ex4 = A("Créer un exécutable (.exe)…", self.build_exe)
        for a in (a_openproj, a_newprog, a_openprog, a_save, a_saveall, a_dup, a_del, a_all, a_run,
                  a_stop, a_fit, a_reset, a_ex1, a_ex3):
            self.addAction(a)

        mb = self.menuBar()
        m = mb.addMenu("&Fichier")
        for a in (a_newproj, a_openproj):
            m.addAction(a)
        m.addSeparator()
        for a in (a_newprog, a_openprog, a_save, a_saveas, a_saveall):
            m.addAction(a)
        m.addSeparator()
        m.addAction(a_quit)
        m = mb.addMenu("&Projet")
        for a in (a_newprog, a_doc, a_import, a_main, a_refresh):
            m.addAction(a)
        m.addSeparator()
        m.addAction(a_libs)
        m.addAction(a_pip)
        m = mb.addMenu("E&xporter")
        for a in (a_ex1, a_ex2, a_ex3, a_ex4):
            m.addAction(a)
        m = mb.addMenu("&Édition")
        for a in (a_dup, a_del, a_all):
            m.addAction(a)
        m = mb.addMenu("E&xécution")
        m.addAction(a_run)
        m.addAction(a_stop)
        m = mb.addMenu("&Affichage")
        for a in (a_fit, a_reset):
            m.addAction(a)
        m.addSeparator()
        m.addAction(a_snap)
        m.addSeparator()
        for d in (self.explorer_dock, self.palette_dock, self.code_dock, self.console_dock):
            m.addAction(d.toggleViewAction())

        tb = QToolBar("Principal")
        tb.setMovable(False)
        self.addToolBar(tb)
        for a in (a_run, a_stop):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(a_save)
        tb.addAction(a_libs)
        tb.addAction(a_ex3)
        tb.addSeparator()
        tb.addAction(a_fit)
        tb.addAction(a_snap)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        tb.addWidget(QLabel("Thème :  "))
        combo = QComboBox()
        combo.addItems(THEMES)
        combo.setCurrentText(self.theme_name)
        combo.currentTextChanged.connect(self.set_theme)
        tb.addWidget(combo)
        self.msg("Fichier ▸ Nouveau projet… pour créer un dossier de travail · glissez les blocs "
                 "depuis la liste · F5 : exécuter", 12000)

    def set_snap(self, on):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, ProgramTab):
                w.scene.snap = on
        self.snap = on

    def reset_zoom(self):
        t = self.tab
        if t:
            t.view.resetTransform()

    # ------------------------------------------------- onglets / fichiers
    def open_untitled(self, data=None):
        self.untitled_count += 1
        return self.add_program_tab(f"sans titre {self.untitled_count}", None, data or blank_program())

    def add_program_tab(self, name, path, data):
        tab = ProgramTab(self.theme_dict(), name, path)
        tab.scene.snap = getattr(self, "snap", True)
        tab.scene.from_dict(data)
        tab.scene.message.connect(lambda m: self.msg(m))
        tab.scene.graph_changed.connect(lambda t=tab: self.on_graph_changed(t))
        tab.scene.moved.connect(lambda t=tab: self.set_dirty(t, True))
        tab.view.customContextMenuRequested.connect(lambda pos, t=tab: self.context_menu(t, pos))
        tab.view.node_double_clicked.connect(lambda node, t=tab: self.edit_node(t, node))
        tab.view.block_dropped.connect(lambda text, pos, t=tab: self.on_drop(t, text, pos))
        idx = self.tabs.addTab(tab, name)
        self.tabs.setCurrentIndex(idx)
        self.set_dirty(tab, False)
        QTimer.singleShot(0, lambda t=tab: self.fit_tab(t))
        return tab

    def set_dirty(self, w, value):
        w.dirty = value
        self.update_tab_title(w)

    def update_tab_title(self, w):
        i = self.tabs.indexOf(w)
        if i >= 0:
            self.tabs.setTabText(i, w.name + ("  ●" if w.dirty else ""))
            self.tabs.setTabToolTip(i, str(w.path) if w.path else "(pas encore enregistré)")

    def on_graph_changed(self, tab):
        self.set_dirty(tab, True)
        if tab is self.tab:
            self.refresh_code()

    def on_tab_changed(self, _i=0):
        w = self.tabs.currentWidget()
        if isinstance(w, ProgramTab):
            self.last_prog = w
        self.refresh_code()

    def fit_tab(self, tab):
        if self.tabs.indexOf(tab) < 0:
            return
        rect = tab.scene.itemsBoundingRect()
        if rect.isNull():
            return
        tab.view.fitInView(rect.adjusted(-60, -60, 60, 60), Qt.KeepAspectRatio)
        if tab.view.transform().m11() > 1.2:
            tab.view.resetTransform()
            tab.view.centerOn(rect.center())

    def fit_current(self):
        t = self.tab
        if t:
            self.fit_tab(t)

    def drop_tab(self, w):
        if self.last_prog is w:
            self.last_prog = None
        self.tabs.removeTab(self.tabs.indexOf(w))
        w.deleteLater()

    def close_tab(self, i):
        w = self.tabs.widget(i)
        if w is None:
            return True
        if getattr(w, "dirty", False):
            r = QMessageBox.question(
                self, "Enregistrer ?", f"« {w.name} » a été modifié.\nEnregistrer avant de fermer ?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Cancel:
                return False
            if r == QMessageBox.Save and not self.save_widget(w):
                return False
        self.drop_tab(w)
        if self.tabs.count() == 0:
            self.refresh_code()
        return True

    def close_all_tabs(self):
        while self.tabs.count():
            if not self.close_tab(0):
                return False
        return True

    def save_widget(self, w):
        if isinstance(w, ProgramTab):
            return self.save_tab(w)
        if isinstance(w, DocTab):
            return self.save_doc(w)
        return True

    def save_current(self):
        w = self.tabs.currentWidget()
        if w is not None:
            self.save_widget(w)

    def save_as_current(self):
        t = self.tab
        if t:
            self.save_tab(t, save_as=True)

    def save_all(self):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if getattr(w, "dirty", False):
                self.save_widget(w)

    def save_tab(self, tab, save_as=False):
        path = tab.path
        if path is None or save_as:
            default = (self.ws / "programmes" / f"{tab.name}.json") if self.ws else Path(f"{tab.name}.json")
            p, _ = QFileDialog.getSaveFileName(self, "Enregistrer le programme", str(default),
                                               "Programme (*.json)")
            if not p:
                return False
            path = Path(p)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(tab.scene.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            QMessageBox.critical(self, "Erreur", f"Enregistrement impossible :\n{e}")
            return False
        tab.path, tab.name = path, path.stem
        self.set_dirty(tab, False)
        self.refresh_explorer()
        self.refresh_code()
        self.msg(f"Programme enregistré : {path.name}", 4000)
        return True

    def save_doc(self, w):
        try:
            w.path.write_text(w.toPlainText(), encoding="utf-8")
        except OSError as e:
            QMessageBox.critical(self, "Erreur", f"Enregistrement impossible :\n{e}")
            return False
        w.document().setModified(False)
        self.msg(f"Document enregistré : {w.name}", 4000)
        return True

    def open_tab_for(self, path):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if getattr(w, "path", None) == path:
                return w
        return None

    def open_program_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Ouvrir un programme", str(self.ws or ""),
                                           "Programme (*.json)")
        if p:
            self.open_program_path(Path(p))

    def open_program_path(self, path):
        existing = self.open_tab_for(path)
        if existing:
            self.tabs.setCurrentWidget(existing)
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("format inattendu")
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Erreur", f"Fichier illisible :\n{e}")
            return
        self.add_program_tab(path.stem, path, data)

    def open_program(self, name):
        self.open_program_path(self.program_path(name))

    def open_doc(self, rel):
        path = self.ws / rel
        if path.suffix.lower() not in TEXT_EXT:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            return
        existing = self.open_tab_for(path)
        if existing:
            self.tabs.setCurrentWidget(existing)
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            QMessageBox.critical(self, "Erreur", f"Lecture impossible :\n{e}")
            return
        tab = DocTab(path, text)
        tab.dirty_changed.connect(self.update_tab_title)
        i = self.tabs.addTab(tab, tab.name)
        self.tabs.setTabToolTip(i, str(path))
        self.tabs.setCurrentIndex(i)

    # ------------------------------------------------------------- projet
    def program_path(self, name):
        return self.ws / "programmes" / f"{name}.json"

    def program_names(self):
        if not self.ws:
            return []
        return sorted(p.stem for p in (self.ws / "programmes").glob("*.json"))

    def doc_files(self):
        if not self.ws or not (self.ws / "documents").is_dir():
            return []
        return sorted(p.relative_to(self.ws).as_posix() for p in (self.ws / "documents").rglob("*")
                      if p.is_file())

    def name_map(self):
        return unique_py_names(self.program_names())

    def program_data(self, name):
        """Données d'un programme : version ouverte (même non enregistrée) ou fichier sur disque."""
        if self.ws:
            tab = self.open_tab_for(self.program_path(name))
            if isinstance(tab, ProgramTab):
                return tab.scene.to_dict()
            try:
                return json.loads(self.program_path(name).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
        t = self.tab
        return t.scene.to_dict() if (t is not None and t.name == name) else None

    def main_program_name(self):
        names = self.program_names()
        m = self.manifest.get("main")
        if m in names:
            return m
        return names[0] if names else None

    def save_manifest(self):
        if self.ws:
            try:
                (self.ws / "projet.json").write_text(
                    json.dumps({"version": 1, "main": self.manifest.get("main")}, indent=2),
                    encoding="utf-8")
            except OSError:
                pass

    def set_main(self, name):
        self.manifest["main"] = name
        self.save_manifest()
        self.refresh_explorer()
        self.msg(f"« {name} » est maintenant le programme principal.", 5000)

    def set_main_current(self):
        t = self.need_program()
        if t is None:
            return
        if not self.ws or t.name not in self.program_names():
            self.msg("Enregistrez d'abord ce programme dans un projet.", 5000)
            return
        self.set_main(t.name)

    def open_workspace(self, path):
        if not self.close_all_tabs():
            return False
        self.ws = Path(path)
        for sub in ("programmes", "documents", "sortie"):
            (self.ws / sub).mkdir(exist_ok=True)
        try:
            data = json.loads((self.ws / "projet.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        self.manifest = {"main": data.get("main") if isinstance(data, dict) else None}
        self.settings.setValue("workspace", str(self.ws))
        self.setWindowTitle(f"Éditeur de code à blocs — {self.ws.name}")
        if not self.program_names():
            self.program_path("principal").write_text(
                json.dumps(blank_program(), indent=2, ensure_ascii=False), encoding="utf-8")
        self.refresh_explorer()
        main = self.main_program_name()
        if main:
            self.open_program(main)
        return True

    def new_project(self):
        parent = QFileDialog.getExistingDirectory(self, "Dossier où créer le projet")
        if not parent:
            return
        name, ok = QInputDialog.getText(self, "Nouveau projet", "Nom du projet :", text="MonProjet")
        name = name.strip()
        if not ok or not name:
            return
        if re.search(r'[\\/:*?"<>|]', name):
            self.msg("Le nom contient un caractère interdit.")
            return
        root = Path(parent) / name
        if root.exists():
            QMessageBox.warning(self, "Nouveau projet", "Ce dossier existe déjà.")
            return
        try:
            sample_project(root)
        except OSError as e:
            QMessageBox.critical(self, "Erreur", f"Création impossible :\n{e}")
            return
        self.open_workspace(root)
        self.msg(f"Projet créé : {root}", 8000)

    def open_project(self):
        d = QFileDialog.getExistingDirectory(self, "Ouvrir un dossier de projet", str(self.ws or ""))
        if not d:
            return
        if not (Path(d) / "programmes").is_dir():
            if QMessageBox.question(self, "Ouvrir", "Ce dossier n'est pas encore un projet.\n"
                                    "Le transformer en projet (création des sous-dossiers) ?"
                                    ) != QMessageBox.Yes:
                return
        self.open_workspace(Path(d))

    # ---------------------------------------------------------- explorateur
    def refresh_explorer(self):
        tree = self.explorer
        tree.clear()
        st = self.style()
        if not self.ws:
            self.ws_label.setText("Aucun projet ouvert")
            it = QTreeWidgetItem(["Fichier ▸ Nouveau projet…"])
            it.setFlags(Qt.NoItemFlags)
            tree.addTopLevelItem(it)
            return
        self.ws_label.setText(f"📦  {self.ws.name}")
        main = self.main_program_name()

        def bold(it):
            f = it.font(0)
            f.setBold(True)
            it.setFont(0, f)

        leaf = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled
        root_p = QTreeWidgetItem(["Programmes"])
        root_p.setIcon(0, st.standardIcon(QStyle.SP_DirIcon))
        root_p.setData(0, Qt.UserRole, "root:prog")
        bold(root_p)
        tree.addTopLevelItem(root_p)
        for name in self.program_names():
            it = QTreeWidgetItem([("★ " if name == main else "") + name])
            it.setIcon(0, color_icon("#3b82f6"))
            it.setData(0, Qt.UserRole, f"prog:{name}")
            it.setFlags(leaf)
            root_p.addChild(it)

        def add_dir(parent_item, directory):
            entries = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            for p in entries:
                rel = p.relative_to(self.ws).as_posix()
                if p.is_dir():
                    d = QTreeWidgetItem([p.name])
                    d.setIcon(0, st.standardIcon(QStyle.SP_DirIcon))
                    d.setData(0, Qt.UserRole, f"dir:{rel}")
                    parent_item.addChild(d)
                    add_dir(d, p)
                else:
                    f = QTreeWidgetItem([p.name])
                    f.setIcon(0, st.standardIcon(QStyle.SP_FileIcon))
                    f.setData(0, Qt.UserRole, f"doc:{rel}")
                    f.setFlags(leaf)
                    parent_item.addChild(f)

        root_d = QTreeWidgetItem(["Documents"])
        root_d.setIcon(0, st.standardIcon(QStyle.SP_DirIcon))
        root_d.setData(0, Qt.UserRole, "dir:documents")
        bold(root_d)
        tree.addTopLevelItem(root_d)
        if (self.ws / "documents").is_dir():
            add_dir(root_d, self.ws / "documents")
        tree.expandAll()

    def explorer_open(self, item, _col=0):
        key = item.data(0, Qt.UserRole) or ""
        if key.startswith("prog:"):
            self.open_program(key[5:])
        elif key.startswith("doc:"):
            self.open_doc(key[4:])

    def explorer_menu(self, pos):
        item = self.explorer.itemAt(pos)
        key = (item.data(0, Qt.UserRole) or "") if item else ""
        menu = QMenu(self)

        def add(text, fn):
            menu.addAction(text).triggered.connect(lambda _=False, f=fn: f())

        if not self.ws:
            add("Nouveau projet…", self.new_project)
            add("Ouvrir un projet…", self.open_project)
        elif key.startswith("prog:"):
            name = key[5:]
            add("Ouvrir", lambda: self.open_program(name))
            add("Définir comme programme principal", lambda: self.set_main(name))
            menu.addSeparator()
            add("Renommer…", lambda: self.rename_program(name))
            add("Dupliquer", lambda: self.duplicate_program(name))
            add("Supprimer", lambda: self.delete_program(name))
        elif key.startswith("dir:"):
            rel = key[4:]
            add("Nouveau document texte…", lambda: self.new_doc(rel))
            add("Nouveau dossier…", lambda: self.new_folder(rel))
            add("Importer des fichiers…", lambda: self.import_files(rel))
            if rel != "documents":
                menu.addSeparator()
                add("Renommer le dossier…", lambda: self.rename_doc(rel))
                add("Supprimer le dossier", lambda: self.delete_doc(rel))
        elif key.startswith("doc:"):
            rel = key[4:]
            add("Ouvrir", lambda: self.open_doc(rel))
            t = self.tab
            if t is not None:
                menu.addSeparator()
                add("Ajouter un bloc « Lire »", lambda: self.add_block(
                    t, "readfile", self.next_free_pos(t), {"path": rel}))
                add("Ajouter un bloc « Écrire »", lambda: self.add_block(
                    t, "writefile", self.next_free_pos(t), {"path": rel}))
            menu.addSeparator()
            add("Renommer…", lambda: self.rename_doc(rel))
            add("Supprimer", lambda: self.delete_doc(rel))
        else:
            add("Nouveau programme…", self.new_program)
        menu.exec(self.explorer.viewport().mapToGlobal(pos))

    # -- programmes
    def valid_name(self, name):
        if not name or re.search(r'[\\/:*?"<>|]', name):
            self.msg("Nom vide ou contenant un caractère interdit (\\ / : * ? \" < > |).")
            return False
        return True

    def new_program(self):
        if not self.ws:
            self.open_untitled()
            self.msg("Programme libre créé. Créez un projet pour en gérer plusieurs.", 6000)
            return
        name, ok = QInputDialog.getText(self, "Nouveau programme", "Nom du programme :")
        name = name.strip()
        if not ok or not self.valid_name(name):
            return
        path = self.program_path(name)
        if path.exists():
            self.msg("Un programme porte déjà ce nom.")
            return
        path.write_text(json.dumps(blank_program(), indent=2, ensure_ascii=False), encoding="utf-8")
        self.refresh_explorer()
        self.open_program(name)

    def rename_program(self, old):
        new, ok = QInputDialog.getText(self, "Renommer", "Nouveau nom :", text=old)
        new = new.strip()
        if not ok or not new or new == old or not self.valid_name(new):
            return
        src, dst = self.program_path(old), self.program_path(new)
        if dst.exists():
            self.msg("Un programme porte déjà ce nom.")
            return
        try:
            src.rename(dst)
        except OSError as e:
            QMessageBox.critical(self, "Erreur", str(e))
            return
        tab = self.open_tab_for(src)
        if tab is not None:
            tab.path, tab.name = dst, new
            self.update_tab_title(tab)
        if self.manifest.get("main") == old:
            self.manifest["main"] = new
            self.save_manifest()
        self.retarget_calls(old, new)
        self.refresh_explorer()
        self.refresh_code()
        self.msg(f"Programme renommé ; les blocs « Appeler » ont été mis à jour.", 6000)

    def retarget_calls(self, old, new):
        for name in self.program_names():
            path = self.program_path(name)
            tab = self.open_tab_for(path)
            if isinstance(tab, ProgramTab):
                changed = False
                for n in tab.scene.nodes():
                    if n.kind == "call" and n.params.get("program") == old:
                        n.params["program"] = new
                        n.update()
                        changed = True
                if changed:
                    self.set_dirty(tab, True)
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            changed = False
            for d in data.get("nodes", []):
                if d.get("kind") == "call" and (d.get("params") or {}).get("program") == old:
                    d["params"]["program"] = new
                    changed = True
            if changed:
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def duplicate_program(self, name):
        new, i = f"{name}_copie", 2
        while self.program_path(new).exists():
            new = f"{name}_copie{i}"
            i += 1
        try:
            shutil.copy2(self.program_path(name), self.program_path(new))
        except OSError as e:
            QMessageBox.critical(self, "Erreur", str(e))
            return
        self.refresh_explorer()
        self.open_program(new)

    def delete_program(self, name):
        if QMessageBox.question(self, "Supprimer", f"Supprimer définitivement le programme « {name} » ?"
                                ) != QMessageBox.Yes:
            return
        path = self.program_path(name)
        tab = self.open_tab_for(path)
        if tab is not None:
            self.drop_tab(tab)
        try:
            path.unlink()
        except OSError as e:
            QMessageBox.critical(self, "Erreur", str(e))
        if self.manifest.get("main") == name:
            self.manifest["main"] = None
            self.save_manifest()
        self.refresh_explorer()
        self.refresh_code()

    # -- documents
    def new_doc(self, rel_dir="documents"):
        if not self.ws:
            self.msg("Créez ou ouvrez d'abord un projet.")
            return
        name, ok = QInputDialog.getText(self, "Nouveau document", "Nom du fichier :", text="notes.txt")
        name = name.strip()
        if not ok or not self.valid_name(name):
            return
        if "." not in name:
            name += ".txt"
        path = self.ws / rel_dir / name
        if path.exists():
            self.msg("Ce fichier existe déjà.")
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        except OSError as e:
            QMessageBox.critical(self, "Erreur", str(e))
            return
        self.refresh_explorer()
        self.open_doc(path.relative_to(self.ws).as_posix())

    def new_folder(self, rel_dir="documents"):
        name, ok = QInputDialog.getText(self, "Nouveau dossier", "Nom du dossier :")
        name = name.strip()
        if not ok or not self.valid_name(name):
            return
        try:
            (self.ws / rel_dir / name).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            QMessageBox.critical(self, "Erreur", str(e))
            return
        self.refresh_explorer()

    def import_files(self, rel_dir="documents"):
        if not self.ws:
            self.msg("Créez ou ouvrez d'abord un projet.")
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Importer des fichiers dans le projet")
        if not files:
            return
        dest = self.ws / rel_dir
        dest.mkdir(parents=True, exist_ok=True)
        for f in files:
            try:
                shutil.copy2(f, dest / Path(f).name)
            except OSError as e:
                QMessageBox.critical(self, "Erreur", f"{f}\n{e}")
        self.refresh_explorer()
        self.msg(f"{len(files)} fichier(s) importé(s).", 5000)

    def rename_doc(self, rel):
        old = self.ws / rel
        new, ok = QInputDialog.getText(self, "Renommer", "Nouveau nom :", text=old.name)
        new = new.strip()
        if not ok or not new or new == old.name or not self.valid_name(new):
            return
        dst = old.with_name(new)
        if dst.exists():
            self.msg("Ce nom est déjà pris.")
            return
        try:
            old.rename(dst)
        except OSError as e:
            QMessageBox.critical(self, "Erreur", str(e))
            return
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DocTab):
                try:
                    sub = w.path.relative_to(old)
                except ValueError:
                    continue
                w.path = dst / sub
                w.name = w.path.name
                self.update_tab_title(w)
        self.refresh_explorer()
        self.msg("Renommé. Pensez à mettre à jour les blocs qui utilisent ce chemin.", 7000)

    def delete_doc(self, rel):
        path = self.ws / rel
        if QMessageBox.question(self, "Supprimer", f"Supprimer « {path.name} » définitivement ?"
                                ) != QMessageBox.Yes:
            return
        for i in reversed(range(self.tabs.count())):
            w = self.tabs.widget(i)
            if isinstance(w, DocTab) and (w.path == path or path in w.path.parents):
                self.drop_tab(w)
        try:
            shutil.rmtree(path) if path.is_dir() else path.unlink()
        except OSError as e:
            QMessageBox.critical(self, "Erreur", str(e))
        self.refresh_explorer()

    # ------------------------------------------------ liste de blocs
    def load_templates(self):
        try:
            data = json.loads(self.settings.value("templates", "[]", type=str))
            out = []
            for t in data:
                if isinstance(t, dict) and {"name", "code", "color"} <= set(t):
                    t.setdefault("folder", DEFAULT_FOLDER)
                    out.append(t)
            return out
        except (ValueError, TypeError):
            return []

    def load_folders(self):
        folders = [DEFAULT_FOLDER]
        try:
            saved = json.loads(self.settings.value("user_folders", "[]", type=str))
        except (ValueError, TypeError):
            saved = []
        for f in list(saved) + [t["folder"] for t in self.templates]:
            if isinstance(f, str) and f and f not in folders:
                folders.append(f)
        return folders

    def save_templates(self):
        self.settings.setValue("templates", json.dumps(self.templates, ensure_ascii=False))
        self.settings.setValue("user_folders", json.dumps(self.user_folders, ensure_ascii=False))
        self.refresh_palette()

    def refresh_palette(self):
        tree = self.palette_tree
        tree.clear()
        st = self.style()
        leaf = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled

        def folder_item(name, user):
            it = QTreeWidgetItem([name])
            it.setIcon(0, st.standardIcon(QStyle.SP_DirIcon))
            it.setData(0, Qt.UserRole + 1, "user" if user else "builtin")
            f = it.font(0)
            f.setBold(True)
            it.setFont(0, f)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            tree.addTopLevelItem(it)
            return it

        for folder in FOLDER_ORDER:
            top = folder_item(folder, False)
            for kind, spec in BLOCKS.items():
                if spec["folder"] == folder:
                    child = QTreeWidgetItem([spec["label"]])
                    child.setIcon(0, color_icon(spec["color"]))
                    child.setData(0, Qt.UserRole, f"block:{kind}")
                    child.setFlags(leaf)
                    top.addChild(child)
        for fname in self.user_folders:
            top = folder_item(fname, True)
            count = 0
            for i, t in enumerate(self.templates):
                if t.get("folder", DEFAULT_FOLDER) == fname:
                    child = QTreeWidgetItem([t["name"]])
                    child.setIcon(0, color_icon(t["color"]))
                    child.setData(0, Qt.UserRole, f"tpl:{i}")
                    child.setFlags(leaf)
                    top.addChild(child)
                    count += 1
            if not count:
                empty = QTreeWidgetItem(["(vide)"])
                empty.setFlags(Qt.NoItemFlags)
                top.addChild(empty)
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            it.setExpanded(it.text(0) not in self.collapsed)

    def palette_activate(self, item, _col=0):
        key = item.data(0, Qt.UserRole)
        t = self.need_program()
        if key and t is not None:
            self.add_from_key(t, key, self.next_free_pos(t))

    def palette_menu(self, pos):
        item = self.palette_tree.itemAt(pos)
        key = (item.data(0, Qt.UserRole) or "") if item else ""
        menu = QMenu(self)

        def add(text, fn):
            menu.addAction(text).triggered.connect(lambda _=False, f=fn: f())

        if key.startswith("tpl:"):
            idx = int(key[4:])
            add("Modifier le modèle…", lambda: self.edit_template(idx))
            add("Déplacer vers un dossier…", lambda: self.move_template(idx))
            add("Supprimer le modèle", lambda: self.delete_template(idx))
            menu.addSeparator()
        elif item is not None and item.parent() is None and item.data(0, Qt.UserRole + 1) == "user":
            name = item.text(0)
            add("Nouveau modèle dans ce dossier…", lambda: self.new_template(folder=name))
            if name != DEFAULT_FOLDER:
                add("Renommer le dossier…", lambda: self.rename_user_folder(name))
                add("Supprimer le dossier", lambda: self.delete_user_folder(name))
            menu.addSeparator()
        add("Nouveau dossier de rangement…", self.new_user_folder)
        menu.exec(self.palette_tree.viewport().mapToGlobal(pos))

    def new_template(self, code="", folder=DEFAULT_FOLDER):
        dlg = TemplateDialog(self, code=code, folder=folder, folders=self.user_folders)
        if dlg.exec() == QDialog.Accepted:
            v = dlg.values()
            if v["folder"] not in self.user_folders:
                self.user_folders.append(v["folder"])
            self.templates.append(v)
            self.save_templates()
            self.msg(f"Modèle ajouté dans le dossier « {v['folder']} ».", 5000)

    def edit_template(self, idx):
        t = self.templates[idx]
        dlg = TemplateDialog(self, t["name"], t["code"], t["color"], t.get("folder", DEFAULT_FOLDER),
                             self.user_folders)
        if dlg.exec() == QDialog.Accepted:
            v = dlg.values()
            if v["folder"] not in self.user_folders:
                self.user_folders.append(v["folder"])
            self.templates[idx] = v
            self.save_templates()

    def delete_template(self, idx):
        if QMessageBox.question(self, "Supprimer", "Supprimer ce modèle ?") == QMessageBox.Yes:
            del self.templates[idx]
            self.save_templates()

    def move_template(self, idx):
        cur = self.templates[idx].get("folder", DEFAULT_FOLDER)
        folder, ok = QInputDialog.getItem(self, "Déplacer", "Dossier de destination :",
                                          self.user_folders, self.user_folders.index(cur)
                                          if cur in self.user_folders else 0, False)
        if ok:
            self.templates[idx]["folder"] = folder
            self.save_templates()

    def new_user_folder(self):
        name, ok = QInputDialog.getText(self, "Nouveau dossier", "Nom du dossier de rangement :")
        name = name.strip()
        if not ok or not name:
            return
        if name in self.user_folders or name in FOLDER_ORDER:
            self.msg("Ce dossier existe déjà.")
            return
        self.user_folders.append(name)
        self.save_templates()

    def rename_user_folder(self, old):
        new, ok = QInputDialog.getText(self, "Renommer le dossier", "Nouveau nom :", text=old)
        new = new.strip()
        if not ok or not new or new == old:
            return
        if new in self.user_folders or new in FOLDER_ORDER:
            self.msg("Ce dossier existe déjà.")
            return
        self.user_folders[self.user_folders.index(old)] = new
        for t in self.templates:
            if t.get("folder") == old:
                t["folder"] = new
        self.save_templates()

    def delete_user_folder(self, name):
        if QMessageBox.question(self, "Supprimer le dossier",
                                f"Supprimer « {name} » ?\nSes modèles seront déplacés dans « {DEFAULT_FOLDER} »."
                                ) != QMessageBox.Yes:
            return
        for t in self.templates:
            if t.get("folder") == name:
                t["folder"] = DEFAULT_FOLDER
        self.user_folders.remove(name)
        self.save_templates()

    # ------------------------------------------------------------ blocs
    def next_free_pos(self, tab):
        c = tab.view.mapToScene(tab.view.viewport().rect().center())
        off = (self.spawn_count % 6) * 40
        self.spawn_count += 1
        return QPointF(c.x() - Node.W / 2 + off, c.y() - 40 + off)

    def add_from_key(self, tab, key, pos):
        kind, _, rest = key.partition(":")
        if kind == "block" and rest in BLOCKS:
            self.add_block(tab, rest, pos)
        elif kind == "tpl":
            try:
                t = self.templates[int(rest)]
            except (ValueError, IndexError):
                return
            self.add_block(tab, "code", pos, {"code": t["code"]}, t["name"], t["color"])
        elif kind == "prog":
            self.add_block(tab, "call", pos, {"program": rest})
        elif kind == "doc":
            menu = QMenu(self)
            a1 = menu.addAction("Lire ce document")
            a2 = menu.addAction("Écrire dans ce document")
            chosen = menu.exec(QCursor.pos())
            if chosen is a1:
                self.add_block(tab, "readfile", pos, {"path": rest})
            elif chosen is a2:
                self.add_block(tab, "writefile", pos, {"path": rest})

    def on_drop(self, tab, text, pos):
        if text:
            self.add_from_key(tab, text, QPointF(pos.x() - Node.W / 2, pos.y() - 30))

    def add_block(self, tab, kind, pos, params=None, label=None, color=None):
        if kind == "start" and any(n.kind == "start" for n in tab.scene.nodes()):
            self.msg("Il n'y a qu'un seul bloc « Début » par programme.", 5000)
            return
        n = tab.scene.create_node(kind, params or {}, pos, None, label, color)
        tab.scene.clearSelection()
        n.setSelected(True)
        tab.scene.graph_changed.emit()

    def edit_node(self, tab, node):
        label = node.label or BLOCKS[node.kind]["label"]
        dlg = BlockDialog(self, node.kind, node.params, label, self.doc_files(), self.program_names())
        if dlg.exec() == QDialog.Accepted:
            node.params.update(dlg.values())
            node.update()
            tab.scene.graph_changed.emit()

    def delete_selected(self):
        t = self.need_program()
        if t is None:
            return
        sel = t.scene.selectedItems()
        nodes = [i for i in sel if isinstance(i, Node)]
        edges = {i for i in sel if isinstance(i, Edge)}
        for n in nodes:
            for port in n.all_ports():
                edges.update(port.edges)
        for e in list(edges):
            t.scene.remove_edge(e)
        for n in nodes:
            t.scene.removeItem(n)
        t.scene.graph_changed.emit()

    def duplicate_selected(self):
        t = self.need_program()
        if t is None:
            return
        nodes = [i for i in t.scene.selectedItems() if isinstance(i, Node) and i.kind != "start"]
        if not nodes:
            return
        mapping = {}
        t.scene.clearSelection()
        for n in nodes:
            c = t.scene.create_node(n.kind, dict(n.params), n.pos() + QPointF(40, 40), None,
                                    n.label, n.color)
            mapping[n] = c
            c.setSelected(True)
        for e in t.scene.edges():
            a, b = e.src.node, e.dst.node
            if a in mapping and b in mapping:
                t.scene.add_edge(mapping[a].out_ports[e.src.index], mapping[b].in_port)
        t.scene.graph_changed.emit()

    def select_all(self):
        t = self.tab
        if t:
            for n in t.scene.nodes():
                n.setSelected(True)

    def context_menu(self, tab, pos):
        item = tab.view.itemAt(pos)
        node = find_node(item)
        sp = tab.view.mapToScene(pos)
        menu = QMenu(self)
        if node is not None:
            if not node.isSelected():
                tab.scene.clearSelection()
                node.setSelected(True)
            menu.addAction("Modifier…").triggered.connect(
                lambda _=False, n=node: self.edit_node(tab, n))
            menu.addAction("Dupliquer").triggered.connect(lambda _=False: self.duplicate_selected())
            if node.kind == "code":
                menu.addAction("Enregistrer comme modèle…").triggered.connect(
                    lambda _=False, n=node: self.save_node_as_template(n))
            menu.addSeparator()
            menu.addAction("Supprimer").triggered.connect(lambda _=False: self.delete_selected())
        elif isinstance(item, Edge):
            tab.scene.clearSelection()
            item.setSelected(True)
            menu.addAction("Supprimer la liaison").triggered.connect(
                lambda _=False: self.delete_selected())
        else:
            at = QPointF(sp.x() - Node.W / 2, sp.y() - 30)
            for folder in FOLDER_ORDER:
                sub = menu.addMenu(folder)
                for kind, spec in BLOCKS.items():
                    if spec["folder"] == folder:
                        a = sub.addAction(color_icon(spec["color"]), spec["label"])
                        a.triggered.connect(
                            lambda _=False, k=f"block:{kind}", p=at: self.add_from_key(tab, k, p))
            if self.templates:
                sub = menu.addMenu("Mes modèles")
                for i, t in enumerate(self.templates):
                    a = sub.addAction(color_icon(t["color"]), f"{t['name']}  ({t.get('folder', DEFAULT_FOLDER)})")
                    a.triggered.connect(lambda _=False, k=f"tpl:{i}", p=at: self.add_from_key(tab, k, p))
        menu.exec(tab.view.viewport().mapToGlobal(pos))

    def save_node_as_template(self, node):
        name, ok = QInputDialog.getText(self, "Nouveau modèle", "Nom du modèle :",
                                        text=node.label or "Mon bloc")
        if ok and name.strip():
            self.templates.append({"name": name.strip(), "code": node.params.get("code", ""),
                                   "color": node.color or BLOCKS["code"]["color"],
                                   "folder": DEFAULT_FOLDER})
            self.save_templates()
            self.msg(f"Modèle « {name.strip()} » ajouté dans « {DEFAULT_FOLDER} ».", 5000)

    # ----------------------------------------------------- code généré
    def refresh_code(self):
        t = self.tab
        bar = self.code_view.verticalScrollBar()
        pos = bar.value()
        if t is None:
            self.code_view.setPlainText("# Aucun programme ouvert.")
            self.code_status.setText("")
            self.code_dock.setWindowTitle("Code Python généré")
            self.last_code, self.code_ok = "", False
            return
        names = self.name_map()
        code, res = module_source(t.name, t.scene.to_dict(), names)
        warnings = list(res["warnings"])
        for c in sorted(res["calls"]):
            if not self.ws:
                warnings.append("Les appels de programmes nécessitent un projet ouvert.")
                break
            if c not in names:
                warnings.append(f"Programme « {c} » introuvable dans le projet.")
        self.last_code = code
        self.code_view.setPlainText(code)
        bar.setValue(pos)
        try:
            compile(code, "<blocs>", "exec")
            self.code_ok = True
            status = "✓ Code valide"
        except SyntaxError as e:
            self.code_ok = False
            status = f"✗ Erreur de syntaxe ligne {e.lineno} : {e.msg}"
        if warnings:
            status += "\n⚠ " + "\n⚠ ".join(dict.fromkeys(warnings))
        self.code_status.setText(status)
        self.code_dock.setWindowTitle(f"Code Python généré — {t.name}")

    def copy_code(self):
        QApplication.clipboard().setText(self.last_code)
        self.msg("Code copié dans le presse-papiers", 4000)

    # ---------------------------------------------------------- exports
    def write_text_file(self, path, text):
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(text, encoding="utf-8")
            return True
        except OSError as e:
            QMessageBox.critical(self, "Erreur", f"Écriture impossible :\n{e}")
            return False

    def export_py(self):
        t = self.need_program()
        if t is None:
            return
        if not self.code_ok and QMessageBox.question(
                self, "Exporter", "Le code contient une erreur de syntaxe.\nL'exporter quand même ?"
        ) != QMessageBox.Yes:
            return
        names = self.name_map()
        default = (self.ws / "sortie" if self.ws else Path.cwd()) / f"{names.get(t.name) or py_name(t.name)}.py"
        path, _ = QFileDialog.getSaveFileName(self, "Exporter le programme", str(default), "Python (*.py)")
        if path and self.write_text_file(path, self.last_code):
            _, res = module_source(t.name, t.scene.to_dict(), names)
            extra = ""
            if any(c != t.name for c in res["calls"]):
                extra = "  (ce programme appelle d'autres programmes : utilisez « Tout en un seul fichier »)"
            self.msg(f"Exporté : {path}{extra}", 9000)

    def export_project(self):
        if not self.ws:
            self.msg("Cette action nécessite un projet ouvert.")
            return
        d = QFileDialog.getExistingDirectory(self, "Dossier d'export", str(self.ws / "sortie"))
        if not d:
            return
        names = self.name_map()
        count = 0
        for name in self.program_names():
            data = self.program_data(name)
            if data is None:
                continue
            code, _ = module_source(name, data, names)
            if self.write_text_file(Path(d) / f"{names[name]}.py", code):
                count += 1
        docs = self.ws / "documents"
        if docs.is_dir():
            try:
                shutil.copytree(docs, Path(d) / "documents", dirs_exist_ok=True)
            except OSError as e:
                QMessageBox.warning(self, "Documents", f"Copie des documents impossible :\n{e}")
        main = self.main_program_name()
        self.msg(f"{count} programme(s) exporté(s) dans {d}"
                 + (f" — lancez : python {names[main]}.py" if main else ""), 10000)

    def make_bundle(self):
        """Fusionne tout en un seul fichier. Retourne (code, avertissements, nom du principal) ou None."""
        if self.ws:
            main = self.main_program_name()
            if main is None:
                self.msg("Le projet ne contient aucun programme.")
                return None
            code, warns = compile_bundle(main, self.program_data, self.name_map())
            return code, warns, main
        t = self.need_program()
        if t is None:
            return None
        data = t.scene.to_dict()
        code, warns = compile_bundle(t.name, lambda n, d=data, tn=t.name: d if n == tn else None, {})
        return code, warns, t.name

    def export_bundle(self):
        r = self.make_bundle()
        if r is None:
            return
        code, warns, main = r
        try:
            compile(code, "<bundle>", "exec")
        except SyntaxError as e:
            if QMessageBox.question(self, "Exporter", f"Le code fusionné contient une erreur (ligne {e.lineno} : "
                                    f"{e.msg}).\nL'exporter quand même ?") != QMessageBox.Yes:
                return
        default = (self.ws / "sortie" / f"{py_name(self.ws.name)}_complet.py") if self.ws \
            else Path.cwd() / f"{py_name(main)}.py"
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le fichier unique", str(default), "Python (*.py)")
        if not path or not self.write_text_file(path, code):
            return
        if self.ws and (self.ws / "documents").is_dir() and any((self.ws / "documents").rglob("*")):
            if QMessageBox.question(self, "Documents", "Copier aussi le dossier « documents » à côté du fichier ?"
                                    ) == QMessageBox.Yes:
                try:
                    shutil.copytree(self.ws / "documents", Path(path).parent / "documents", dirs_exist_ok=True)
                except OSError as e:
                    QMessageBox.warning(self, "Documents", str(e))
        info = f"Fichier unique créé : {path}"
        if warns:
            info += f"  (⚠ {len(warns)} avertissement(s) : " + " | ".join(warns[:2]) + ")"
        self.msg(info, 12000)

    def build_exe(self):
        r = self.make_bundle()
        if r is None:
            return
        code, _warns, main = r
        if importlib.util.find_spec("PyInstaller") is None:
            if QMessageBox.question(self, "PyInstaller requis",
                                    "Pour créer un .exe, la bibliothèque PyInstaller doit être installée.\n"
                                    "L'installer maintenant ? (relancez ensuite cette action)") == QMessageBox.Yes:
                self.install_packages(["pyinstaller"])
            return
        if self.ws:
            dist = self.ws / "sortie" / "exe"
        else:
            d = QFileDialog.getExistingDirectory(self, "Dossier de sortie de l'exécutable")
            if not d:
                return
            dist = Path(d)
        dist.mkdir(parents=True, exist_ok=True)
        self.stop_code()
        tmp = tempfile.mkdtemp(prefix="blocs_exe_")
        script = Path(tmp) / f"{py_name(main)}.py"
        script.write_text(code, encoding="utf-8")
        args = ["-m", "PyInstaller", "--onefile", "--noconfirm", "--clean", "--name", py_name(main),
                "--distpath", str(dist), "--workpath", str(Path(tmp) / "build"), "--specpath", tmp,
                str(script)]

        def done(exit_code, d=dist):
            if exit_code == 0:
                if self.ws and (self.ws / "documents").is_dir():
                    try:
                        shutil.copytree(self.ws / "documents", d / "documents", dirs_exist_ok=True)
                    except OSError:
                        pass
                self.append_console(f"\n✓ Exécutable créé dans : {d}\n")
            else:
                self.append_console("\n✗ La création de l'exécutable a échoué.\n")

        self.start_process(sys.executable, args, cwd=tmp, on_done=done, tmp=tmp,
                           banner="⚙ Création de l'exécutable (peut prendre une minute)…")

    # --------------------------------------------------- bibliothèques
    def libraries_dialog(self):
        modules = set()
        for name in self.program_names():
            data = self.program_data(name)
            if data:
                modules |= generate_body(data, lambda n: "x")["modules"]
        t = self.tab
        if t is not None and (t.path is None or not self.ws):
            modules |= generate_body(t.scene.to_dict(), lambda n: "x")["modules"]
        dlg = LibraryDialog(self, sorted(modules))
        if dlg.exec() == QDialog.Accepted and dlg.packages:
            self.install_packages(dlg.packages)

    def install_package(self):
        text, ok = QInputDialog.getText(self, "Installer un paquet", "Nom(s) du/des paquet(s) pip :")
        if ok and text.strip():
            self.install_packages(text.split())

    def install_packages(self, pkgs):
        def done(code):
            self.append_console("\n✓ Installation terminée.\n" if code == 0
                                else "\n✗ L'installation a échoué (voir les messages ci-dessus).\n")
            self.refresh_code()

        self.start_process(sys.executable, ["-m", "pip", "install", *pkgs], on_done=done,
                           banner=f"⬇ Installation : {' '.join(pkgs)} …")

    # -------------------------------------------------------- exécution
    def run_code(self):
        t = self.need_program()
        if t is None:
            return
        self.stop_code()
        if not self.code_ok:
            QMessageBox.warning(self, "Exécution", "Le code contient une erreur de syntaxe : "
                                "corrigez-le avant de l'exécuter.")
            return
        names = self.name_map()
        files, warns, entry = compile_modules(t.name, t.scene.to_dict(), self.program_data, names)
        tmp = tempfile.mkdtemp(prefix="blocs_run_")
        for fn, code in files.items():
            (Path(tmp) / fn).write_text(code, encoding="utf-8")
        cwd = self.ws or Path.cwd()
        banner = f"▶ Exécution de « {t.name} »…"
        if warns:
            banner += "\n⚠ " + "\n⚠ ".join(dict.fromkeys(warns))
        self.start_process(sys.executable, ["-u", str(Path(tmp) / entry)], cwd=cwd,
                           env={"BLOCS_BASE": str(cwd)}, tmp=tmp, banner=banner)
        self.stdin.setFocus()

    def start_process(self, program, args, cwd=None, env=None, on_done=None, tmp=None, banner=""):
        self.stop_code()
        self.cleanup_run()
        self.run_tmp = tmp
        self.console.clear()
        self.append_console(banner + "\n")
        self.console_dock.show()
        proc = QProcess(self)
        self.proc = proc
        penv = QProcessEnvironment.systemEnvironment()
        penv.insert("PYTHONIOENCODING", "utf-8")
        for k, v in (env or {}).items():
            penv.insert(k, v)
        proc.setProcessEnvironment(penv)
        if cwd:
            proc.setWorkingDirectory(str(cwd))
        proc.readyReadStandardOutput.connect(
            lambda p=proc: self.append_console(p.readAllStandardOutput().data().decode("utf-8", "replace")))
        proc.readyReadStandardError.connect(
            lambda p=proc: self.append_console(p.readAllStandardError().data().decode("utf-8", "replace")))
        proc.finished.connect(lambda code, _s, cb=on_done: self.on_proc_finished(code, cb))
        proc.errorOccurred.connect(lambda err: self.append_console("\n[Impossible de lancer le processus]\n")
                                   if err == QProcess.ProcessError.FailedToStart else None)
        proc.start(program, args)

    def on_proc_finished(self, code, cb):
        self.append_console(f"\n■ Terminé (code {code})\n")
        self.cleanup_run()
        if cb:
            cb(code)

    def stop_code(self):
        if self.proc is not None and self.proc.state() != QProcess.ProcessState.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(1500)

    def cleanup_run(self):
        if self.run_tmp:
            shutil.rmtree(self.run_tmp, ignore_errors=True)
        self.run_tmp = None

    def send_input(self):
        text = self.stdin.text()
        self.stdin.clear()
        if self.proc is not None and self.proc.state() != QProcess.ProcessState.NotRunning:
            self.proc.write((text + "\n").encode("utf-8"))
            self.append_console(text + "\n")
        else:
            self.msg("Aucun programme en cours d'exécution (F5).", 4000)

    def closeEvent(self, event):
        if not self.close_all_tabs():
            event.ignore()
            return
        self.stop_code()
        self.cleanup_run()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
