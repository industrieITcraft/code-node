"""
Nouveautés :
  - Projet = un dossier contenant plusieurs programmes (blocs) et des documents
  - Explorateur de projet : programmes, documents (txt, csv, json…), dossiers
  - Un programme peut en appeler un autre (bloc « Appeler un programme »)
  - Blocs « Importer » (bibliothèques), « Lire / Écrire un fichier » (documents)
  - Gestionnaire de bibliothèques (installation avec pip)
  - Blocs rangés dans des dossiers, dossiers personnalisables pour vos modèles
  - Export : un programme, tout le projet (dossier), TOUT EN UN SEUL FICHIER, ou .exe
  - Mise en évidence : le bloc sélectionné illumine son code (et un clic sur le code sélectionne le bloc)
  - « Flux du projet » : second graphe où programmes (entrées/sorties multiples) et documents sont reliés
"""

import atexit
import html
import importlib.util
import json
import keyword
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import traceback
import unicodedata
from pathlib import Path

# --- Démarrage : préférences, console Windows masquée, mini écran de chargement ---------------
PREFS_FILE = Path.home() / ".editeur_code_blocs.json"


def load_prefs():
    try:
        data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


PREFS = load_prefs()


def save_pref(key, value):
    PREFS[key] = value
    try:
        PREFS_FILE.write_text(json.dumps(PREFS, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def console_window(visible):
    """Windows : affiche ou masque la fenêtre de commandes (console) de ce processus."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 5 if visible else 0)
    except Exception:
        pass


def child_python():
    """Python utilisé pour lancer vos programmes (pythonw sous Windows : aucune fenêtre noire)."""
    exe = sys.executable
    if sys.platform == "win32":
        w = Path(exe).with_name("pythonw.exe")
        if w.exists():
            return str(w)
    return exe


def _fatal(text):
    """Erreur au démarrage : journal + message visible, même sans console."""
    try:
        with open(Path.home() / ".editeur_code_blocs_erreurs.log", "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Code Node", text[-1500:])
        root.destroy()
    except Exception:
        try:
            sys.__stderr__.write(text)
        except Exception:
            pass


def relaunch_without_console():
    """Windows : relance ce même fichier avec pythonw (aucune console), puis ce processus se termine."""
    if sys.platform != "win32" or "--sans-console" in sys.argv:
        return False
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    if exe.name.lower() == "pythonw.exe" or not pyw.exists():
        return False
    try:
        flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
        subprocess.Popen([str(pyw), os.path.abspath(__file__), "--sans-console", *sys.argv[1:]],
                         creationflags=flags, close_fds=True)
        return True
    except (OSError, ValueError):
        return False


_BOOT = {"fr": ("Code Node", "Chargement…"), "en": ("Code Node", "Loading…"),
         "es": ("Code Node", "Cargando…"), "de": ("Code Node", "Wird geladen…"),
         "ru": ("Code Node", "Загрузка…"), "zh": ("Code Node", "正在加载…"),
         "ja": ("Code Node", "読み込み中…")}
_EARLY = None
if __name__ == "__main__":
    if importlib.util.find_spec("PySide6") is None:
        _fatal("PySide6 n'est pas installé.\nOuvrez une invite de commandes et tapez :\n\n"
               "    py -m pip install PySide6")
        sys.exit(1)
    if "--sans-console" in sys.argv:  # on est déjà dans le processus sans console
        sys.argv.remove("--sans-console")
    elif PREFS.get("hide_console", True):
        if relaunch_without_console():
            sys.exit(0)  # le nouveau processus (sans console) prend le relais
        console_window(False)  # repli : on masque la console de ce processus
        atexit.register(console_window, True)
    if PREFS.get("splash", True):  # affiché tout de suite, avant le chargement (lent) de Qt
        try:
            import tkinter as _tk
            _t, _s = _BOOT.get(PREFS.get("lang", "fr"), _BOOT["fr"])
            _EARLY = _tk.Tk()
            _EARLY.overrideredirect(True)
            _EARLY.configure(bg="#1b1c23")
            _EARLY.attributes("-topmost", True)
            _EARLY.geometry(f"480x250+{(_EARLY.winfo_screenwidth() - 480) // 2}"
                            f"+{(_EARLY.winfo_screenheight() - 250) // 2}")
            _tk.Label(_EARLY, text="◆  " + _t, fg="#e8e9f0", bg="#1b1c23",
                      font=("Segoe UI", 19, "bold")).pack(pady=(78, 6))
            _tk.Label(_EARLY, text=_s, fg="#8b8fa8", bg="#1b1c23", font=("Segoe UI", 11)).pack()
            _EARLY.update()
        except Exception:
            _EARLY = None

from PySide6.QtCore import (
    QLineF, QMimeData, QPointF, QProcess, QProcessEnvironment, QRectF,
    QSettings, QSize, Qt, QTimer, QUrl, Signal,
)
from PySide6.QtGui import (
    QAction, QColor, QCursor, QDesktopServices, QFont, QFontDatabase,
    QFontMetrics, QIcon, QKeySequence, QPainter, QPainterPath,
    QPainterPathStroker, QPalette, QPen, QPixmap, QSyntaxHighlighter,
    QTextCharFormat, QTextCursor, QTextFormat,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QColorDialog, QComboBox, QDialog,
    QDialogButtonBox, QDockWidget, QFileDialog, QFormLayout, QGraphicsItem,
    QGraphicsPathItem, QGraphicsScene, QGraphicsView, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy, QSlider, QStyle,
    QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QToolBar, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

# =========================================================================== #
#  TRADUCTIONS : interface (clé = texte français) et aide Python (7 langues)
# =========================================================================== #
LANGS = [("fr", "Français"), ("en", "English"), ("es", "Español"), ("de", "Deutsch"),
         ("ru", "Русский"), ("zh", "中文"), ("ja", "日本語")]
LANG = "fr"


def set_language(code):
    global LANG
    LANG = code if code in dict(LANGS) else "fr"


set_language(PREFS.get("lang", "fr"))
TR = {}


def tr(text):
    """Traduit un texte français (clé). Repli : anglais, puis français."""
    if LANG == "fr":
        return text
    d = TR.get(text)
    if not d:
        return text
    return d.get(LANG) or d.get("en") or text


# français | anglais | espagnol | allemand | russe | chinois | japonais
TR_RAW = r"""
Fichier|File|Archivo|Datei|Файл|文件|ファイル
Projet|Project|Proyecto|Projekt|Проект|项目|プロジェクト
Exporter|Export|Exportar|Exportieren|Экспорт|导出|エクスポート
Édition|Edit|Edición|Bearbeiten|Правка|编辑|編集
Exécution|Run|Ejecución|Ausführung|Запуск|运行|実行
Affichage|View|Ver|Ansicht|Вид|视图|表示
Nouveau projet…|New project…|Nuevo proyecto…|Neues Projekt…|Новый проект…|新建项目…|新規プロジェクト…
Ouvrir un projet…|Open project…|Abrir proyecto…|Projekt öffnen…|Открыть проект…|打开项目…|プロジェクトを開く…
Nouveau programme|New program|Nuevo programa|Neues Programm|Новая программа|新建程序|新規プログラム
Ouvrir un programme (.json)…|Open program (.json)…|Abrir programa (.json)…|Programm öffnen (.json)…|Открыть программу (.json)…|打开程序 (.json)…|プログラムを開く (.json)…
Enregistrer|Save|Guardar|Speichern|Сохранить|保存|保存
Enregistrer le programme sous…|Save program as…|Guardar programa como…|Programm speichern unter…|Сохранить программу как…|程序另存为…|名前を付けてプログラムを保存…
Tout enregistrer|Save all|Guardar todo|Alles speichern|Сохранить всё|全部保存|すべて保存
Quitter|Quit|Salir|Beenden|Выход|退出|終了
Dupliquer|Duplicate|Duplicar|Duplizieren|Дублировать|复制|複製
Supprimer la sélection|Delete selection|Eliminar selección|Auswahl löschen|Удалить выделенное|删除所选|選択を削除
Tout sélectionner|Select all|Seleccionar todo|Alles auswählen|Выделить всё|全选|すべて選択
▶  Exécuter|▶  Run|▶  Ejecutar|▶  Ausführen|▶  Запустить|▶  运行|▶  実行
■  Arrêter|■  Stop|■  Detener|■  Stoppen|■  Остановить|■  停止|■  停止
▶▶  Exécuter le projet|▶▶  Run project|▶▶  Ejecutar proyecto|▶▶  Projekt ausführen|▶▶  Запустить проект|▶▶  运行项目|▶▶  プロジェクトを実行
Tout afficher|Show all|Mostrar todo|Alles anzeigen|Показать всё|显示全部|すべて表示
Zoom 100 %|Zoom 100%|Zoom 100 %|Zoom 100 %|Масштаб 100 %|缩放 100%|ズーム 100%
Aimanter à la grille|Snap to grid|Ajustar a la cuadrícula|Am Raster ausrichten|Привязка к сетке|对齐网格|グリッドに吸着
Nouveau document texte|New text document|Nuevo documento de texto|Neues Textdokument|Новый текстовый документ|新建文本文档|新規テキスト文書
Importer des fichiers dans le projet…|Import files into project…|Importar archivos al proyecto…|Dateien ins Projekt importieren…|Импортировать файлы в проект…|向项目导入文件…|ファイルをプロジェクトにインポート…
Définir comme programme principal|Set as main program|Definir como programa principal|Als Hauptprogramm festlegen|Сделать главной программой|设为主程序|メインプログラムに設定
Actualiser l'explorateur|Refresh explorer|Actualizar explorador|Explorer aktualisieren|Обновить обозреватель|刷新资源管理器|エクスプローラーを更新
🔀  Ouvrir le flux du projet|🔀  Open project flow|🔀  Abrir flujo del proyecto|🔀  Projektfluss öffnen|🔀  Открыть поток проекта|🔀  打开项目流程|🔀  プロジェクトフローを開く
📚  Bibliothèques…|📚  Libraries…|📚  Bibliotecas…|📚  Bibliotheken…|📚  Библиотеки…|📚  库…|📚  ライブラリ…
Installer un paquet (pip)…|Install a package (pip)…|Instalar un paquete (pip)…|Paket installieren (pip)…|Установить пакет (pip)…|安装包 (pip)…|パッケージをインストール (pip)…
Programme actuel (.py)…|Current program (.py)…|Programa actual (.py)…|Aktuelles Programm (.py)…|Текущая программа (.py)…|当前程序 (.py)…|現在のプログラム (.py)…
Projet complet (dossier)…|Whole project (folder)…|Proyecto completo (carpeta)…|Ganzes Projekt (Ordner)…|Весь проект (папка)…|完整项目（文件夹）…|プロジェクト全体（フォルダー）…
⇪  Tout en UN SEUL fichier (.py)…|⇪  Everything in ONE file (.py)…|⇪  Todo en UN solo archivo (.py)…|⇪  Alles in EINER Datei (.py)…|⇪  Всё в ОДНОМ файле (.py)…|⇪  全部合并为一个文件 (.py)…|⇪  すべてを1つのファイルに (.py)…
Créer un exécutable (.exe)…|Create an executable (.exe)…|Crear un ejecutable (.exe)…|Ausführbare Datei erstellen (.exe)…|Создать исполняемый файл (.exe)…|创建可执行文件 (.exe)…|実行ファイルを作成 (.exe)…
⚙  Paramètres…|⚙  Settings…|⚙  Ajustes…|⚙  Einstellungen…|⚙  Настройки…|⚙  设置…|⚙  設定…
Blocs|Blocks|Bloques|Blöcke|Блоки|代码块|ブロック
Code Python généré|Generated Python code|Código Python generado|Erzeugter Python-Code|Сгенерированный код Python|生成的 Python 代码|生成されたPythonコード
Console|Console|Consola|Konsole|Консоль|控制台|コンソール
Thème :|Theme:|Tema:|Design:|Тема:|主题：|テーマ：
Aucun projet ouvert|No project open|Ningún proyecto abierto|Kein Projekt geöffnet|Проект не открыт|未打开项目|プロジェクトが開かれていません
＋ Programme|＋ Program|＋ Programa|＋ Programm|＋ Программа|＋ 程序|＋ プログラム
＋ Document|＋ Document|＋ Documento|＋ Dokument|＋ Документ|＋ 文档|＋ ドキュメント
Programmes|Programs|Programas|Programme|Программы|程序|プログラム
Documents|Documents|Documentos|Dokumente|Документы|文档|ドキュメント
Flux du projet|Project flow|Flujo del proyecto|Projektfluss|Поток проекта|项目流程|プロジェクトフロー
Fichier ▸ Nouveau projet…|File ▸ New project…|Archivo ▸ Nuevo proyecto…|Datei ▸ Neues Projekt…|Файл ▸ Новый проект…|文件 ▸ 新建项目…|ファイル ▸ 新規プロジェクト…
Double-clic ou glisser un bloc vers la zone de travail.|Double-click or drag a block into the workspace.|Doble clic o arrastra un bloque al área de trabajo.|Doppelklick oder Block in den Arbeitsbereich ziehen.|Дважды щёлкните или перетащите блок в рабочую область.|双击或拖动代码块到工作区。|ダブルクリックまたはドラッグでブロックを作業領域へ。
＋ Modèle de bloc|＋ Block template|＋ Plantilla de bloque|＋ Blockvorlage|＋ Шаблон блока|＋ 代码块模板|＋ ブロックテンプレート
＋ Dossier|＋ Folder|＋ Carpeta|＋ Ordner|＋ Папка|＋ 文件夹|＋ フォルダー
Copier|Copy|Copiar|Kopieren|Копировать|复制|コピー
Exporter .py|Export .py|Exportar .py|.py exportieren|Экспорт .py|导出 .py|.py をエクスポート
Réponse envoyée au programme (Entrée) — pour les blocs « Saisie »|Reply sent to the program (Enter) — for Input blocks|Respuesta enviada al programa (Intro) — para bloques Entrada|Antwort an das Programm (Enter) — für Eingabe-Blöcke|Ответ программе (Enter) — для блоков Ввод|发送给程序的回复（回车）— 用于输入块|プログラムへの返答（Enter）— 入力ブロック用
La sortie du programme s'affichera ici (F5 pour exécuter).|The program output will appear here (F5 to run).|La salida del programa aparecerá aquí (F5 para ejecutar).|Die Ausgabe des Programms erscheint hier (F5 zum Ausführen).|Здесь появится вывод программы (F5 — запуск).|程序输出将显示在这里（按 F5 运行）。|プログラムの出力がここに表示されます（F5で実行）。
Aucun programme ouvert.|No program open.|Ningún programa abierto.|Kein Programm geöffnet.|Программа не открыта.|没有打开的程序。|開いているプログラムはありません。
✓ Code valide|✓ Valid code|✓ Código válido|✓ Code gültig|✓ Код корректен|✓ 代码有效|✓ コードは有効です
✗ Erreur de syntaxe ligne {} : {}|✗ Syntax error line {}: {}|✗ Error de sintaxis línea {}: {}|✗ Syntaxfehler Zeile {}: {}|✗ Синтаксическая ошибка, строка {}: {}|✗ 语法错误，第 {} 行：{}|✗ 構文エラー {} 行目：{}
▶ Exécution de « {} »…|▶ Running « {} »…|▶ Ejecutando « {} »…|▶ « {} » wird ausgeführt…|▶ Запуск « {} »…|▶ 正在运行“{}”…|▶ « {} » を実行中…
■ Terminé (code {})|■ Finished (code {})|■ Terminado (código {})|■ Beendet (Code {})|■ Завершено (код {})|■ 已结束（代码 {}）|■ 終了（コード {}）
Bloc sélectionné : {} (lignes {}–{})|Selected block: {} (lines {}–{})|Bloque seleccionado: {} (líneas {}–{})|Ausgewählter Block: {} (Zeilen {}–{})|Выбранный блок: {} (строки {}–{})|所选块：{}（第 {}–{} 行）|選択中のブロック：{}（{}–{} 行）
Ce bloc ne produit aucun code (non relié au « Début » ?)|This block produces no code (not linked to Start?)|Este bloque no produce código (¿no conectado a Inicio?)|Dieser Block erzeugt keinen Code (nicht mit Start verbunden?)|Этот блок не создаёт код (не связан с Началом?)|此块不产生代码（未连接到“开始”？）|このブロックはコードを生成しません（開始につながっていない？）
Expliquer « {} »|Explain « {} »|Explicar « {} »|« {} » erklären|Объяснить « {} »|解释“{}”|「{}」を説明
Éditeur de code à blocs|Block code editor|Editor de código por bloques|Block-Code-Editor|Блочный редактор кода|积木代码编辑器|ブロックコードエディター
Chargement…|Loading…|Cargando…|Wird geladen…|Загрузка…|正在加载…|読み込み中…
Préparation de l'interface…|Preparing the interface…|Preparando la interfaz…|Oberfläche wird vorbereitet…|Подготовка интерфейса…|正在准备界面…|インターフェースを準備中…
Application du thème…|Applying the theme…|Aplicando el tema…|Design wird angewendet…|Применение темы…|正在应用主题…|テーマを適用中…
Ouverture du projet…|Opening the project…|Abriendo el proyecto…|Projekt wird geöffnet…|Открытие проекта…|正在打开项目…|プロジェクトを開いています…
Prêt !|Ready!|¡Listo!|Bereit!|Готово!|就绪！|準備完了！
Fichier ▸ Nouveau projet… pour créer un dossier de travail · glissez les blocs depuis la liste · F5 : exécuter · ⚙ Paramètres : Ctrl+,|File ▸ New project… to create a workspace · drag blocks from the list · F5: run · ⚙ Settings: Ctrl+,|Archivo ▸ Nuevo proyecto… para crear una carpeta de trabajo · arrastra bloques de la lista · F5: ejecutar · ⚙ Ajustes: Ctrl+,|Datei ▸ Neues Projekt… für einen Arbeitsordner · Blöcke aus der Liste ziehen · F5: ausführen · ⚙ Einstellungen: Strg+,|Файл ▸ Новый проект… — рабочая папка · перетаскивайте блоки из списка · F5 — запуск · ⚙ Настройки: Ctrl+,|文件 ▸ 新建项目… 创建工作文件夹 · 从列表拖动代码块 · F5：运行 · ⚙ 设置：Ctrl+,|ファイル ▸ 新規プロジェクト… で作業フォルダーを作成 · リストからブロックをドラッグ · F5：実行 · ⚙ 設定：Ctrl+,
Flux|Flow|Flujo|Ablauf|Поток|流程|フロー
Données|Data|Datos|Daten|Данные|数据|データ
Fichiers|Files|Archivos|Dateien|Файлы|文件|ファイル
Bibliothèques & programmes|Libraries & programs|Bibliotecas y programas|Bibliotheken & Programme|Библиотеки и программы|库与程序|ライブラリとプログラム
Code|Code|Código|Code|Код|代码|コード
Mes modèles|My templates|Mis plantillas|Meine Vorlagen|Мои шаблоны|我的模板|マイテンプレート
Début|Start|Inicio|Start|Начало|开始|開始
Fin / Retour|End / Return|Fin / Retorno|Ende / Rückgabe|Конец / Возврат|结束 / 返回|終了 / 戻り値
Si / Sinon|If / Else|Si / Si no|Wenn / Sonst|Если / Иначе|如果 / 否则|もし / それ以外
Répéter|Repeat|Repetir|Wiederholen|Повторять|重复|繰り返す
Tant que|While|Mientras|Solange|Пока|当…时|〜の間
Pour chaque|For each|Para cada|Für jedes|Для каждого|对每个|それぞれ
Attendre|Wait|Esperar|Warten|Ждать|等待|待つ
Variable|Variable|Variable|Variable|Переменная|变量|変数
Saisie|Input|Entrada|Eingabe|Ввод|输入|入力
Afficher|Show|Mostrar|Anzeigen|Показать|显示|表示
Ajouter à une liste|Add to a list|Añadir a una lista|Zu Liste hinzufügen|Добавить в список|添加到列表|リストに追加
Nombre aléatoire|Random number|Número aleatorio|Zufallszahl|Случайное число|随机数|ランダムな数
Date et heure|Date and time|Fecha y hora|Datum und Uhrzeit|Дата и время|日期和时间|日付と時刻
Lire un document|Read a document|Leer un documento|Dokument lesen|Прочитать документ|读取文档|ドキュメントを読む
Écrire un document|Write a document|Escribir un documento|Dokument schreiben|Записать документ|写入文档|ドキュメントに書く
Importer|Import|Importar|Importieren|Импорт|导入|インポート
Appeler un programme|Call a program|Llamar a un programa|Programm aufrufen|Вызвать программу|调用程序|プログラムを呼ぶ
Code Python|Python code|Código Python|Python-Code|Код Python|Python 代码|Pythonコード
Programme|Program|Programa|Programm|Программа|程序|プログラム
Document|Document|Documento|Dokument|Документ|文档|ドキュメント
Valeur|Value|Valor|Wert|Значение|值|値
Suite|Next|Siguiente|Weiter|Далее|下一步|次へ
Vrai|True|Verdadero|Wahr|Истина|真|真
Faux|False|Falso|Falsch|Ложь|假|偽
Corps|Body|Cuerpo|Rumpf|Тело|循环体|本体
Après|After|Después|Danach|После|之后|その後
Point de départ du programme|Program start point|Punto de inicio del programa|Startpunkt des Programms|Точка входа программы|程序起点|プログラムの開始点
Termine le programme|Ends the program|Termina el programa|Beendet das Programm|Завершает программу|结束程序|プログラムを終了
retourner {}|return {}|devolver {}|zurückgeben {}|вернуть {}|返回 {}|{} を返す
répéter {} fois|repeat {} times|repetir {} veces|{} Mal wiederholen|повторить {} раз|重复 {} 次|{} 回繰り返す
tant que {}|while {}|mientras {}|solange {}|пока {}|当 {} 时|{} の間
si {}|if {}|si {}|wenn {}|если {}|如果 {}|もし {}
pour {} dans {}|for {} in {}|para {} en {}|für {} in {}|для {} в {}|对 {} 在 {} 中|{} を {} の中で
attendre {} s|wait {} s|esperar {} s|{} s warten|ждать {} с|等待 {} 秒|{} 秒待つ
aléatoire({} à {})|random({} to {})|aleatorio({} a {})|Zufall({} bis {})|случайное({}–{})|随机({} 到 {})|ランダム({}〜{})
date et heure|date and time|fecha y hora|Datum und Uhrzeit|дата и время|日期和时间|日付と時刻
(choisir un programme)|(choose a program)|(elegir un programa)|(Programm wählen)|(выберите программу)|（选择程序）|（プログラムを選択）
(choisir un document)|(choose a document)|(elegir un documento)|(Dokument wählen)|(выберите документ)|（选择文档）|（ドキュメントを選択）
Aucune entrée / sortie déclarée|No input / output declared|Ninguna entrada / salida declarada|Keine Ein-/Ausgabe deklariert|Входы/выходы не объявлены|未声明输入/输出|入出力が宣言されていません
Ouvrir le flux du projet|Open project flow|Abrir flujo del proyecto|Projektfluss öffnen|Открыть поток проекта|打开项目流程|プロジェクトフローを開く
Définir comme point d'entrée du projet|Set as project entry point|Definir como punto de entrada del proyecto|Als Einstiegspunkt des Projekts festlegen|Сделать точкой входа проекта|设为项目入口|プロジェクトのエントリポイントに設定
Ouvrir|Open|Abrir|Öffnen|Открыть|打开|開く
Renommer…|Rename…|Renombrar…|Umbenennen…|Переименовать…|重命名…|名前を変更…
Supprimer|Delete|Eliminar|Löschen|Удалить|删除|削除
Nouveau document texte…|New text document…|Nuevo documento de texto…|Neues Textdokument…|Новый текстовый документ…|新建文本文档…|新規テキスト文書…
Nouveau dossier…|New folder…|Nueva carpeta…|Neuer Ordner…|Новая папка…|新建文件夹…|新規フォルダー…
Importer des fichiers…|Import files…|Importar archivos…|Dateien importieren…|Импортировать файлы…|导入文件…|ファイルをインポート…
Renommer le dossier…|Rename folder…|Renombrar carpeta…|Ordner umbenennen…|Переименовать папку…|重命名文件夹…|フォルダー名を変更…
Supprimer le dossier|Delete folder|Eliminar carpeta|Ordner löschen|Удалить папку|删除文件夹|フォルダーを削除
Ajouter un bloc « Lire »|Add a Read block|Añadir un bloque Leer|Block Lesen hinzufügen|Добавить блок Чтение|添加读取块|読むブロックを追加
Ajouter un bloc « Écrire »|Add a Write block|Añadir un bloque Escribir|Block Schreiben hinzufügen|Добавить блок Запись|添加写入块|書くブロックを追加
Nouveau programme…|New program…|Nuevo programa…|Neues Programm…|Новая программа…|新建程序…|新規プログラム…
Modifier le modèle…|Edit template…|Editar plantilla…|Vorlage bearbeiten…|Изменить шаблон…|编辑模板…|テンプレートを編集…
Déplacer vers un dossier…|Move to a folder…|Mover a una carpeta…|In Ordner verschieben…|Переместить в папку…|移动到文件夹…|フォルダーへ移動…
Supprimer le modèle|Delete template|Eliminar plantilla|Vorlage löschen|Удалить шаблон|删除模板|テンプレートを削除
Nouveau modèle dans ce dossier…|New template in this folder…|Nueva plantilla en esta carpeta…|Neue Vorlage in diesem Ordner…|Новый шаблон в этой папке…|在此文件夹中新建模板…|このフォルダーに新規テンプレート…
Nouveau dossier de rangement…|New organizing folder…|Nueva carpeta de organización…|Neuer Ordnungsordner…|Новая папка для организации…|新建整理文件夹…|新規整理フォルダー…
Modifier…|Edit…|Editar…|Bearbeiten…|Изменить…|编辑…|編集…
Enregistrer comme modèle…|Save as template…|Guardar como plantilla…|Als Vorlage speichern…|Сохранить как шаблон…|保存为模板…|テンプレートとして保存…
Supprimer la liaison|Delete link|Eliminar enlace|Verbindung löschen|Удалить связь|删除连线|接続を削除
Ouvrir ce programme|Open this program|Abrir este programa|Dieses Programm öffnen|Открыть эту программу|打开此程序|このプログラムを開く
Lire ce document|Read this document|Leer este documento|Dieses Dokument lesen|Прочитать этот документ|读取此文档|このドキュメントを読む
Écrire dans ce document|Write to this document|Escribir en este documento|In dieses Dokument schreiben|Записать в этот документ|写入此文档|このドキュメントに書く
Paramètres|Settings|Ajustes|Einstellungen|Настройки|设置|設定
Général|General|General|Allgemein|Общие|常规|一般
Apparence|Appearance|Apariencia|Darstellung|Оформление|外观|外観
Aide Python|Python help|Ayuda de Python|Python-Hilfe|Справка по Python|Python 帮助|Pythonヘルプ
Aide|Help|Ayuda|Hilfe|Справка|帮助|ヘルプ
📖  Aide Python…|📖  Python help…|📖  Ayuda de Python…|📖  Python-Hilfe…|📖  Справка по Python…|📖  Python 帮助…|📖  Pythonヘルプ…
Rechercher un paramètre…|Search a setting…|Buscar un ajuste…|Einstellung suchen…|Поиск параметра…|搜索设置…|設定を検索…
{} paramètre(s) trouvé(s)|{} setting(s) found|{} ajuste(s) encontrado(s)|{} Einstellung(en) gefunden|Найдено параметров: {}|找到 {} 项设置|{} 件の設定が見つかりました
Aucun paramètre trouvé.|No setting found.|Ningún ajuste encontrado.|Keine Einstellung gefunden.|Параметры не найдены.|未找到设置。|該当する設定がありません。
Bloc concerné : {}|Affected block: {}|Bloque afectado: {}|Betroffener Block: {}|Проблемный блок: {}|相关代码块：{}|該当ブロック：{}
Langue de l'interface et de l'aide|Interface and help language|Idioma de la interfaz y de la ayuda|Sprache der Oberfläche und der Hilfe|Язык интерфейса и справки|界面与帮助语言|インターフェースとヘルプの言語
Comportement|Behavior|Comportamiento|Verhalten|Поведение|行为|動作
Aimanter les blocs à la grille|Snap blocks to the grid|Ajustar bloques a la cuadrícula|Blöcke am Raster ausrichten|Привязывать блоки к сетке|将代码块对齐到网格|ブロックをグリッドに吸着
Masquer la fenêtre de commandes Windows (console)|Hide the Windows command window (console)|Ocultar la ventana de comandos de Windows (consola)|Windows-Eingabeaufforderung (Konsole) ausblenden|Скрывать окно командной строки Windows (консоль)|隐藏 Windows 命令窗口（控制台）|Windowsのコマンドウィンドウ（コンソール）を隠す
Afficher l'écran de chargement au démarrage|Show the loading screen at startup|Mostrar la pantalla de carga al iniciar|Ladebildschirm beim Start anzeigen|Показывать экран загрузки при запуске|启动时显示加载画面|起動時に読み込み画面を表示
S'applique au prochain démarrage.|Applies at next start.|Se aplica en el próximo inicio.|Gilt ab dem nächsten Start.|Применяется при следующем запуске.|下次启动时生效。|次回の起動時に反映されます。
Thème|Theme|Tema|Design|Тема|主题|テーマ
Couleur d'accent|Accent color|Color de acento|Akzentfarbe|Акцентный цвет|强调色|アクセントカラー
Choisir…|Choose…|Elegir…|Wählen…|Выбрать…|选择…|選択…
Par défaut|Default|Predeterminado|Standard|По умолчанию|默认|既定
Taille du texte|Text size|Tamaño del texto|Textgröße|Размер текста|文字大小|文字サイズ
Arrondi des blocs|Block roundness|Redondeo de bloques|Blockrundung|Скругление блоков|代码块圆角|ブロックの角丸
Afficher la grille|Show the grid|Mostrar la cuadrícula|Raster anzeigen|Показывать сетку|显示网格|グリッドを表示
Réinitialiser l'apparence|Reset appearance|Restablecer apariencia|Darstellung zurücksetzen|Сбросить оформление|重置外观|外観をリセット
Rechercher un mot-clé ou une fonction Python…|Search a Python keyword or function…|Buscar una palabra clave o función de Python…|Python-Schlüsselwort oder -Funktion suchen…|Поиск ключевого слова или функции Python…|搜索 Python 关键字或函数…|Pythonのキーワードや関数を検索…
La recherche inclut toujours les termes anglais.|Search always includes the English terms.|La búsqueda siempre incluye los términos en inglés.|Die Suche berücksichtigt immer die englischen Begriffe.|Поиск всегда учитывает английские термины.|搜索始终包含英文术语。|検索には常に英語の用語も含まれます。
Tout|All|Todo|Alle|Все|全部|すべて
Mots-clés|Keywords|Palabras clave|Schlüsselwörter|Ключевые слова|关键字|キーワード
Fonctions|Functions|Funciones|Funktionen|Функции|函数|関数
Mot-clé|Keyword|Palabra clave|Schlüsselwort|Ключевое слово|关键字|キーワード
Fonction|Function|Función|Funktion|Функция|函数|関数
Exemple|Example|Ejemplo|Beispiel|Пример|示例|例
Aucun résultat.|No results.|Sin resultados.|Keine Ergebnisse.|Нет результатов.|没有结果。|結果がありません。
{} résultat(s)|{} result(s)|{} resultado(s)|{} Ergebnis(se)|Результатов: {}|{} 个结果|{} 件の結果
Sélectionnez un élément pour voir son explication.|Select an item to see its explanation.|Selecciona un elemento para ver su explicación.|Wählen Sie ein Element für die Erklärung.|Выберите элемент, чтобы увидеть объяснение.|选择一项以查看说明。|項目を選ぶと説明が表示されます。
Sombre|Dark|Oscuro|Dunkel|Тёмная|深色|ダーク
Clair|Light|Claro|Hell|Светлая|浅色|ライト
Océan|Ocean|Océano|Ozean|Океан|海洋|オーシャン
Forêt|Forest|Bosque|Wald|Лес|森林|フォレスト
Néon|Neon|Neón|Neon|Неон|霓虹|ネオン
Papier|Paper|Papel|Papier|Бумага|纸张|ペーパー
"""


def _load_tr(raw):
    for line in raw.strip().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 7:
            TR[parts[0]] = dict(zip(("en", "es", "de", "ru", "zh", "ja"), parts[1:]))


_load_tr(TR_RAW)

# Aide Python : [nom] catégorie (kw = mot-clé, fn = fonction), ex = exemple, puis « langue libellé | explication »
REF_RAW = r"""
[False] kw
ex ok = False
fr faux | Valeur booléenne faux.
en false | Boolean value meaning false.
es falso | Valor booleano falso.
de falsch | Boolescher Wert falsch.
ru ложь | Логическое значение ложь.
zh 假 | 布尔值“假”。
ja 偽 | 真偽値の偽です。
[None] kw
ex resultat = None
fr aucun | Valeur spéciale qui signifie rien.
en nothing | Special value meaning no value.
es ninguno | Valor especial que significa nada.
de nichts | Spezieller Wert für kein Wert.
ru ничего | Особое значение нет значения.
zh 空值 | 表示“没有值”的特殊值。
ja なし | 値がないことを表す特別な値です。
[True] kw
ex ok = True
fr vrai | Valeur booléenne vrai.
en true | Boolean value meaning true.
es verdadero | Valor booleano verdadero.
de wahr | Boolescher Wert wahr.
ru истина | Логическое значение истина.
zh 真 | 布尔值“真”。
ja 真 | 真偽値の真です。
[and] kw
ex if a > 0 and b > 0:\n    print("positifs")
fr et | Vrai seulement si les deux conditions sont vraies.
en and | True only if both conditions are true.
es y | Verdadero solo si ambas condiciones lo son.
de und | Wahr nur, wenn beide Bedingungen wahr sind.
ru и | Истинно, только если оба условия истинны.
zh 并且 | 仅当两个条件都为真时才为真。
ja かつ | 両方の条件が真のときだけ真になります。
[as] kw
ex import numpy as np
fr comme | Donne un autre nom (alias) à un import ou à un fichier ouvert.
en as | Gives an alias to an import or an opened file.
es como | Da un alias a una importación o a un archivo abierto.
de als | Gibt einem Import oder einer geöffneten Datei einen Alias.
ru как | Задаёт псевдоним для импорта или открытого файла.
zh 作为 | 为导入或打开的文件起别名。
ja として | インポートや開いたファイルに別名を付けます。
[assert] kw
ex assert age >= 0
fr vérifier | Arrête le programme si une condition attendue est fausse.
en assert | Stops the program if an expected condition is false.
es afirmar | Detiene el programa si una condición esperada es falsa.
de sicherstellen | Bricht ab, wenn eine erwartete Bedingung falsch ist.
ru проверить | Останавливает программу, если ожидаемое условие ложно.
zh 断言 | 如果预期条件为假，则终止程序。
ja 表明 | 期待した条件が偽ならプログラムを止めます。
[async] kw
ex async def charger():\n    ...
fr asynchrone | Définit une fonction qui peut être suspendue (avec await).
en async | Defines a function that can be paused (with await).
es asíncrono | Define una función que puede pausarse (con await).
de asynchron | Definiert eine Funktion, die pausiert werden kann (mit await).
ru асинхронный | Определяет функцию, которую можно приостановить (с await).
zh 异步 | 定义可以暂停的函数（配合 await 使用）。
ja 非同期 | 一時停止できる関数を定義します（awaitと併用）。
[await] kw
ex data = await charger()
fr attendre | Attend la fin d'une opération asynchrone.
en await | Waits for an asynchronous operation to finish.
es esperar | Espera a que termine una operación asíncrona.
de warten | Wartet auf das Ende einer asynchronen Operation.
ru ждать | Ждёт завершения асинхронной операции.
zh 等待 | 等待异步操作完成。
ja 待機 | 非同期処理の完了を待ちます。
[break] kw
ex for i in range(10):\n    if i == 3:\n        break
fr arrêter | Sort immédiatement d'une boucle.
en break | Exits a loop immediately.
es romper | Sale inmediatamente de un bucle.
de abbrechen | Verlässt eine Schleife sofort.
ru прервать | Немедленно выходит из цикла.
zh 跳出 | 立即退出循环。
ja 中断 | ループをすぐに抜けます。
[class] kw
ex class Chat:\n    def parler(self):\n        print("miaou")
fr classe | Définit un nouveau type d'objet avec ses données et ses actions.
en class | Defines a new kind of object with its data and actions.
es clase | Define un nuevo tipo de objeto con sus datos y acciones.
de Klasse | Definiert einen neuen Objekttyp mit Daten und Aktionen.
ru класс | Определяет новый тип объектов с данными и действиями.
zh 类 | 定义带有数据和行为的新对象类型。
ja クラス | データと動作を持つ新しい種類のオブジェクトを定義します。
[continue] kw
ex for i in range(5):\n    if i == 2:\n        continue\n    print(i)
fr continuer | Passe directement à l'itération suivante de la boucle.
en continue | Jumps to the next iteration of the loop.
es continuar | Salta a la siguiente iteración del bucle.
de weiter | Springt zur nächsten Schleifenrunde.
ru продолжить | Переходит к следующей итерации цикла.
zh 继续 | 直接进入循环的下一次迭代。
ja 続行 | ループの次の繰り返しへ進みます。
[def] kw
ex def saluer(nom):\n    print("Bonjour", nom)
fr définir | Crée une fonction réutilisable.
en define | Creates a reusable function.
es definir | Crea una función reutilizable.
de definieren | Erstellt eine wiederverwendbare Funktion.
ru определить | Создаёт функцию, которую можно использовать повторно.
zh 定义 | 创建可重复使用的函数。
ja 定義 | 再利用できる関数を作ります。
[del] kw
ex del liste[0]
fr supprimer | Supprime une variable ou un élément d'une liste.
en delete | Deletes a variable or an item from a list.
es eliminar | Elimina una variable o un elemento de una lista.
de löschen | Löscht eine Variable oder ein Listenelement.
ru удалить | Удаляет переменную или элемент списка.
zh 删除 | 删除变量或列表中的元素。
ja 削除 | 変数やリストの要素を削除します。
[elif] kw
ex if n < 0:\n    print("négatif")\nelif n == 0:\n    print("zéro")
fr sinon si | Teste une autre condition si le if précédent était faux.
en else if | Tests another condition if the previous if was false.
es si no, si | Prueba otra condición si el if anterior fue falso.
de sonst falls | Prüft eine weitere Bedingung, wenn das vorherige if falsch war.
ru иначе если | Проверяет другое условие, если предыдущее if ложно.
zh 否则如果 | 如果前面的 if 为假，则检查另一个条件。
ja そうでなければもし | 直前の if が偽のとき、別の条件を調べます。
[else] kw
ex if age >= 18:\n    print("adulte")\nelse:\n    print("mineur")
fr sinon | Exécute ce bloc quand la condition du if est fausse.
en else | Runs this block when the if condition is false.
es si no | Ejecuta este bloque cuando la condición del if es falsa.
de sonst | Führt diesen Block aus, wenn die if-Bedingung falsch ist.
ru иначе | Выполняет блок, когда условие if ложно.
zh 否则 | 当 if 的条件为假时执行此代码块。
ja それ以外 | if の条件が偽のときにこのブロックを実行します。
[except] kw
ex try:\n    x = int("a")\nexcept ValueError:\n    print("pas un nombre")
fr sauf | Gère une erreur survenue dans le bloc try.
en except | Handles an error raised inside the try block.
es excepto | Gestiona un error ocurrido en el bloque try.
de Ausnahme | Behandelt einen Fehler aus dem try-Block.
ru исключение | Обрабатывает ошибку, возникшую в блоке try.
zh 捕获异常 | 处理 try 代码块中发生的错误。
ja 例外処理 | try ブロックで起きたエラーを処理します。
[finally] kw
ex try:\n    f = open("a.txt")\nfinally:\n    print("fini")
fr finalement | Bloc toujours exécuté, qu'il y ait une erreur ou non.
en finally | Block that always runs, error or not.
es finalmente | Bloque que siempre se ejecuta, haya error o no.
de schließlich | Block, der immer ausgeführt wird, mit oder ohne Fehler.
ru наконец | Блок, который выполняется всегда, с ошибкой или без.
zh 最终 | 无论是否出错都会执行的代码块。
ja 最後に | エラーの有無にかかわらず必ず実行されます。
[for] kw
ex for nom in ["a", "b"]:\n    print(nom)
fr pour | Répète le bloc pour chaque élément d'une séquence.
en for | Repeats the block for each item of a sequence.
es para | Repite el bloque para cada elemento de una secuencia.
de für | Wiederholt den Block für jedes Element einer Folge.
ru для | Повторяет блок для каждого элемента последовательности.
zh 对于 | 对序列中的每个元素重复执行代码块。
ja 〜について | シーケンスの各要素についてブロックを繰り返します。
[from] kw
ex from math import sqrt
fr depuis | Importe des éléments précis d'un module (from … import …).
en from | Imports specific items from a module (from … import …).
es desde | Importa elementos concretos de un módulo (from … import …).
de aus | Importiert bestimmte Elemente aus einem Modul.
ru из | Импортирует отдельные элементы из модуля.
zh 从 | 从模块中导入指定内容。
ja から | モジュールから特定の要素をインポートします。
[global] kw
ex total = 0\ndef ajouter():\n    global total\n    total += 1
fr global | Permet de modifier une variable définie en dehors de la fonction.
en global | Lets a function modify a variable defined outside it.
es global | Permite a una función modificar una variable definida fuera.
de global | Erlaubt, eine außerhalb der Funktion definierte Variable zu ändern.
ru глобальная | Позволяет менять переменную, объявленную вне функции.
zh 全局 | 允许函数修改在函数外定义的变量。
ja グローバル | 関数の外で定義した変数を関数内で変更できるようにします。
[if] kw
ex if age >= 18:\n    print("adulte")
fr si | Exécute le bloc seulement si la condition est vraie.
en if | Runs the block only if the condition is true.
es si | Ejecuta el bloque solo si la condición es verdadera.
de falls | Führt den Block nur aus, wenn die Bedingung wahr ist.
ru если | Выполняет блок, только если условие истинно.
zh 如果 | 仅当条件为真时才执行该代码块。
ja もし | 条件が真のときだけブロックを実行します。
[import] kw
ex import random
fr importer | Charge une bibliothèque (module) pour l'utiliser.
en import | Loads a library (module) so you can use it.
es importar | Carga una biblioteca (módulo) para usarla.
de importieren | Lädt eine Bibliothek (Modul) zur Verwendung.
ru импортировать | Подключает библиотеку (модуль) для использования.
zh 导入 | 加载库（模块）以便使用。
ja インポート | ライブラリ（モジュール）を読み込んで使えるようにします。
[in] kw
ex if "a" in "chat":\n    print("oui")
fr dans | Teste si un élément est présent dans une séquence, ou la parcourt avec for.
en in | Tests whether an item is in a sequence, or loops over one with for.
es en | Comprueba si un elemento está en una secuencia, o la recorre con for.
de in | Prüft, ob ein Element in einer Folge ist, oder durchläuft sie mit for.
ru в | Проверяет, есть ли элемент в последовательности, или перебирает её в for.
zh 在…中 | 判断元素是否在序列中，或在 for 中遍历序列。
ja 〜の中 | 要素が列にあるか調べる、または for で列を順に処理します。
[is] kw
ex if resultat is None:\n    print("rien")
fr est | Vérifie que deux noms désignent exactement le même objet.
en is | Checks that two names refer to the very same object.
es es | Comprueba que dos nombres se refieren exactamente al mismo objeto.
de ist | Prüft, ob zwei Namen genau dasselbe Objekt bezeichnen.
ru является | Проверяет, что два имени указывают на один и тот же объект.
zh 是 | 检查两个名称是否指向同一个对象。
ja 同一である | 2つの名前がまったく同じオブジェクトを指すか調べます。
[lambda] kw
ex double = lambda x: x * 2
fr lambda | Crée une petite fonction anonyme en une ligne.
en lambda | Creates a small anonymous one-line function.
es lambda | Crea una pequeña función anónima en una línea.
de lambda | Erzeugt eine kleine anonyme Einzeiler-Funktion.
ru лямбда | Создаёт небольшую анонимную функцию в одну строку.
zh 匿名函数 | 用一行创建小型匿名函数。
ja ラムダ | 1行の小さな無名関数を作ります。
[nonlocal] kw
ex def a():\n    n = 0\n    def b():\n        nonlocal n\n        n += 1
fr non local | Modifie une variable de la fonction englobante (fonctions imbriquées).
en nonlocal | Modifies a variable of the enclosing function (nested functions).
es no local | Modifica una variable de la función contenedora (funciones anidadas).
de nichtlokal | Ändert eine Variable der umgebenden Funktion (verschachtelte Funktionen).
ru нелокальная | Изменяет переменную внешней функции (вложенные функции).
zh 非局部 | 修改外层函数的变量（嵌套函数中使用）。
ja 非ローカル | 外側の関数の変数を変更します（入れ子の関数で使用）。
[not] kw
ex if not liste:\n    print("liste vide")
fr non | Inverse une condition (vrai devient faux).
en not | Inverts a condition (true becomes false).
es no | Invierte una condición (verdadero pasa a falso).
de nicht | Kehrt eine Bedingung um (wahr wird falsch).
ru не | Инвертирует условие (истина становится ложью).
zh 非 | 反转条件（真变为假）。
ja 否定 | 条件を反転します（真が偽になります）。
[or] kw
ex if a == 0 or b == 0:\n    print("un zéro")
fr ou | Vrai si au moins une des conditions est vraie.
en or | True if at least one condition is true.
es o | Verdadero si al menos una condición es verdadera.
de oder | Wahr, wenn mindestens eine Bedingung wahr ist.
ru или | Истинно, если хотя бы одно условие истинно.
zh 或者 | 只要有一个条件为真即为真。
ja または | どれか1つでも条件が真なら真になります。
[pass] kw
ex def plus_tard():\n    pass
fr passer | Ne fait rien ; sert de bloc vide.
en pass | Does nothing; used as an empty block.
es pasar | No hace nada; sirve como bloque vacío.
de nichts tun | Tut nichts; dient als leerer Block.
ru пропустить | Ничего не делает; нужен как пустой блок.
zh 空操作 | 什么都不做，用作空代码块。
ja 何もしない | 何もしません。空のブロックとして使います。
[raise] kw
ex raise ValueError("valeur invalide")
fr lever | Déclenche volontairement une erreur.
en raise | Deliberately triggers an error.
es lanzar | Provoca un error a propósito.
de auslösen | Löst absichtlich einen Fehler aus.
ru вызвать | Намеренно вызывает ошибку.
zh 抛出 | 主动触发一个错误。
ja 送出 | 意図的にエラーを発生させます。
[return] kw
ex def carre(x):\n    return x * x
fr retourner | Termine la fonction et renvoie une valeur.
en return | Ends the function and sends back a value.
es devolver | Termina la función y devuelve un valor.
de zurückgeben | Beendet die Funktion und gibt einen Wert zurück.
ru вернуть | Завершает функцию и возвращает значение.
zh 返回 | 结束函数并返回一个值。
ja 戻す | 関数を終了して値を返します。
[try] kw
ex try:\n    x = 1 / 0\nexcept ZeroDivisionError:\n    print("division par zéro")
fr essayer | Exécute du code en capturant les erreurs possibles.
en try | Runs code while catching possible errors.
es intentar | Ejecuta código capturando los posibles errores.
de versuchen | Führt Code aus und fängt mögliche Fehler ab.
ru попробовать | Выполняет код, перехватывая возможные ошибки.
zh 尝试 | 执行代码并捕获可能出现的错误。
ja 試行 | コードを実行し、起こり得るエラーを捕まえます。
[while] kw
ex n = 3\nwhile n > 0:\n    n -= 1
fr tant que | Répète le bloc tant que la condition reste vraie.
en while | Repeats the block as long as the condition stays true.
es mientras | Repite el bloque mientras la condición siga siendo verdadera.
de solange | Wiederholt den Block, solange die Bedingung wahr bleibt.
ru пока | Повторяет блок, пока условие остаётся истинным.
zh 当…时 | 只要条件保持为真就重复执行代码块。
ja 〜の間 | 条件が真である間、ブロックを繰り返します。
[with] kw
ex with open("a.txt") as f:\n    texte = f.read()
fr avec | Utilise une ressource (comme un fichier) et la ferme automatiquement.
en with | Uses a resource (like a file) and closes it automatically.
es con | Usa un recurso (como un archivo) y lo cierra automáticamente.
de mit | Nutzt eine Ressource (z. B. Datei) und schließt sie automatisch.
ru с | Использует ресурс (например, файл) и автоматически закрывает его.
zh 使用 | 使用资源（如文件）并自动关闭。
ja 〜を使って | ファイルなどの資源を使い、自動的に閉じます。
[yield] kw
ex def compter():\n    yield 1\n    yield 2
fr produire | Renvoie une valeur à la fois dans un générateur.
en yield | Returns one value at a time from a generator.
es producir | Devuelve un valor cada vez desde un generador.
de liefern | Gibt in einem Generator jeweils einen Wert zurück.
ru выдать | Возвращает по одному значению из генератора.
zh 产出 | 在生成器中每次返回一个值。
ja 生成 | ジェネレーターから値を1つずつ返します。
[print] fn
ex print("Bonjour", 3)
fr afficher | Affiche du texte ou des valeurs à l'écran.
en print | Displays text or values on screen.
es imprimir | Muestra texto o valores en pantalla.
de ausgeben | Zeigt Text oder Werte auf dem Bildschirm an.
ru вывод | Выводит текст или значения на экран.
zh 打印 | 在屏幕上显示文本或值。
ja 表示 | 文字や値を画面に表示します。
[input] fn
ex nom = input("Votre nom : ")
fr saisir | Demande un texte à l'utilisateur et le renvoie.
en input | Asks the user for text and returns it.
es entrada | Pide un texto al usuario y lo devuelve.
de Eingabe | Fragt den Benutzer nach Text und gibt ihn zurück.
ru ввод | Запрашивает у пользователя текст и возвращает его.
zh 输入 | 向用户请求文本并返回。
ja 入力 | ユーザーに文字を入力させて返します。
[len] fn
ex len("chat")  # 4
fr longueur | Donne le nombre d'éléments ou de caractères.
en length | Gives the number of items or characters.
es longitud | Da el número de elementos o caracteres.
de Länge | Gibt die Anzahl der Elemente oder Zeichen an.
ru длина | Возвращает число элементов или символов.
zh 长度 | 返回元素或字符的数量。
ja 長さ | 要素や文字の数を返します。
[range] fn
ex for i in range(3):\n    print(i)
fr intervalle | Génère une suite de nombres entiers (pour les boucles).
en range | Generates a sequence of whole numbers (for loops).
es rango | Genera una secuencia de números enteros (para bucles).
de Bereich | Erzeugt eine Folge ganzer Zahlen (für Schleifen).
ru диапазон | Создаёт последовательность целых чисел (для циклов).
zh 范围 | 生成整数序列（用于循环）。
ja 範囲 | 整数の列を作ります（ループ用）。
[int] fn
ex age = int("18")
fr entier | Convertit une valeur en nombre entier.
en integer | Converts a value to a whole number.
es entero | Convierte un valor en número entero.
de Ganzzahl | Wandelt einen Wert in eine ganze Zahl um.
ru целое | Преобразует значение в целое число.
zh 整数 | 把值转换为整数。
ja 整数 | 値を整数に変換します。
[float] fn
ex prix = float("9.99")
fr décimal | Convertit une valeur en nombre à virgule.
en float | Converts a value to a decimal number.
es decimal | Convierte un valor en número decimal.
de Kommazahl | Wandelt einen Wert in eine Dezimalzahl um.
ru дробное | Преобразует значение в число с плавающей точкой.
zh 浮点数 | 把值转换为小数。
ja 小数 | 値を小数に変換します。
[str] fn
ex texte = str(42)
fr texte | Convertit une valeur en texte.
en string | Converts a value to text.
es cadena | Convierte un valor en texto.
de Text | Wandelt einen Wert in Text um.
ru строка | Преобразует значение в текст.
zh 字符串 | 把值转换为文本。
ja 文字列 | 値を文字列に変換します。
[list] fn
ex fruits = ["pomme", "poire"]
fr liste | Crée une liste ordonnée et modifiable.
en list | Creates an ordered, changeable list.
es lista | Crea una lista ordenada y modificable.
de Liste | Erzeugt eine geordnete, veränderbare Liste.
ru список | Создаёт упорядоченный изменяемый список.
zh 列表 | 创建有序且可修改的列表。
ja リスト | 順序があり変更可能なリストを作ります。
[dict] fn
ex age = {"Léa": 12, "Tom": 9}
fr dictionnaire | Crée une collection de paires clé → valeur.
en dictionary | Creates a collection of key → value pairs.
es diccionario | Crea una colección de pares clave → valor.
de Wörterbuch | Erzeugt eine Sammlung von Schlüssel → Wert-Paaren.
ru словарь | Создаёт набор пар ключ → значение.
zh 字典 | 创建键 → 值对的集合。
ja 辞書 | キーと値のペアの集まりを作ります。
[set] fn
ex uniques = set([1, 1, 2])
fr ensemble | Crée une collection sans doublons.
en set | Creates a collection without duplicates.
es conjunto | Crea una colección sin duplicados.
de Menge | Erzeugt eine Sammlung ohne Duplikate.
ru множество | Создаёт набор без повторов.
zh 集合 | 创建不含重复项的集合。
ja 集合 | 重複のないコレクションを作ります。
[tuple] fn
ex point = (3, 4)
fr n-uplet | Crée une suite d'éléments non modifiable.
en tuple | Creates a fixed, unchangeable sequence of items.
es tupla | Crea una secuencia de elementos no modificable.
de Tupel | Erzeugt eine unveränderliche Folge von Elementen.
ru кортеж | Создаёт неизменяемую последовательность элементов.
zh 元组 | 创建不可修改的元素序列。
ja タプル | 変更できない要素の並びを作ります。
[open] fn
ex f = open("a.txt", "w")
fr ouvrir | Ouvre un fichier en lecture ou en écriture.
en open | Opens a file for reading or writing.
es abrir | Abre un archivo para leer o escribir.
de öffnen | Öffnet eine Datei zum Lesen oder Schreiben.
ru открыть | Открывает файл для чтения или записи.
zh 打开 | 打开文件用于读取或写入。
ja 開く | ファイルを読み書き用に開きます。
[sum] fn
ex sum([1, 2, 3])  # 6
fr somme | Additionne tous les éléments d'une liste.
en sum | Adds up all items of a list.
es suma | Suma todos los elementos de una lista.
de Summe | Addiert alle Elemente einer Liste.
ru сумма | Складывает все элементы списка.
zh 求和 | 把列表中所有元素相加。
ja 合計 | リストの要素をすべて足します。
[min] fn
ex min(4, 2, 9)  # 2
fr minimum | Renvoie la plus petite valeur.
en minimum | Returns the smallest value.
es mínimo | Devuelve el valor más pequeño.
de Minimum | Gibt den kleinsten Wert zurück.
ru минимум | Возвращает наименьшее значение.
zh 最小值 | 返回最小的值。
ja 最小値 | 最も小さい値を返します。
[max] fn
ex max(4, 2, 9)  # 9
fr maximum | Renvoie la plus grande valeur.
en maximum | Returns the largest value.
es máximo | Devuelve el valor más grande.
de Maximum | Gibt den größten Wert zurück.
ru максимум | Возвращает наибольшее значение.
zh 最大值 | 返回最大的值。
ja 最大値 | 最も大きい値を返します。
[abs] fn
ex abs(-5)  # 5
fr valeur absolue | Renvoie un nombre sans son signe (toujours positif).
en absolute value | Returns a number without its sign (always positive).
es valor absoluto | Devuelve un número sin signo (siempre positivo).
de Betrag | Gibt eine Zahl ohne Vorzeichen zurück (immer positiv).
ru модуль | Возвращает число без знака (всегда положительное).
zh 绝对值 | 返回不带符号的数（始终为正）。
ja 絶対値 | 符号を除いた数（常に正）を返します。
[round] fn
ex round(3.14159, 2)  # 3.14
fr arrondir | Arrondit un nombre décimal.
en round | Rounds a decimal number.
es redondear | Redondea un número decimal.
de runden | Rundet eine Dezimalzahl.
ru округлить | Округляет дробное число.
zh 四舍五入 | 对小数进行四舍五入。
ja 四捨五入 | 小数を丸めます。
[sorted] fn
ex sorted([3, 1, 2])  # [1, 2, 3]
fr trier | Renvoie une liste triée.
en sorted | Returns a sorted list.
es ordenar | Devuelve una lista ordenada.
de sortieren | Gibt eine sortierte Liste zurück.
ru сортировка | Возвращает отсортированный список.
zh 排序 | 返回排好序的列表。
ja 並べ替え | 並べ替えたリストを返します。
[enumerate] fn
ex for i, x in enumerate(["a", "b"]):\n    print(i, x)
fr numéroter | Associe un numéro à chaque élément pendant une boucle.
en enumerate | Pairs each item with its index in a loop.
es enumerar | Asocia un número a cada elemento en un bucle.
de nummerieren | Verknüpft in einer Schleife jedes Element mit seinem Index.
ru нумерация | Сопоставляет каждому элементу номер в цикле.
zh 枚举 | 在循环中为每个元素配上序号。
ja 番号付け | ループ中に各要素へ番号を付けます。
[zip] fn
ex for a, b in zip([1, 2], ["x", "y"]):\n    print(a, b)
fr assembler | Associe les éléments de plusieurs listes deux à deux.
en zip | Pairs up items from several lists.
es unir | Empareja los elementos de varias listas.
de verbinden | Verbindet die Elemente mehrerer Listen paarweise.
ru объединить | Попарно объединяет элементы нескольких списков.
zh 打包 | 把多个列表的元素按位置配对。
ja 組み合わせ | 複数のリストの要素を順に組にします。
[map] fn
ex list(map(str, [1, 2]))
fr appliquer | Applique une fonction à chaque élément.
en map | Applies a function to every item.
es aplicar | Aplica una función a cada elemento.
de anwenden | Wendet eine Funktion auf jedes Element an.
ru применить | Применяет функцию к каждому элементу.
zh 映射 | 对每个元素应用一个函数。
ja 適用 | すべての要素に関数を適用します。
[filter] fn
ex list(filter(lambda n: n > 1, [1, 2, 3]))
fr filtrer | Garde seulement les éléments qui respectent une condition.
en filter | Keeps only the items that meet a condition.
es filtrar | Conserva solo los elementos que cumplen una condición.
de filtern | Behält nur Elemente, die eine Bedingung erfüllen.
ru фильтр | Оставляет только элементы, удовлетворяющие условию.
zh 过滤 | 只保留满足条件的元素。
ja フィルター | 条件を満たす要素だけを残します。
[type] fn
ex type(3.5)  # float
fr type | Donne le type d'une valeur (int, str…).
en type | Gives the type of a value (int, str…).
es tipo | Da el tipo de un valor (int, str…).
de Typ | Gibt den Typ eines Werts an (int, str …).
ru тип | Возвращает тип значения (int, str…).
zh 类型 | 返回值的类型（int、str 等）。
ja 型 | 値の型（int、strなど）を返します。
[isinstance] fn
ex isinstance(3, int)  # True
fr est de type | Vérifie qu'une valeur est d'un certain type.
en is instance of | Checks whether a value is of a given type.
es es instancia de | Comprueba si un valor es de cierto tipo.
de ist Instanz von | Prüft, ob ein Wert von einem bestimmten Typ ist.
ru является экземпляром | Проверяет, что значение имеет заданный тип.
zh 是否为类型 | 检查值是否属于某个类型。
ja 型の判定 | 値が特定の型かどうかを調べます。
[bool] fn
ex bool(0)  # False
fr booléen | Convertit une valeur en vrai/faux.
en boolean | Converts a value to true/false.
es booleano | Convierte un valor en verdadero/falso.
de Wahrheitswert | Wandelt einen Wert in wahr/falsch um.
ru логическое | Преобразует значение в истина/ложь.
zh 布尔值 | 把值转换为真/假。
ja 真偽値 | 値を真/偽に変換します。
[append] fn
ex fruits.append("kiwi")
fr ajouter | Ajoute un élément à la fin d'une liste (liste.append).
en append | Adds an item to the end of a list (list.append).
es añadir | Añade un elemento al final de una lista (lista.append).
de anhängen | Hängt ein Element ans Ende einer Liste an (liste.append).
ru добавить | Добавляет элемент в конец списка (список.append).
zh 追加 | 在列表末尾添加元素（列表.append）。
ja 追加 | リストの末尾に要素を追加します（リスト.append）。
[split] fn
ex "a,b,c".split(",")
fr découper | Coupe un texte en liste de morceaux (texte.split).
en split | Cuts a text into a list of pieces (text.split).
es dividir | Corta un texto en una lista de trozos (texto.split).
de teilen | Zerlegt einen Text in eine Liste von Teilen (text.split).
ru разбить | Разбивает текст на список частей (текст.split).
zh 拆分 | 把文本拆成多个片段的列表（文本.split）。
ja 分割 | 文字列を断片のリストに分けます（文字列.split）。
[join] fn
ex ", ".join(["a", "b"])
fr coller du texte | Colle des morceaux de texte avec un séparateur (séparateur.join).
en join | Glues pieces of text with a separator (sep.join).
es unir texto | Une trozos de texto con un separador (sep.join).
de zusammenfügen | Fügt Textteile mit einem Trennzeichen zusammen (sep.join).
ru соединить | Склеивает части текста через разделитель (разд.join).
zh 连接 | 用分隔符把多段文本连接起来（分隔符.join）。
ja 連結 | 区切り文字で文字列をつなぎます（区切り.join）。
[f-string] fn
ex nom = "Léa"\nprint(f"Bonjour {nom} !")
fr texte formaté | Insère des valeurs dans un texte avec f"…{x}…".
en f-string | Inserts values into text with f"…{x}…".
es texto formateado | Inserta valores en un texto con f"…{x}…".
de Formatstring | Fügt Werte mit f"…{x}…" in Text ein.
ru f-строка | Вставляет значения в текст через f"…{x}…".
zh 格式化字符串 | 用 f"…{x}…" 把值插入文本。
ja f文字列 | f"…{x}…" で値を文字列に埋め込みます。
[random.randint] fn
ex import random\nde = random.randint(1, 6)
fr nombre aléatoire | Tire un entier au hasard entre deux valeurs (module random).
en random number | Picks a random whole number between two values (random module).
es número aleatorio | Elige un entero al azar entre dos valores (módulo random).
de Zufallszahl | Wählt eine zufällige ganze Zahl zwischen zwei Werten (Modul random).
ru случайное число | Выбирает случайное целое число между двумя значениями (модуль random).
zh 随机数 | 在两个值之间随机选取一个整数（random 模块）。
ja ランダムな数 | 2つの値の間の整数を無作為に選びます（randomモジュール）。
[time.sleep] fn
ex import time\ntime.sleep(2)
fr pause | Met le programme en pause quelques secondes (module time).
en pause | Pauses the program for some seconds (time module).
es pausa | Pausa el programa unos segundos (módulo time).
de Pause | Hält das Programm einige Sekunden an (Modul time).
ru пауза | Приостанавливает программу на несколько секунд (модуль time).
zh 暂停 | 让程序暂停几秒（time 模块）。
ja 一時停止 | プログラムを数秒止めます（timeモジュール）。
"""

REF = []  # [nom, catégorie, exemple, {langue: (libellé, explication)}]


def _load_ref(raw):
    codes = {c for c, _ in LANGS}
    cur = None
    for line in raw.strip().splitlines():
        line = line.rstrip()
        if line.startswith("["):
            name, _, cat = line[1:].partition("] ")
            cur = [name, cat.strip(), "", {}]
            REF.append(cur)
        elif cur is not None and line.startswith("ex "):
            cur[2] = line[3:].replace("\\n", "\n")
        elif cur is not None and line[:2] in codes and line[2:3] == " ":
            label, _, desc = line[3:].partition("|")
            cur[3][line[:2]] = (label.strip(), desc.strip())


_load_ref(REF_RAW)


def _norm(text):
    """Minuscules sans accents : la recherche ignore la casse et les accents."""
    t = unicodedata.normalize("NFKD", str(text)).casefold()
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def search_reference(query, lang, cat=None):
    """Cherche dans l'aide Python : nom, texte de la langue choisie ET texte anglais (toujours)."""
    q = _norm(query).strip()
    out = []
    for name, c, ex, texts in REF:
        if cat and c != cat:
            continue
        if q:
            hay = [name]
            for code in {lang, "en"}:
                hay += list(texts.get(code, ()))
            if not any(q in _norm(h) for h in hay):
                continue
        out.append((name, c, ex, texts))
    return out


class TMenu(QMenu):
    """Menu dont les libellés connus sont traduits automatiquement."""

    def addAction(self, *args):
        args = list(args)
        for i, a in enumerate(args):
            if isinstance(a, str):
                args[i] = tr(a)
                break
        return super().addAction(*args)

    def addMenu(self, *args):
        if args and isinstance(args[0], str):
            sub = TMenu(tr(args[0]), self)
            super().addMenu(sub)
            return sub
        return super().addMenu(*args)


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
FLOW_KINDS = {
    "prog":  dict(label="Programme", color="#3b82f6"),
    "doc":   dict(label="Document",  color="#84cc16"),
    "value": dict(label="Valeur",    color="#a855f7"),
    "show":  dict(label="Afficher",  color="#06b6d4"),
}
FLOW_ENTRY = "@flux"  # nom interne du « Flux du projet » (peut être le point d'entrée du projet)

DEFAULTS = {
    "start": {"params": "", "outputs": ""}, "end": {"value": ""},
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
    "prog": {"program": ""},
    "doc": {"path": "documents/notes.txt", "mode": "Écraser"},
    "value": {"expr": '"Alice"'},
    "show": {"label": ""},
}
# (clé, libellé, type de champ[, options])  — types : line, code, doc, prog, lib, choice
FIELDS = {
    "start": [("params", "Entrées du programme (ex : nom, age)", "line"),
              ("outputs", "Sorties du programme = variables retournées (ex : total, message)", "line")],
    "end": [("value", "Valeur retournée (vide = les sorties déclarées dans « Début »)", "line")],
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
    # éléments du « Flux du projet »
    "prog": [("program", "Programme à exécuter", "prog")],
    "doc": [("path", "Document", "doc"),
            ("mode", "Si une valeur est envoyée dans le document", "choice", ["Écraser", "Ajouter à la fin"])],
    "value": [("expr", 'Valeur (expression Python, ex : "Alice" ou 3)', "line")],
    "show": [("label", "Libellé affiché devant la valeur (optionnel)", "line")],
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


def unique_py_names(stems, reserved=("flux",)):
    used, out = set(reserved), {}
    for s in stems:
        base = py_name(s)
        n, i = base, 2
        while n in used:
            n = f"{base}_{i}"
            i += 1
        used.add(n)
        out[s] = n
    return out


class L(str):
    """Ligne de code Python qui mémorise le bloc (nid) dont elle provient."""

    def __new__(cls, text="", nid=None):
        obj = super().__new__(cls, text)
        obj.nid = nid
        return obj


def ind(lines):
    return [L(("    " + ln) if ln else str(ln), getattr(ln, "nid", None)) for ln in lines]


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


def split_names(raw):
    return [x.strip() for x in str(raw or "").split(",") if x.strip()]


def interface_of(data):
    """(entrées, sorties) déclarées dans le bloc « Début » d'un programme."""
    g = Graph(data)
    s = g.start()
    if s is None:
        return [], []
    p = g.params(s)
    return split_names(p.get("params")), split_names(p.get("outputs"))


def generate_body(data, call_expr):
    """Transforme un programme (dict JSON) en corps de fonction Python.

    call_expr(nom_programme) -> expression Python qui appelle ce programme.
    Chaque ligne produite (classe L) mémorise son bloc d'origine (mise en évidence).
    """
    g = Graph(data)
    res = dict(body=[], params=[], outputs=[], imports=set(), import_nodes={}, modules=set(),
               needs_doc=False, calls=set(), warnings=[], start=None)
    start = g.start()
    if start is None:
        res["warnings"].append("Aucun bloc « Début ».")
        return res
    res["start"] = start
    if sum(1 for d in g.nodes.values() if d["kind"] == "start") > 1:
        res["warnings"].append("Plusieurs blocs « Début » : seul le premier est utilisé.")
    reach = g.reach(start)
    ignored = [n for n in g.nodes if n not in reach]
    if ignored:
        res["warnings"].append(f"{len(ignored)} bloc(s) non relié(s) au Début : ignoré(s).")

    sp = g.params(start)
    for name in split_names(sp.get("params")):
        if name.isidentifier():
            res["params"].append(name)
        else:
            res["warnings"].append(f"Entrée invalide dans « Début » : « {name} ».")
    for name in split_names(sp.get("outputs")):
        if name.isidentifier():
            res["outputs"].append(name)
        else:
            res["warnings"].append(f"Sortie invalide dans « Début » : « {name} ».")
    ret = ", ".join(res["outputs"])

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

        def add(text):
            out.append(L(text, node))

        def add_import(line):
            res["imports"].add(line)
            res["import_nodes"].setdefault(line, node)

        while node is not None and node not in stop:
            k, p = g.kind(node), g.params(node)
            if k != "import" and (p.get("comment") or "").strip():
                add("# " + " ".join(p["comment"].split()))
            cont = g.nxt(node)
            if k == "print":
                add(f"print({p.get('expr', '').strip()})")
            elif k == "var":
                add(f"{ident(p.get('name'), k)} = {p.get('expr', '').strip() or 'None'}")
            elif k == "input":
                add(f"{ident(p.get('name'), k)} = input({p.get('prompt', '')!r})")
            elif k == "append":
                add(f"{p.get('list', '').strip() or 'liste'}.append({p.get('value', '').strip() or 'None'})")
            elif k == "random":
                add_import("import random")
                lib("random")
                add(f"{ident(p.get('name'), k)} = random.randint("
                    f"{p.get('min', '').strip() or '1'}, {p.get('max', '').strip() or '6'})")
            elif k == "now":
                add_import("import datetime")
                lib("datetime")
                add(f"{ident(p.get('name'), k)} = datetime.datetime.now()"
                    f".strftime({p.get('fmt', '') or '%d/%m/%Y %H:%M:%S'!r})")
            elif k == "sleep":
                add_import("import time")
                lib("time")
                add(f"time.sleep({p.get('seconds', '').strip() or '0'})")
            elif k == "import":
                mod = p.get("module", "").strip()
                alias, names = p.get("alias", "").strip(), p.get("names", "").strip()
                if not mod:
                    res["warnings"].append("Un bloc « Importer » n'a pas de bibliothèque.")
                else:
                    lib(mod)
                    if names:
                        add_import(f"from {mod} import {names}")
                    elif alias:
                        add_import(f"import {mod} as {alias}")
                    else:
                        add_import(f"import {mod}")
            elif k == "call":
                target = p.get("program", "").strip()
                if not target:
                    res["warnings"].append("Un bloc « Appeler un programme » n'a pas de programme choisi.")
                    add("pass")
                else:
                    res["calls"].add(target)
                    expr = f"{call_expr(target)}({p.get('args', '').strip()})"
                    rv = p.get("result", "").strip()
                    add(f"{ident(rv, k)} = {expr}" if rv else expr)
            elif k == "readfile":
                res["needs_doc"] = True
                path = p.get("path", "").strip()
                if not path:
                    res["warnings"].append("Un bloc « Lire un document » n'a pas de chemin.")
                name = ident(p.get("name"), k)
                add('with open(_doc(%r), encoding="utf-8") as _f:' % path)
                if p.get("mode", "").startswith("Liste"):
                    add(f"    {name} = _f.read().splitlines()")
                else:
                    add(f"    {name} = _f.read()")
            elif k == "writefile":
                res["needs_doc"] = True
                path = p.get("path", "").strip()
                if not path:
                    res["warnings"].append("Un bloc « Écrire un document » n'a pas de chemin.")
                mode = "a" if p.get("mode", "").startswith("Ajouter") else "w"
                add("os.makedirs(os.path.dirname(_doc(%r)), exist_ok=True)" % path)
                add('with open(_doc(%r), %r, encoding="utf-8") as _f:' % (path, mode))
                add(f"    _f.write(str({p.get('expr', '').strip() or chr(34) * 2}))")
            elif k == "code":
                code = textwrap.dedent(p.get("code", "")).strip("\n")
                for m in re.finditer(r"^\s*(?:from|import)\s+([A-Za-z_]\w*)", code, re.M):
                    lib(m.group(1))
                for ln in (code.splitlines() or ["pass"]):
                    add(ln)
            elif k == "end":
                val = p.get("value", "").strip() or ret
                add(f"return {val}" if val else "return")
                cont = None
            elif k == "if":
                t, f = g.nxt(node, 0), g.nxt(node, 1)
                merge = first_common(t, f) if (t is not None and f is not None) else None
                st = (stop | {merge}) if merge is not None else stop
                add(f"if {p.get('cond', '').strip() or 'True'}:")
                out.extend(ind(gen(t, st, depth) or [L("pass", node)]))
                other = gen(f, st, depth)
                if other:
                    add("else:")
                    out.extend(ind(other))
                cont = merge
            elif k in ("repeat", "while", "foreach"):
                body, after = g.nxt(node, 0), g.nxt(node, 1)
                st = (stop | g.reach(after)) if after is not None else stop
                if k == "repeat":
                    add(f"for _i{depth} in range({p.get('count', '').strip() or '1'}):")
                elif k == "while":
                    add(f"while {p.get('cond', '').strip() or 'True'}:")
                else:
                    add(f"for {ident(p.get('var'), k)} in {p.get('iterable', '').strip() or '[]'}:")
                out.extend(ind(gen(body, st, depth + 1) or [L("pass", node)]))
                cont = after
            node = cont
        return out

    body = gen(start, set(), 0)
    if ret and not (body and str(body[-1]).startswith("return")):
        body.append(L("return " + ret, start))
    res["body"] = body
    return res


def generate_flow(data, call_expr, interface):
    """« Flux du projet » : programmes, documents, valeurs reliés (entrées/sorties multiples).

    interface(nom_programme) -> (entrées, sorties). Génère le script qui orchestre le tout.
    """
    res = dict(body=[], params=[], outputs=[], imports=set(), import_nodes={}, modules=set(),
               needs_doc=False, calls=set(), warnings=[], start=None)
    nodes = {d["id"]: d for d in data.get("nodes", []) if d.get("kind") in FLOW_KINDS and "id" in d}
    if not nodes:
        res["warnings"].append("Le flux est vide : ajoutez des programmes et des documents.")

    def params(nid):
        d = nodes[nid]
        p = dict(DEFAULTS.get(d["kind"], {}))
        p.update(d.get("params") or {})
        return p

    def ports(nid):
        k, p = nodes[nid]["kind"], params(nid)
        if k == "prog":
            name = str(p.get("program", "")).strip()
            ins, outs = interface(name) if name else ([], [])
        elif k == "doc":
            ins, outs = ["écrire"], ["contenu"]
        elif k == "value":
            ins, outs = [], ["valeur"]
        else:
            ins, outs = ["valeur"], []
        return list(ins), list(outs)

    cache = {nid: ports(nid) for nid in nodes}
    src_of, out_used = {}, set()
    deps = {nid: set() for nid in nodes}
    for e in data.get("edges", []):
        if len(e) != 4:
            continue
        a, ao, b, bi = e
        if a not in nodes or b not in nodes or a == b:
            continue
        if ao >= len(cache[a][1]) or bi >= len(cache[b][0]):
            continue
        src_of[(b, bi)] = (a, ao)
    for (b, _bi), (a, ao) in src_of.items():
        deps[b].add(a)
        out_used.add((a, ao))

    key = lambda nid: (nodes[nid].get("x", 0), nodes[nid].get("y", 0), nid)
    remaining, order = set(nodes), []
    while remaining:
        ready = sorted((n for n in remaining if not (deps[n] & remaining)), key=key)
        if not ready:
            res["warnings"].append("Le flux contient une boucle : certains éléments sont ignorés.")
            break
        order.append(ready[0])
        remaining.discard(ready[0])

    var = lambda nid, i: f"v{nid}_{i}"

    def arg(nid, i):
        src = src_of.get((nid, i))
        return var(*src) if src else "None"

    for nid in order:
        k, p = nodes[nid]["kind"], params(nid)
        ins, outs = cache[nid]

        def add(text, nid=nid):
            res["body"].append(L(text, nid))

        if k == "value":
            add(f"{var(nid, 0)} = {str(p.get('expr', '')).strip() or 'None'}")
        elif k == "prog":
            name = str(p.get("program", "")).strip()
            if not name:
                res["warnings"].append("Un élément « Programme » n'a pas de programme choisi.")
                continue
            res["calls"].add(name)
            add(f"# Programme « {name} »")
            call = f"{call_expr(name)}({', '.join(arg(nid, i) for i in range(len(ins)))})"
            if not outs:
                add(call)
            elif len(outs) == 1:
                add(f"{var(nid, 0)} = {call}")
            else:
                add(f"{', '.join(var(nid, i) for i in range(len(outs)))} = {call}")
        elif k == "doc":
            path = str(p.get("path", "")).strip()
            if not path:
                res["warnings"].append("Un élément « Document » n'a pas de chemin.")
                continue
            res["needs_doc"] = True
            wrote, read = (nid, 0) in src_of, (nid, 0) in out_used
            if not wrote and not read:
                res["warnings"].append(f"Le document « {path} » n'est relié à rien.")
            if wrote:
                mode = "a" if str(p.get("mode", "")).startswith("Ajouter") else "w"
                add("os.makedirs(os.path.dirname(_doc(%r)), exist_ok=True)" % path)
                add('with open(_doc(%r), %r, encoding="utf-8") as _f:' % (path, mode))
                add(f"    _f.write(str({arg(nid, 0)}))")
            if read:
                add('with open(_doc(%r), encoding="utf-8") as _f:' % path)
                add(f"    {var(nid, 0)} = _f.read()")
        elif k == "show":
            label = str(p.get("label", "")).strip()
            if (nid, 0) not in src_of:
                res["warnings"].append("Un élément « Afficher » n'a rien en entrée.")
            add(f"print({label!r}, {arg(nid, 0)})" if label else f"print({arg(nid, 0)})")
    return res


def signature(res):
    return ", ".join(f"{n}=None" for n in res["params"])


def assemble_module(name, res, names):
    """Un programme -> un fichier .py autonome. Retourne (code, correspondance ligne -> bloc)."""
    imports = set(res["imports"])
    if res["needs_doc"]:
        imports |= {"import os", "import sys"}
    title = "Flux du projet" if name == FLOW_ENTRY else f"Programme « {name} »"
    inodes = res.get("import_nodes", {})
    head = [L(f"# {title} — généré par Code Node")]
    head += [L(line, inodes.get(line)) for line in sorted(imports)]
    for c in sorted(res["calls"]):
        if c != name:
            head.append(L(f"import {names.get(c) or py_name(c)}"))
    start = res.get("start")
    sections = [head]
    if res["needs_doc"]:
        sections.append([L(x) for x in DOC_HELPER])
    sections.append([L(f"def main({signature(res)}):", start)] + ind(res["body"] or [L("pass", start)]))
    sections.append([L('if __name__ == "__main__":'), L("    main()")])
    lines = []
    for i, sec in enumerate(sections):
        if i:
            lines += [L(""), L("")]
        lines += sec
    return "\n".join(lines) + "\n", [getattr(x, "nid", None) for x in lines]


def module_source(name, data, names, flow_interface=None):
    """Retourne (code, résultat de génération, correspondance ligne -> bloc)."""
    names = dict(names)
    names.setdefault(FLOW_ENTRY, "flux")

    def call_expr(target):
        return "main" if target == name else f"{names.get(target) or py_name(target)}.main"

    if name == FLOW_ENTRY:
        res = generate_flow(data, call_expr, flow_interface or (lambda n: ([], [])))
    else:
        res = generate_body(data, call_expr)
    code, linemap = assemble_module(name, res, names)
    return code, res, linemap


def compile_modules(entry_name, entry_data, get_data, names, flow_interface=None):
    """Génère le programme d'entrée + tous les programmes qu'il appelle (un fichier chacun)."""
    names = dict(names)
    names.setdefault(FLOW_ENTRY, "flux")
    files, warnings, seen = {}, [], set()
    queue = [(entry_name, entry_data)]
    while queue:
        n, data = queue.pop()
        if n in seen:
            continue
        seen.add(n)
        code, res, _lm = module_source(n, data, names, flow_interface)
        files[(names.get(n) or py_name(n)) + ".py"] = code
        label = "Flux" if n == FLOW_ENTRY else n
        warnings += [f"[{label}] {w}" for w in res["warnings"]]
        for c in sorted(res["calls"]):
            if c in seen:
                continue
            d = get_data(c)
            if d is None:
                warnings.append(f"[{label}] Programme « {c} » introuvable.")
            else:
                queue.append((c, d))
    return files, warnings, (names.get(entry_name) or py_name(entry_name)) + ".py"


def compile_bundle(main_name, get_data, names, flow_interface=None):
    """Fusionne le point d'entrée et tous les programmes appelés en UN SEUL fichier .py."""
    names = dict(names)
    names.setdefault(FLOW_ENTRY, "flux")
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
        if n == FLOW_ENTRY:
            res = generate_flow(data, call_expr, flow_interface or (lambda x: ([], [])))
        else:
            res = generate_body(data, call_expr)
        results[n] = res
        label = "Flux" if n == FLOW_ENTRY else n
        warnings += [f"[{label}] {w}" for w in res["warnings"]]
        stack.extend(sorted(res["calls"], reverse=True))
    order = [n for n in results if n != main_name] + ([main_name] if main_name in results else [])
    imports, needs_doc = set(), False
    for n in order:
        imports |= results[n]["imports"]
        needs_doc = needs_doc or results[n]["needs_doc"]
    if needs_doc:
        imports |= {"import os", "import sys"}
    sections = ["\n".join(["# Projet complet : tous les programmes fusionnés en un seul fichier",
                           "# Généré par Code Node"] + sorted(imports))]
    if needs_doc:
        sections.append("\n".join(DOC_HELPER))
    for n in missing:
        fn = call_expr(n)
        sections.append(f"def {fn}(*args, **kwargs):\n    raise NotImplementedError({('Programme ' + n + ' introuvable')!r})")
    for n in order:
        r = results[n]
        fn = call_expr(n)
        title = "Flux du projet" if n == FLOW_ENTRY else f"Programme « {n} »"
        sections.append("\n".join([f"# --- {title} ---", f"def {fn}({signature(r)}):"]
                                  + ind(r["body"] or ["pass"])))
    if main_name in results:
        sections.append(f'if __name__ == "__main__":\n    {call_expr(main_name)}()')
    return "\n\n\n".join(sections) + "\n", warnings


def error_span(e, lines, shift_l=0, shift_c=0):
    """(ligne0, colonne_début, colonne_fin) d'une SyntaxError, recadrées sur les lignes affichées."""
    n = len(lines)
    line = min(max((e.lineno or 1) - 1 - shift_l, 0), max(n - 1, 0))
    c0 = max((e.offset or 1) - 1 - shift_c, 0)
    c1 = (getattr(e, "end_offset", None) or 0) - 1 - shift_c
    if getattr(e, "end_lineno", None) not in (None, e.lineno):  # erreur sur plusieurs lignes
        c1 = len(lines[line]) if line < n else c0 + 1
    elif c1 <= c0:
        c1 = c0 + 1
    return line, c0, c1


def check_code_syntax(code):
    """Vérifie un extrait de code (bloc « Code Python »). None si correct, sinon (ligne0, col0, col1, message).

    L'extrait est vérifié comme s'il se trouvait dans une fonction : « return » y est donc permis."""
    lines = textwrap.dedent(code).splitlines() or ["pass"]
    src = "def _f():\n" + "\n".join("    " + ln for ln in lines) + "\n"
    try:
        compile(src, "<code>", "exec")
        return None
    except SyntaxError as e:
        line, c0, c1 = error_span(e, lines, shift_l=1, shift_c=4)
        return line, c0, c1, e.msg


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
        ("start", dict(params="nom", outputs="message"), 0, 0),
        ("var", dict(name="message", expr='"Bonjour " + str(nom) + " !"'), 280, 0),
        ("end", {}, 560, 0),
    ], [(0, 0, 1), (1, 0, 2)])
    for name, graph in (("principal", principal), ("utilitaires", utilitaires)):
        (root / "programmes" / f"{name}.json").write_text(
            json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    flux = {"version": 1, "nodes": [
        dict(id=1, kind="value", params=dict(expr='"Alice"'), x=0, y=0),
        dict(id=2, kind="prog", params=dict(program="utilitaires"), x=320, y=0),
        dict(id=3, kind="show", params=dict(label="Message"), x=680, y=-60),
        dict(id=4, kind="doc", params=dict(path="documents/journal.txt", mode="Ajouter à la fin"), x=680, y=80),
        dict(id=5, kind="doc", params=dict(path="documents/notes.txt"), x=0, y=240),
        dict(id=6, kind="show", params=dict(label="Notes"), x=320, y=240),
    ], "edges": [[1, 0, 2, 0], [2, 0, 3, 0], [2, 0, 4, 0], [5, 0, 6, 0]]}
    (root / "flux.json").write_text(json.dumps(flux, indent=2, ensure_ascii=False), encoding="utf-8")
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
        ins, outs = g("params"), g("outputs")
        if ins or outs:
            return f"{ins or '()'} → {outs or '()'}"
        return tr("Point de départ du programme")
    if kind == "end":
        return tr("retourner {}").format(g("value")) if g("value") else tr("Termine le programme")
    if kind == "print":
        return f"print({g('expr')})"
    if kind == "var":
        return f"{g('name')} = {g('expr')}"
    if kind == "input":
        return f"{g('name')} = input(…)"
    if kind == "append":
        return f"{g('list')}.append({g('value')})"
    if kind == "random":
        return f"{g('name')} = " + tr("aléatoire({} à {})").format(g("min"), g("max"))
    if kind == "now":
        return f"{g('name')} = " + tr("date et heure")
    if kind == "if":
        return tr("si {}").format(g("cond"))
    if kind == "repeat":
        return tr("répéter {} fois").format(g("count"))
    if kind == "while":
        return tr("tant que {}").format(g("cond"))
    if kind == "foreach":
        return tr("pour {} dans {}").format(g("var"), g("iterable"))
    if kind == "sleep":
        return tr("attendre {} s").format(g("seconds"))
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

    def __init__(self, kind, params, node_id, label=None, color=None, ins=None, outs=None):
        super().__init__()
        self.id, self.kind = node_id, kind
        self.params = dict(DEFAULTS.get(kind, {}))
        self.params.update(params or {})
        self.params.setdefault("comment", "")
        self.label, self.color = label, color
        self.flow = kind in FLOW_KINDS
        if self.flow:  # élément du « Flux du projet » : entrées/sorties en nombre quelconque
            self.in_labels, self.out_labels = list(ins or []), list(outs or [])
            self.H = 44 + 24 * max(len(self.in_labels), len(self.out_labels), 1)
        else:
            spec = BLOCKS[kind]
            self.in_labels = [""] if spec.get("has_in", True) else []
            self.out_labels = list(spec["outs"])
            self.H = 96 if kind == "code" else (104 if len(self.out_labels) >= 2 else 76)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable
                      | QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(1)
        self.in_ports = [self._make_port(False, i, lab) for i, lab in enumerate(self.in_labels)]
        self.out_ports = [self._make_port(True, i, lab) for i, lab in enumerate(self.out_labels)]

    def _make_port(self, is_output, i, label):
        port = Port(self, is_output, i, label)
        if self.flow:
            y = 48 + 24 * i
        elif is_output and len(self.out_labels) >= 2:
            y = 66 + 24 * i
        else:
            y = 28 + (self.H - 28) / 2
        port.setPos(self.W if is_output else 0, y)
        return port

    @property
    def in_port(self):
        return self.in_ports[0] if self.in_ports else None

    def all_ports(self):
        return self.in_ports + self.out_ports

    def boundingRect(self):
        return QRectF(-8, -14, self.W + 20, self.H + 24)

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

    def flow_title(self):
        k, pr = self.kind, self.params
        if k == "prog":
            return str(pr.get("program", "")).strip() or tr("(choisir un programme)")
        if k == "doc":
            return Path(str(pr.get("path", ""))).name or tr("(choisir un document)")
        if k == "value":
            return str(pr.get("expr", "")).strip()
        return str(pr.get("label", "")).strip()

    def paint_flow(self, p):
        th = self.scene().theme
        p.setRenderHint(QPainter.Antialiasing)
        sel = self.isSelected()
        body = QPainterPath()
        body.addRoundedRect(QRectF(0, 0, self.W, self.H), th.get("radius", 12), th.get("radius", 12))
        p.setPen(self.outline_pen(th, sel))
        p.setBrush(QColor(th["surface"]))
        p.drawPath(body)
        spec = FLOW_KINDS[self.kind]
        color = QColor(self.color or spec["color"])
        p.save()
        p.setClipPath(body)
        p.fillRect(QRectF(0, 0, self.W, 26), color)
        p.restore()
        f = QFont(p.font())
        f.setPointSize(8)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(contrast_text(color.name())))
        p.drawText(QRectF(12, 0, 90, 26), int(Qt.AlignVCenter | Qt.AlignLeft), tr(spec["label"]).upper())
        f.setPointSize(9)
        p.setFont(f)
        title = QFontMetrics(f).elidedText(self.flow_title(), Qt.ElideRight, int(self.W - 120))
        p.drawText(QRectF(100, 0, self.W - 112, 26), int(Qt.AlignVCenter | Qt.AlignRight), title)
        f.setBold(False)
        p.setFont(f)
        fm = QFontMetrics(f)
        p.setPen(QColor(th["text"]))
        half = int(self.W / 2 - 24)
        for i, lab in enumerate(self.in_labels):
            p.drawText(QRectF(14, 48 + 24 * i - 11, self.W / 2 - 20, 22),
                       int(Qt.AlignVCenter | Qt.AlignLeft), fm.elidedText(lab, Qt.ElideRight, half))
        for i, lab in enumerate(self.out_labels):
            p.drawText(QRectF(self.W / 2 + 6, 48 + 24 * i - 11, self.W / 2 - 20, 22),
                       int(Qt.AlignVCenter | Qt.AlignRight), fm.elidedText(lab, Qt.ElideRight, half))
        if not self.in_labels and not self.out_labels:
            p.setPen(QColor(th["muted"]))
            p.drawText(QRectF(14, 37, self.W - 28, 22), int(Qt.AlignVCenter | Qt.AlignLeft),
                       tr("Aucune entrée / sortie déclarée"))

    def outline_pen(self, th, sel):
        if self.id in getattr(self.scene(), "error_nodes", ()):
            return QPen(QColor("#ef4444"), 3.4)
        return QPen(QColor(th["accent"]) if sel else QColor(th["border"]), 2.6 if sel else 1.2)

    def paint_error_badge(self, p):
        if self.id not in getattr(self.scene(), "error_nodes", ()):
            return
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("white"), 1.5))
        p.setBrush(QColor("#ef4444"))
        p.drawEllipse(QPointF(self.W - 6, 6), 11, 11)
        f = QFont(p.font())
        f.setPointSize(10)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(self.W - 17, -5, 22, 22), int(Qt.AlignCenter), "!")

    def paint(self, p, option, widget=None):
        self.paint_block(p, option, widget)
        self.paint_error_badge(p)

    def paint_block(self, p, option=None, widget=None):
        if self.flow:
            self.paint_flow(p)
            return
        th = self.scene().theme
        p.setRenderHint(QPainter.Antialiasing)
        sel = self.isSelected()
        body = QPainterPath()
        body.addRoundedRect(QRectF(0, 0, self.W, self.H), th.get("radius", 12), th.get("radius", 12))
        p.setPen(self.outline_pen(th, sel))
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
                   QFontMetrics(f).elidedText((self.label or tr(BLOCKS[self.kind]["label"])).upper(),
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
                           int(Qt.AlignVCenter | Qt.AlignRight), tr(port.label))


class Edge(QGraphicsPathItem):
    def __init__(self, src, dst):
        super().__init__()
        self.src, self.dst = src, dst  # src = port de sortie, dst = port d'entrée
        src.edges.append(self)
        dst.edges.append(self)
        self.setZValue(0)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setPen(QPen(Qt.black, 8))
        self.dataflow = False
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
        elif self.dataflow:
            pen = QPen(QColor(th["accent"]), 2.8)
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


def red_selections(doc, line, c0, c1):
    """Erreur de syntaxe : toute la ligne en rouge clair + le mot fautif en rouge, souligné en vague."""
    block = doc.findBlockByNumber(line)
    if not block.isValid():
        return []
    red = QColor(239, 68, 68)
    line_bg = QColor(red)
    line_bg.setAlpha(70)
    fmt = QTextCharFormat()
    fmt.setBackground(line_bg)
    fmt.setProperty(QTextFormat.Property.FullWidthSelection, True)
    whole = QTextEdit.ExtraSelection()
    whole.format = fmt
    whole.cursor = QTextCursor(block)
    last = block.position() + max(block.length() - 1, 0)
    start = min(block.position() + c0, last)
    end = max(start, min(block.position() + c1, last))
    cur = QTextCursor(doc)
    cur.setPosition(start)
    cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    tok_bg = QColor(red)
    tok_bg.setAlpha(150)
    fmt2 = QTextCharFormat()
    fmt2.setBackground(tok_bg)
    fmt2.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
    fmt2.setUnderlineColor(red)
    token = QTextEdit.ExtraSelection()
    token.format = fmt2
    token.cursor = cur
    return [whole, token]


class CodeEdit(QPlainTextEdit):
    """Zone de code : police fixe, Tab = 4 espaces, indentation automatique."""

    def __init__(self, text="", read_only=False):
        super().__init__()
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        font.setPointSize(10)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._label = None
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

    def watch_syntax(self, label=None):
        """Surligne en rouge l'erreur de syntaxe pendant la frappe (blocs « Code Python »)."""
        self._label = label
        self.textChanged.connect(self._check_syntax)
        self._check_syntax()

    def _check_syntax(self):
        info = check_code_syntax(self.toPlainText())
        if info is None:
            self.setExtraSelections([])
            text, style = tr("✓ Code valide"), "color: gray;"
        else:
            line, c0, c1, msg = info
            self.setExtraSelections(red_selections(self.document(), line, c0, c1))
            text = tr("✗ Erreur de syntaxe ligne {} : {}").format(line + 1, msg)
            style = "color: #ef4444; font-weight: 600;"
        if self._label is not None:
            self._label.setText(text)
            self._label.setStyleSheet(style)


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
        self.error_nodes = set()  # blocs dont le code contient une erreur de syntaxe
        self.setSceneRect(-6000, -6000, 12000, 12000)
        self.graph_changed.connect(self.update_reachability)

    def nodes(self):
        return [i for i in self.items() if isinstance(i, Node)]

    def edges(self):
        return [i for i in self.items() if isinstance(i, Edge)]

    def drawBackground(self, p, rect):
        th = self.theme
        p.fillRect(rect, QColor(th["bg"]))
        if not th.get("grid", True):
            return
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


class FlowScene(NodeScene):
    """Scène du « Flux du projet » : programmes et documents reliés (entrées/sorties multiples)."""

    def __init__(self, theme, interface):
        super().__init__(theme)
        self.interface = interface  # nom de programme -> (entrées, sorties)

    def update_reachability(self):
        pass

    def ports_for(self, kind, params):
        if kind == "prog":
            name = str(params.get("program", "")).strip()
            ins, outs = self.interface(name) if name else ([], [])
            return list(ins), list(outs)
        if kind == "doc":
            return ["écrire"], ["contenu"]
        if kind == "value":
            return [], ["valeur"]
        return ["valeur"], []

    def create_node(self, kind, params, pos, node_id=None, label=None, color=None):
        ins, outs = self.ports_for(kind, params or {})
        node = Node(kind, params, node_id or self.next_id, label, color, ins, outs)
        self.next_id = max(self.next_id, node.id) + 1
        self.addItem(node)
        node.setPos(pos)
        return node

    def add_edge(self, out_port, in_port):
        edge = super().add_edge(out_port, in_port)
        edge.dataflow = True
        return edge

    def try_connect(self, a, b):
        if a.is_output == b.is_output:
            self.message.emit("Reliez une sortie (à droite) à une entrée (à gauche).")
            return
        out, inp = (a, b) if a.is_output else (b, a)
        if out.node is inp.node:
            self.message.emit("Un élément ne peut pas être relié à lui-même.")
        elif any(e.src is out for e in inp.edges):
            self.message.emit("Ces deux ports sont déjà reliés.")
        elif out.node in reachable_from(inp.node):
            self.message.emit("Liaison refusée : elle créerait une boucle dans le flux.")
        else:
            for old in list(inp.edges):  # une entrée n'a qu'une seule source : on remplace
                self.remove_edge(old)
            self.add_edge(out, inp)
            self.graph_changed.emit()

    def stale(self):
        """Vrai si l'interface d'un programme a changé depuis la création des ports."""
        for n in self.nodes():
            if n.kind == "prog":
                ins, outs = self.ports_for("prog", n.params)
                if ins != n.in_labels or outs != n.out_labels:
                    return True
        return False

    def rebuild(self):
        self.from_dict(self.to_dict())

    def to_dict(self):
        nodes = sorted(self.nodes(), key=lambda n: n.id)
        return {
            "version": 1,
            "nodes": [dict(id=n.id, kind=n.kind, params=dict(n.params), label=n.label, color=n.color,
                           x=n.pos().x(), y=n.pos().y()) for n in nodes],
            "edges": [[e.src.node.id, e.src.index, e.dst.node.id, e.dst.index] for e in self.edges()],
        }

    def from_dict(self, data):
        self.clear()
        self.next_id = 1
        by_id = {}
        for d in data.get("nodes", []):
            if d.get("kind") not in FLOW_KINDS:
                continue
            by_id[d["id"]] = self.create_node(
                d["kind"], d.get("params", {}), QPointF(float(d.get("x", 0)), float(d.get("y", 0))),
                int(d["id"]), d.get("label"), d.get("color"))
        for e in data.get("edges", []):
            if len(e) != 4:
                continue
            a, ao, b, bi = e
            if a in by_id and b in by_id and a != b:
                src, dst = by_id[a], by_id[b]
                if ao < len(src.out_ports) and bi < len(dst.in_ports) and src not in reachable_from(dst):
                    for old in list(dst.in_ports[bi].edges):
                        self.remove_edge(old)
                    self.add_edge(src.out_ports[ao], dst.in_ports[bi])
        self.graph_changed.emit()


class FlowTab(QWidget):
    """Onglet « Flux du projet »."""

    def __init__(self, theme, path, interface):
        super().__init__()
        self.name, self.path, self.dirty = tr("Flux du projet"), path, False
        self.scene = FlowScene(theme, interface)
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
            if ftype == "code":
                status = QLabel()
                status.setWordWrap(True)
                form.addRow("", status)
                w.watch_syntax(status)
        self.comment = QLineEdit(str(params.get("comment", "")))
        self.comment.setPlaceholderText("Optionnel : ajouté en commentaire dans le code")
        if kind not in FLOW_KINDS:
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
        code_status = QLabel()
        code_status.setWordWrap(True)
        form.addRow("", code_status)
        self.code.watch_syntax(code_status)
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
class SplashScreen(QWidget):
    """Écran de chargement affiché pendant l'ouverture de l'application."""

    def __init__(self):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint)
        self.setObjectName("Splash")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(480, 250)
        self.setStyleSheet(
            "#Splash { background: #1b1c23; border: 1px solid #3a3d52; }"
            "QLabel { color: #e8e9f0; background: transparent; }"
            "QProgressBar { background: #31344a; border: none; border-radius: 4px; max-height: 8px; }"
            "QProgressBar::chunk { background: #4c8dff; border-radius: 4px; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 36, 36, 30)
        title = QLabel("◆  Code Node")
        f = title.font()
        f.setPointSize(19)
        f.setBold(True)
        title.setFont(f)
        sub = QLabel("Python  ·  PySide6")
        sub.setStyleSheet("color: #8b8fa8;")
        self.status = QLabel(tr("Chargement…"))
        self.status.setStyleSheet("color: #8b8fa8;")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addStretch()
        lay.addWidget(self.status)
        lay.addWidget(self.bar)
        geo = QApplication.primaryScreen().availableGeometry()
        self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    def step(self, pct, text):
        self.bar.setValue(pct)
        self.status.setText(text)
        QApplication.processEvents()

    def finish_now(self):
        try:
            self.hide()
            self.close()
            self.deleteLater()
        except RuntimeError:  # déjà détruit
            pass


class SettingsTab(QWidget):
    """Onglet « Paramètres » : langue et apparence, avec une recherche dans les paramètres."""
    PAGES = ("Général", "Apparence")

    def __init__(self, win, search="", page=0):
        super().__init__()
        self.win = win
        self.name, self.path, self.dirty = tr("Paramètres"), None, False
        self.rows = []  # (page, ligne, texte français servant de clé de recherche)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(10)
        title = QLabel("⚙  " + tr("Paramètres"))
        f = title.font()
        f.setPointSize(f.pointSize() + 8)
        f.setBold(True)
        title.setFont(f)
        self.search = QLineEdit(search)
        self.search.setPlaceholderText(tr("Rechercher un paramètre…"))
        self.search.setClearButtonEnabled(True)
        hint = QLabel(tr("La recherche inclut toujours les termes anglais."))
        hint.setStyleSheet("color: gray;")
        self.found = QLabel("")
        self.found.setStyleSheet("color: gray;")
        self.sub = QTabWidget()
        self.sub.addTab(self.page_general(), tr("Général"))
        self.sub.addTab(self.page_appearance(), tr("Apparence"))
        root.addWidget(title)
        root.addWidget(self.search)
        root.addWidget(hint)
        root.addWidget(self.found)
        root.addWidget(self.sub, 1)
        self.search.textChanged.connect(self.on_search)
        if search:
            self.on_search(search)
        elif 0 <= page < len(self.PAGES):
            self.sub.setCurrentIndex(page)

    # ------------------------------------------------------------ outils
    def new_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 22, 24, 22)
        lay.setSpacing(18)
        return w, lay

    def row(self, lay, page, key, control, label=True):
        """Ajoute une ligne de réglage. `key` (texte français) sert à l'affichage ET à la recherche."""
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(16)
        if label:
            lab = QLabel(tr(key))
            lab.setMinimumWidth(280)
            lab.setWordWrap(True)
            h.addWidget(lab)
        if isinstance(control, QWidget):
            h.addWidget(control)
        else:
            h.addLayout(control)
        h.addStretch(1)
        lay.addWidget(box)
        self.rows.append((page, box, key))
        return box

    def words(self, key, page):
        """Textes dans lesquels la recherche s'applique : langue choisie, anglais, français, nom de la page."""
        out = [key, tr(key), tr(self.PAGES[page]), self.PAGES[page]]
        for k in (key, self.PAGES[page]):
            en = TR.get(k, {}).get("en")
            if en:
                out.append(en)
        return out

    def on_search(self, text):
        q = _norm(text).strip()
        counts = [0] * len(self.PAGES)
        for page, box, key in self.rows:
            ok = (not q) or any(q in _norm(w) for w in self.words(key, page))
            box.setVisible(ok)
            if ok:
                counts[page] += 1
        for i, c in enumerate(counts):
            self.sub.setTabVisible(i, c > 0 or not q)
        if not q:
            self.found.setText("")
            return
        total = sum(counts)
        self.found.setText(tr("{} paramètre(s) trouvé(s)").format(total) if total
                           else tr("Aucun paramètre trouvé."))
        first = next((i for i, c in enumerate(counts) if c), None)
        if first is not None and counts[self.sub.currentIndex()] == 0:
            self.sub.setCurrentIndex(first)

    # -------------------------------------------------------------- Général
    def page_general(self):
        w, lay = self.new_page()
        win = self.win
        self.lang_combo = QComboBox()
        for code, name in LANGS:
            self.lang_combo.addItem(name, code)
        self.lang_combo.setCurrentIndex([c for c, _ in LANGS].index(LANG))
        self.lang_combo.setMinimumWidth(220)
        self.lang_combo.currentIndexChanged.connect(
            lambda i: win.set_language(self.lang_combo.itemData(i)))
        self.row(lay, 0, "Langue de l'interface et de l'aide", self.lang_combo)
        snap = QCheckBox(tr("Aimanter les blocs à la grille"))
        snap.setChecked(win.snap)
        snap.toggled.connect(lambda on: win.a_snap.setChecked(on))
        self.row(lay, 0, "Aimanter les blocs à la grille", snap, label=False)
        con_box = QWidget()
        cv = QVBoxLayout(con_box)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(2)
        con = QCheckBox(tr("Masquer la fenêtre de commandes Windows (console)"))
        con.setChecked(bool(PREFS.get("hide_console", True)))
        con.setEnabled(sys.platform == "win32")
        con.toggled.connect(win.set_hide_console)
        con_note = QLabel(tr("S'applique au prochain démarrage."))
        con_note.setStyleSheet("color: gray; margin-left: 26px;")
        cv.addWidget(con)
        cv.addWidget(con_note)
        self.row(lay, 0, "Masquer la fenêtre de commandes Windows (console)", con_box, label=False)
        spl_box = QWidget()
        sv = QVBoxLayout(spl_box)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(2)
        spl = QCheckBox(tr("Afficher l'écran de chargement au démarrage"))
        spl.setChecked(bool(PREFS.get("splash", True)))
        spl.toggled.connect(lambda on: save_pref("splash", bool(on)))
        note = QLabel(tr("S'applique au prochain démarrage."))
        note.setStyleSheet("color: gray; margin-left: 26px;")
        sv.addWidget(spl)
        sv.addWidget(note)
        self.row(lay, 0, "Afficher l'écran de chargement au démarrage", spl_box, label=False)
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------ Apparence
    def page_appearance(self):
        w, lay = self.new_page()
        win = self.win
        self.theme_combo = QComboBox()
        for name in THEMES:
            self.theme_combo.addItem(tr(name), name)
        self.theme_combo.setCurrentIndex(list(THEMES).index(win.theme_name))
        self.theme_combo.setMinimumWidth(220)
        self.theme_combo.currentIndexChanged.connect(
            lambda i: win.set_theme(self.theme_combo.itemData(i)))
        self.row(lay, 1, "Thème", self.theme_combo)
        acc = QHBoxLayout()
        self.accent_btn = QPushButton(tr("Choisir…"))
        self.accent_btn.clicked.connect(self.pick_color_accent)
        b_def = QPushButton(tr("Par défaut"))
        b_def.setObjectName("Secondary")
        b_def.clicked.connect(lambda: win.set_accent(""))
        acc.addWidget(self.accent_btn)
        acc.addWidget(b_def)
        self.row(lay, 1, "Couleur d'accent", acc)
        self.refresh_accent_btn()
        self.row(lay, 1, "Taille du texte", self.slider_row(8, 16, win.font_size, win.set_font_size))
        self.row(lay, 1, "Arrondi des blocs", self.slider_row(2, 22, win.radius, win.set_radius))
        grid = QCheckBox(tr("Afficher la grille"))
        grid.setChecked(win.show_grid)
        grid.toggled.connect(win.set_grid)
        self.row(lay, 1, "Afficher la grille", grid, label=False)
        reset = QPushButton(tr("Réinitialiser l'apparence"))
        reset.setObjectName("Secondary")
        reset.clicked.connect(lambda: win.reset_appearance())
        self.row(lay, 1, "Réinitialiser l'apparence", reset, label=False)
        lay.addStretch(1)
        return w

    def slider_row(self, lo, hi, value, apply):
        box = QHBoxLayout()
        sl = QSlider(Qt.Horizontal)
        sl.setRange(lo, hi)
        sl.setValue(value)
        sl.setMinimumWidth(240)
        lbl = QLabel(str(value))
        lbl.setMinimumWidth(30)

        def changed(v):
            lbl.setText(str(v))
            if not sl.isSliderDown():
                apply(v)

        sl.valueChanged.connect(changed)
        sl.sliderReleased.connect(lambda: apply(sl.value()))
        box.addWidget(sl)
        box.addWidget(lbl)
        return box

    def refresh_accent_btn(self):
        c = self.win.theme_dict()["accent"]
        self.accent_btn.setStyleSheet(
            f"QPushButton {{ background: {c}; color: {contrast_text(c)}; }}")

    def pick_color_accent(self):
        c = QColorDialog.getColor(QColor(self.win.theme_dict()["accent"]), self)
        if c.isValid():
            self.win.set_accent(c.name())


class HelpTab(QWidget):
    """Onglet « Aide Python » : mots-clés et fonctions expliqués dans la langue choisie, avec recherche."""

    def __init__(self, win, search=""):
        super().__init__()
        self.win = win
        self.name, self.path, self.dirty = tr("Aide Python"), None, False
        self.results = []
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(10)
        title = QLabel("📖  " + tr("Aide Python"))
        f = title.font()
        f.setPointSize(f.pointSize() + 8)
        f.setBold(True)
        title.setFont(f)
        self.search = QLineEdit(search)
        self.search.setPlaceholderText(tr("Rechercher un mot-clé ou une fonction Python…"))
        self.search.setClearButtonEnabled(True)
        hint = QLabel(tr("La recherche inclut toujours les termes anglais."))
        hint.setStyleSheet("color: gray;")
        body = QHBoxLayout()
        body.setSpacing(14)
        left = QVBoxLayout()
        self.cat = QComboBox()
        for label, data in (("Tout", None), ("Mots-clés", "kw"), ("Fonctions", "fn")):
            self.cat.addItem(tr(label), data)
        self.cat.currentIndexChanged.connect(lambda _i: self.fill())
        self.count = QLabel()
        self.count.setStyleSheet("color: gray;")
        self.listw = QListWidget()
        self.listw.setIconSize(QSize(14, 14))
        self.listw.currentRowChanged.connect(self.show_detail)
        left.addWidget(self.cat)
        left.addWidget(self.count)
        left.addWidget(self.listw, 1)
        right = QVBoxLayout()
        self.d_title = QLabel()
        self.d_title.setTextFormat(Qt.RichText)
        self.d_desc = QLabel()
        self.d_desc.setWordWrap(True)
        f2 = self.d_desc.font()
        f2.setPointSize(f2.pointSize() + 2)
        self.d_desc.setFont(f2)
        self.d_ex_title = QLabel(tr("Exemple"))
        f3 = self.d_ex_title.font()
        f3.setBold(True)
        self.d_ex_title.setFont(f3)
        self.d_ex = CodeEdit(read_only=True)
        self.d_ex.setMaximumHeight(200)
        win.highlighters.append(PythonHighlighter(self.d_ex.document(), dark=is_dark()))
        right.addWidget(self.d_title)
        right.addWidget(self.d_desc)
        right.addSpacing(8)
        right.addWidget(self.d_ex_title)
        right.addWidget(self.d_ex)
        right.addStretch()
        body.addLayout(left, 2)
        body.addLayout(right, 3)
        root.addWidget(title)
        root.addWidget(self.search)
        root.addWidget(hint)
        root.addLayout(body, 1)
        self.search.textChanged.connect(lambda _t: self.fill())
        self.fill()

    def fill(self):
        res = search_reference(self.search.text(), LANG, self.cat.currentData())
        self.results = res
        self.listw.blockSignals(True)
        self.listw.clear()
        for name, cat, _ex, texts in res:
            label = (texts.get(LANG) or texts.get("en") or ("", ""))[0]
            it = QListWidgetItem(f"{name}   —   {label}" if label and label.lower() != name.lower() else name)
            it.setIcon(color_icon("#8b5cf6" if cat == "kw" else "#14b8a6", 14))
            self.listw.addItem(it)
        self.listw.blockSignals(False)
        self.count.setText(tr("{} résultat(s)").format(len(res)) if res else tr("Aucun résultat."))
        if res:
            self.listw.setCurrentRow(0)
        else:
            self.show_detail(-1)

    def show_detail(self, row):
        if row < 0 or row >= len(self.results):
            self.d_title.setText("")
            self.d_desc.setText(tr("Sélectionnez un élément pour voir son explication."))
            self.d_ex_title.hide()
            self.d_ex.hide()
            return
        name, cat, ex, texts = self.results[row]
        label, desc = texts.get(LANG) or texts.get("en") or ("", "")
        kind = tr("Mot-clé" if cat == "kw" else "Fonction")
        self.d_title.setText(
            f"<span style='font-size:22pt; font-weight:700'>{html.escape(name)}</span>"
            f" &nbsp;&nbsp; <span style='color:gray'>{html.escape(label)} · {html.escape(kind)}</span>")
        self.d_desc.setText(desc)
        self.d_ex.setPlainText(ex)
        self.d_ex_title.show()
        self.d_ex.show()


class MainWindow(QMainWindow):
    def __init__(self, splash=None):
        super().__init__()
        self.splash = splash
        self.settings = QSettings("DemoPySide", "EditeurCodeBlocsV2")
        self.theme_name = self.settings.value("theme", "Sombre", type=str)
        if self.theme_name not in THEMES:
            self.theme_name = "Sombre"
        self.accent = self.settings.value("accent", "", type=str)
        self.font_size = self.settings.value("font_size", 10, type=int)
        self.radius = self.settings.value("radius", 12, type=int)
        self.show_grid = self.settings.value("grid", True, type=bool)
        self.snap = self.settings.value("snap", True, type=bool)
        self._all_actions = []
        self._toolbar = None
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
        self._syncing = False
        self.linemap = []
        self.err = None  # (ligne, col début, col fin, message) de l'erreur de syntaxe affichée
        self._err_key = None

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.setCentralWidget(self.tabs)

        self.step(15, "Préparation de l'interface…")
        self.build_explorer_dock()
        self.build_palette_dock()
        self.build_code_dock()
        self.build_console_dock()
        self.build_actions()

        self.setWindowTitle("Code Node")
        self.resize(1600, 920)
        self.step(55, "Application du thème…")
        self.apply_theme()
        self.refresh_explorer()

        self.step(75, "Ouverture du projet…")
        last = self.settings.value("workspace", "", type=str)
        if last and (Path(last) / "programmes").is_dir():
            self.open_workspace(Path(last))
        else:
            self.open_untitled(example_graph())
        self.step(95, "Prêt !")

    # ------------------------------------------------ onglet courant
    @property
    def tab(self):
        w = self.tabs.currentWidget()
        if isinstance(w, (ProgramTab, FlowTab)):
            return w
        lp = self.last_prog
        return lp if (lp is not None and self.tabs.indexOf(lp) >= 0) else None

    def need_program(self):
        t = self.tab
        if t is None:
            self.statusBar().showMessage("Ouvrez ou créez d'abord un programme.", 5000)
        return t

    def msg(self, text, ms=6000):
        self.statusBar().showMessage(tr(text), ms)

    # --------------------------------------------------------------- thème
    def theme_dict(self):
        t = dict(THEMES[self.theme_name])
        if self.accent:
            t["accent"] = self.accent
        t["accent_text"] = contrast_text(t["accent"])
        t["accent_hover"] = QColor(t["accent"]).lighter(115).name()
        t["fs"], t["radius"], t["grid"] = self.font_size, self.radius, self.show_grid
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
QWidget {{ color: {t['text']}; font-family: "Segoe UI", Arial, sans-serif; font-size: {t['fs']}pt; }}
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
        alive = []
        for hl in self.highlighters:
            try:
                hl.set_dark(dark)
                alive.append(hl)
            except RuntimeError:  # coloration d'un onglet déjà fermé
                pass
        self.highlighters = alive
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, (ProgramTab, FlowTab)):
                w.scene.theme = t
                w.scene.update()
                w.view.viewport().update()

    def set_theme(self, name):
        self.theme_name = name
        self.settings.setValue("theme", name)
        self.apply_theme()
        self.sync_theme_widgets()

    # ---------------------------------------------------------------- docks
    # ------------------------------------------- chargement, réglages, langue
    def step(self, pct, text):
        if self.splash is not None:
            self.splash.step(pct, tr(text))

    def sync_theme_widgets(self):
        """Garde la liste de thèmes de la barre d'outils et l'onglet Paramètres à jour."""
        idx = list(THEMES).index(self.theme_name)
        combo = getattr(self, "theme_combo", None)
        if combo is not None:
            combo.blockSignals(True)
            combo.setCurrentIndex(idx)
            combo.blockSignals(False)
        st = self.find_settings_tab()
        if st is not None:
            st.theme_combo.blockSignals(True)
            st.theme_combo.setCurrentIndex(idx)
            st.theme_combo.blockSignals(False)
            st.refresh_accent_btn()

    def set_font_size(self, v):
        self.font_size = v
        self.settings.setValue("font_size", v)
        self.apply_theme()

    def set_radius(self, v):
        self.radius = v
        self.settings.setValue("radius", v)
        self.apply_theme()

    def set_grid(self, on):
        self.show_grid = on
        self.settings.setValue("grid", on)
        self.apply_theme()

    def set_accent(self, color):
        self.accent = color
        self.settings.setValue("accent", color)
        self.apply_theme()
        self.sync_theme_widgets()

    def reset_appearance(self):
        self.accent, self.font_size, self.radius, self.show_grid = "", 10, 12, True
        for key, value in (("accent", ""), ("font_size", 10), ("radius", 12), ("grid", True)):
            self.settings.setValue(key, value)
        self.apply_theme()
        self.sync_theme_widgets()
        QTimer.singleShot(0, self.reopen_settings)

    def set_hide_console(self, hide):
        save_pref("hide_console", bool(hide))
        console_window(not hide)

    def find_settings_tab(self):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, SettingsTab):
                return w
        return None

    def open_settings(self, search="", page=0):
        st = self.find_settings_tab()
        if st is not None:
            self.tabs.setCurrentWidget(st)
            if search:
                st.search.setText(search)
            elif 0 <= page < len(SettingsTab.PAGES):
                st.sub.setCurrentIndex(page)
            return
        st = SettingsTab(self, search, page)
        self.tabs.setCurrentIndex(self.tabs.addTab(st, "⚙  " + tr("Paramètres")))

    def find_help_tab(self):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, HelpTab):
                return w
        return None

    def open_help(self, search=""):
        """Ouvre l'aide Python (mots-clés et fonctions), éventuellement sur un mot précis."""
        ht = self.find_help_tab()
        if ht is not None:
            self.tabs.setCurrentWidget(ht)
            if search:
                ht.search.setText(search)
            return
        ht = HelpTab(self, search)
        self.tabs.setCurrentIndex(self.tabs.addTab(ht, "📖  " + tr("Aide Python")))

    def reopen_help(self):
        ht = self.find_help_tab()
        if ht is not None:
            search = ht.search.text()
            self.drop_tab(ht)
            self.open_help(search)

    def reopen_settings(self):
        st = self.find_settings_tab()
        if st is not None:
            page, search = st.sub.currentIndex(), st.search.text()
            self.drop_tab(st)
            self.open_settings(search, page)

    def set_language(self, code):
        if code == LANG:
            return
        set_language(code)
        save_pref("lang", code)
        QTimer.singleShot(0, self.apply_language_change)

    def apply_language_change(self):
        cur = self.tabs.currentWidget()
        was = ('settings' if isinstance(cur, SettingsTab) else 'help' if isinstance(cur, HelpTab) else None)
        self.build_actions()
        self.retranslate_widgets()
        self.refresh_palette()
        self.refresh_explorer()
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, FlowTab):
                w.name = tr("Flux du projet")
                self.update_tab_title(w)
            if isinstance(w, (ProgramTab, FlowTab)):
                w.scene.update()
        self.refresh_code()
        self.reopen_settings()
        self.reopen_help()
        target = {"settings": self.find_settings_tab, "help": self.find_help_tab}.get(was)
        if target is not None:
            w = target()
            if w is not None:
                self.tabs.setCurrentWidget(w)
        elif cur is not None and self.tabs.indexOf(cur) >= 0:
            self.tabs.setCurrentWidget(cur)

    def retranslate_widgets(self):
        self.setWindowTitle("Code Node" + (f" — {self.ws.name}" if self.ws else ""))
        self.explorer_dock.setWindowTitle(tr("Projet"))
        self.palette_dock.setWindowTitle(tr("Blocs"))
        self.console_dock.setWindowTitle(tr("Console"))
        self.btn_prog.setText(tr("＋ Programme"))
        self.btn_doc.setText(tr("＋ Document"))
        self.palette_hint.setText(tr("Double-clic ou glisser un bloc vers la zone de travail."))
        self.btn_tpl.setText(tr("＋ Modèle de bloc"))
        self.btn_folder.setText(tr("＋ Dossier"))
        self.btn_copy.setText(tr("Copier"))
        self.btn_export.setText(tr("Exporter .py"))
        self.stdin.setPlaceholderText(tr("Réponse envoyée au programme (Entrée) — pour les blocs « Saisie »"))

    def code_menu(self, pos):
        """Clic droit sur le code : explique le mot sous le curseur (aide Python)."""
        cur = self.code_view.cursorForPosition(pos)
        cur.select(QTextCursor.SelectionType.WordUnderCursor)
        word = cur.selectedText().strip()
        menu = TMenu(self)
        if word and any(r[0] == word or r[0].endswith("." + word) for r in REF):
            menu.addAction(tr("Expliquer « {} »").format(word)).triggered.connect(
                lambda _=False, w=word: self.open_help(w))
        menu.addAction("Copier").triggered.connect(lambda _=False: self.copy_code())
        menu.exec(self.code_view.viewport().mapToGlobal(pos))

    def build_explorer_dock(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        self.ws_label = QLabel(tr("Aucun projet ouvert"))
        f = self.ws_label.font()
        f.setBold(True)
        self.ws_label.setFont(f)
        self.explorer = DragTree()
        self.explorer.itemDoubleClicked.connect(self.explorer_open)
        self.explorer.setContextMenuPolicy(Qt.CustomContextMenu)
        self.explorer.customContextMenuRequested.connect(self.explorer_menu)
        row = QHBoxLayout()
        b1 = self.btn_prog = QPushButton(tr("＋ Programme"))
        b1.setObjectName("Secondary")
        b1.clicked.connect(lambda: self.new_program())
        b2 = self.btn_doc = QPushButton(tr("＋ Document"))
        b2.setObjectName("Secondary")
        b2.clicked.connect(lambda: self.new_doc("documents"))
        row.addWidget(b1)
        row.addWidget(b2)
        lay.addWidget(self.ws_label)
        lay.addWidget(self.explorer)
        lay.addLayout(row)
        self.explorer_dock = QDockWidget(tr("Projet"), self)
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
        hint = self.palette_hint = QLabel(tr("Double-clic ou glisser un bloc vers la zone de travail."))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")
        lay.addWidget(hint)
        lay.addWidget(self.palette_tree)
        row = QHBoxLayout()
        b1 = self.btn_tpl = QPushButton(tr("＋ Modèle de bloc"))
        b1.clicked.connect(lambda: self.new_template())
        b2 = self.btn_folder = QPushButton(tr("＋ Dossier"))
        b2.setObjectName("Secondary")
        b2.clicked.connect(lambda: self.new_user_folder())
        row.addWidget(b1)
        row.addWidget(b2)
        lay.addLayout(row)
        self.palette_dock = QDockWidget(tr("Blocs"), self)
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
        self.sel_label = QLabel()
        self.sel_label.setWordWrap(True)
        self.code_view = CodeEdit(read_only=True)
        self.highlighters.append(PythonHighlighter(self.code_view.document()))
        self.code_view.cursorPositionChanged.connect(self.on_code_cursor)
        self.code_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.code_view.customContextMenuRequested.connect(self.code_menu)
        row = QHBoxLayout()
        b_copy = self.btn_copy = QPushButton(tr("Copier"))
        b_copy.setObjectName("Secondary")
        b_copy.clicked.connect(self.copy_code)
        b_export = self.btn_export = QPushButton(tr("Exporter .py"))
        b_export.clicked.connect(lambda: self.export_py())
        row.addWidget(b_copy)
        row.addWidget(b_export)
        lay.addWidget(self.code_status)
        lay.addWidget(self.sel_label)
        lay.addWidget(self.code_view)
        lay.addLayout(row)
        self.code_dock = QDockWidget(tr("Code Python généré"), self)
        self.code_dock.setWidget(box)
        self.addDockWidget(Qt.RightDockWidgetArea, self.code_dock)
        self.resizeDocks([self.code_dock], [470], Qt.Horizontal)

    def build_console_dock(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        self.console = CodeEdit(read_only=True)
        self.stdin = QLineEdit()
        self.stdin.setPlaceholderText(tr("Réponse envoyée au programme (Entrée) — pour les blocs « Saisie »"))
        self.stdin.returnPressed.connect(self.send_input)
        lay.addWidget(self.console)
        lay.addWidget(self.stdin)
        self.console_dock = QDockWidget(tr("Console"), self)
        self.console_dock.setWidget(box)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.console_dock)
        self.resizeDocks([self.console_dock], [170], Qt.Vertical)
        self.append_console(tr("La sortie du programme s'affichera ici (F5 pour exécuter).") + "\n")

    def append_console(self, text):
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(text)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    # -------------------------------------------------------------- actions
    def act(self, text, slot, shortcut=None, checkable=False, checked=False):
        a = QAction(tr(text), self)
        self._all_actions.append(a)
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
        for old in self._all_actions:  # reconstruction (changement de langue)
            self.removeAction(old)
            old.deleteLater()
        self._all_actions = []
        self.menuBar().clear()
        if self._toolbar is not None:
            self.removeToolBar(self._toolbar)
            self._toolbar.deleteLater()
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
        a_runproj = A("▶▶  Exécuter le projet", self.run_project, "F6")
        a_fit = A("Tout afficher", self.fit_current, "F")
        a_reset = A("Zoom 100 %", self.reset_zoom, "Ctrl+0")
        a_snap = self.a_snap = A("Aimanter à la grille", self.set_snap, checkable=True, checked=self.snap)
        a_doc = A("Nouveau document texte", lambda: self.new_doc("documents"))
        a_import = A("Importer des fichiers dans le projet…", lambda: self.import_files("documents"))
        a_main = A("Définir comme programme principal", self.set_main_current)
        a_refresh = A("Actualiser l'explorateur", self.refresh_explorer)
        a_flow = A("🔀  Ouvrir le flux du projet", self.open_flow)
        a_libs = A("📚  Bibliothèques…", self.libraries_dialog)
        a_pip = A("Installer un paquet (pip)…", self.install_package)
        a_ex1 = A("Programme actuel (.py)…", self.export_py, "Ctrl+E")
        a_ex2 = A("Projet complet (dossier)…", self.export_project)
        a_ex3 = A("⇪  Tout en UN SEUL fichier (.py)…", self.export_bundle, "Ctrl+Shift+E")
        a_ex4 = A("Créer un exécutable (.exe)…", self.build_exe)
        a_settings = A("⚙  Paramètres…", self.open_settings, "Ctrl+,")
        a_help = A("📖  Aide Python…", self.open_help, "F1")
        for a in (a_openproj, a_newprog, a_openprog, a_save, a_saveall, a_dup, a_del, a_all, a_run,
                  a_stop, a_runproj, a_fit, a_reset, a_ex1, a_ex3):
            self.addAction(a)

        mb = self.menuBar()
        old_gear = mb.cornerWidget(Qt.TopRightCorner)
        if old_gear is not None:
            old_gear.deleteLater()
        gear = QPushButton("⚙  " + tr("Paramètres"))
        gear.setObjectName("Secondary")
        gear.setStyleSheet("padding: 3px 14px; margin: 2px 6px;")
        gear.setCursor(Qt.PointingHandCursor)
        gear.clicked.connect(lambda: self.open_settings())
        mb.setCornerWidget(gear, Qt.TopRightCorner)
        m = mb.addMenu("&" + tr("Fichier"))
        for a in (a_newproj, a_openproj):
            m.addAction(a)
        m.addSeparator()
        for a in (a_newprog, a_openprog, a_save, a_saveas, a_saveall):
            m.addAction(a)
        m.addSeparator()
        m.addAction(a_settings)
        m.addSeparator()
        m.addAction(a_quit)
        m = mb.addMenu("&" + tr("Projet"))
        for a in (a_flow, a_newprog, a_doc, a_import, a_main, a_refresh):
            m.addAction(a)
        m.addSeparator()
        m.addAction(a_libs)
        m.addAction(a_pip)
        m = mb.addMenu("&" + tr("Exporter"))
        for a in (a_ex1, a_ex2, a_ex3, a_ex4):
            m.addAction(a)
        m = mb.addMenu("&" + tr("Édition"))
        for a in (a_dup, a_del, a_all):
            m.addAction(a)
        m = mb.addMenu("&" + tr("Exécution"))
        m.addAction(a_run)
        m.addAction(a_runproj)
        m.addAction(a_stop)
        m = mb.addMenu("&" + tr("Affichage"))
        for a in (a_fit, a_reset):
            m.addAction(a)
        m.addSeparator()
        m.addAction(a_snap)
        m.addSeparator()
        for d in (self.explorer_dock, self.palette_dock, self.code_dock, self.console_dock):
            m.addAction(d.toggleViewAction())

        m = mb.addMenu("&" + tr("Aide"))
        m.addAction(a_help)
        tb = QToolBar("Principal")
        self._toolbar = tb
        tb.setMovable(False)
        self.addToolBar(tb)
        for a in (a_run, a_runproj, a_stop):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(a_save)
        tb.addAction(a_flow)
        tb.addAction(a_libs)
        tb.addAction(a_ex3)
        tb.addSeparator()
        tb.addAction(a_fit)
        tb.addAction(a_snap)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        tb.addAction(a_help)
        tb.addAction(a_settings)
        tb.addSeparator()
        tb.addWidget(QLabel(tr("Thème :") + "  "))
        combo = self.theme_combo = QComboBox()
        for name in THEMES:
            combo.addItem(tr(name), name)
        combo.setCurrentIndex(list(THEMES).index(self.theme_name))
        combo.currentIndexChanged.connect(lambda i, c=combo: self.set_theme(c.itemData(i)))
        tb.addWidget(combo)
        self.msg("Fichier ▸ Nouveau projet… pour créer un dossier de travail · glissez les blocs "
                 "depuis la liste · F5 : exécuter · ⚙ Paramètres : Ctrl+,", 15000)

    def set_snap(self, on):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, (ProgramTab, FlowTab)):
                w.scene.snap = on
        self.snap = on
        self.settings.setValue("snap", on)

    def reset_zoom(self):
        t = self.tab
        if t:
            t.view.resetTransform()

    # ------------------------------------------------- onglets / fichiers
    # ------------------------------------------------------ flux du projet
    def flow_path(self):
        return self.ws / "flux.json"

    def flow_data(self):
        if not self.ws:
            return None
        tab = self.open_tab_for(self.flow_path())
        if isinstance(tab, FlowTab):
            return tab.scene.to_dict()
        try:
            return json.loads(self.flow_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"nodes": [], "edges": []}

    def program_interface(self, name):
        """(entrées, sorties) d'un programme, d'après son bloc « Début »."""
        data = self.program_data(name) if name else None
        return interface_of(data) if data else ([], [])

    def open_flow(self):
        if not self.ws:
            self.msg("Le flux du projet nécessite un projet ouvert (Fichier ▸ Nouveau projet…).")
            return
        path = self.flow_path()
        existing = self.open_tab_for(path)
        if existing:
            self.tabs.setCurrentWidget(existing)
            return
        try:
            data = (json.loads(path.read_text(encoding="utf-8")) if path.exists()
                    else {"nodes": [], "edges": []})
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Erreur", f"Flux illisible :\n{e}")
            return
        tab = FlowTab(self.theme_dict(), path, self.program_interface)
        tab.scene.snap = getattr(self, "snap", True)
        tab.scene.from_dict(data)
        self.register_tab(tab, tab.name)

    def save_flow(self, tab):
        try:
            tab.path.write_text(json.dumps(tab.scene.to_dict(), indent=2, ensure_ascii=False),
                                encoding="utf-8")
        except OSError as e:
            QMessageBox.critical(self, "Erreur", f"Enregistrement impossible :\n{e}")
            return False
        self.set_dirty(tab, False)
        self.msg("Flux du projet enregistré", 4000)
        return True

    def add_flow_node(self, tab, kind, pos, params=None):
        n = tab.scene.create_node(kind, params or {}, pos)
        tab.scene.clearSelection()
        n.setSelected(True)
        tab.scene.graph_changed.emit()

    def flow_context_menu(self, tab, pos):
        item = tab.view.itemAt(pos)
        node = find_node(item)
        sp = tab.view.mapToScene(pos)
        menu = TMenu(self)
        if node is not None:
            if not node.isSelected():
                tab.scene.clearSelection()
                node.setSelected(True)
            menu.addAction("Modifier…").triggered.connect(lambda _=False, n=node: self.edit_node(tab, n))
            if node.kind == "prog" and str(node.params.get("program", "")).strip():
                menu.addAction("Ouvrir ce programme").triggered.connect(
                    lambda _=False, n=node: self.open_program(n.params["program"]))
            menu.addAction("Dupliquer").triggered.connect(lambda _=False: self.duplicate_selected())
            menu.addSeparator()
            menu.addAction("Supprimer").triggered.connect(lambda _=False: self.delete_selected())
        elif isinstance(item, Edge):
            tab.scene.clearSelection()
            item.setSelected(True)
            menu.addAction("Supprimer la liaison").triggered.connect(lambda _=False: self.delete_selected())
        else:
            at = QPointF(sp.x() - Node.W / 2, sp.y() - 30)
            sub = menu.addMenu("Programme")
            progs = self.program_names()
            for name in progs:
                sub.addAction(color_icon(FLOW_KINDS["prog"]["color"]), name).triggered.connect(
                    lambda _=False, n=name, p=at: self.add_flow_node(tab, "prog", p, {"program": n}))
            if not progs:
                sub.addAction("(aucun programme)").setEnabled(False)
            sub = menu.addMenu("Document")
            docs = self.doc_files()
            for rel in docs:
                sub.addAction(color_icon(FLOW_KINDS["doc"]["color"]), rel).triggered.connect(
                    lambda _=False, r=rel, p=at: self.add_flow_node(tab, "doc", p, {"path": r}))
            if not docs:
                sub.addAction("(aucun document)").setEnabled(False)
            menu.addAction(color_icon(FLOW_KINDS["value"]["color"]), "Valeur").triggered.connect(
                lambda _=False, p=at: self.add_flow_node(tab, "value", p))
            menu.addAction(color_icon(FLOW_KINDS["show"]["color"]), "Afficher").triggered.connect(
                lambda _=False, p=at: self.add_flow_node(tab, "show", p))
        menu.exec(tab.view.viewport().mapToGlobal(pos))

    # ----------------------------------------- code <-> blocs (mise en évidence)
    def apply_highlight(self, move=True):
        """Surligne dans la feuille de code les lignes des blocs sélectionnés."""
        t = self.tab
        nodes = [] if t is None else [n for n in t.scene.selectedItems() if isinstance(n, Node)]
        ids = {n.id for n in nodes}
        doc = self.code_view.document()
        color = QColor(self.theme_dict()["accent"])
        color.setAlpha(110)
        sels, first, last = [], None, None
        for i, nid in enumerate(self.linemap):
            if nid is None or nid not in ids:
                continue
            block = doc.findBlockByNumber(i)
            if not block.isValid():
                continue
            fmt = QTextCharFormat()
            fmt.setBackground(color)
            fmt.setProperty(QTextFormat.Property.FullWidthSelection, True)
            sel = QTextEdit.ExtraSelection()
            sel.format = fmt
            sel.cursor = QTextCursor(block)
            sels.append(sel)
            first = i if first is None else first
            last = i
        if self.err is not None:  # l'erreur de syntaxe passe en dernier : le rouge reste visible
            sels.extend(red_selections(doc, self.err[0], self.err[1], self.err[2]))
        self.code_view.setExtraSelections(sels)
        if not nodes:
            self.sel_label.setText("")
        elif first is None:
            self.sel_label.setText(tr("Ce bloc ne produit aucun code (non relié au « Début » ?)"))
        else:
            n = nodes[0]
            name = n.label or tr(FLOW_KINDS[n.kind]["label"] if n.kind in FLOW_KINDS
                                 else BLOCKS[n.kind]["label"])
            self.sel_label.setText(tr("Bloc sélectionné : {} (lignes {}–{})").format(name, first + 1, last + 1))
        if move and first is not None:
            self._syncing = True
            try:
                self.code_view.setTextCursor(QTextCursor(doc.findBlockByNumber(first)))
                self.code_view.centerCursor()
            finally:
                self._syncing = False

    def on_selection_changed(self):
        if not self._syncing:
            self.apply_highlight(move=True)

    def on_code_cursor(self):
        """Un clic dans le code sélectionne le bloc qui l'a produit."""
        if self._syncing or not self.linemap:
            return
        line = self.code_view.textCursor().blockNumber()
        nid = self.linemap[line] if 0 <= line < len(self.linemap) else None
        t = self.tab
        if nid is None or t is None:
            return
        node = next((n for n in t.scene.nodes() if n.id == nid), None)
        if node is None:
            return
        self._syncing = True
        try:
            t.scene.clearSelection()
            node.setSelected(True)
            self.apply_highlight(move=False)
            t.view.centerOn(node)
        finally:
            self._syncing = False

    def open_untitled(self, data=None):
        self.untitled_count += 1
        return self.add_program_tab(f"sans titre {self.untitled_count}", None, data or blank_program())

    def register_tab(self, tab, title):
        tab.scene.message.connect(lambda m: self.msg(m))
        tab.scene.graph_changed.connect(lambda t=tab: self.on_graph_changed(t))
        tab.scene.moved.connect(lambda t=tab: self.set_dirty(t, True))
        tab.scene.selectionChanged.connect(self.on_selection_changed)
        tab.view.customContextMenuRequested.connect(lambda pos, t=tab: self.context_menu(t, pos))
        tab.view.node_double_clicked.connect(lambda node, t=tab: self.edit_node(t, node))
        tab.view.block_dropped.connect(lambda text, pos, t=tab: self.on_drop(t, text, pos))
        idx = self.tabs.addTab(tab, title)
        self.tabs.setCurrentIndex(idx)
        self.set_dirty(tab, False)
        QTimer.singleShot(0, lambda t=tab: self.fit_tab(t))

    def add_program_tab(self, name, path, data):
        tab = ProgramTab(self.theme_dict(), name, path)
        tab.scene.snap = getattr(self, "snap", True)
        tab.scene.from_dict(data)
        self.register_tab(tab, name)
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
        if isinstance(w, (ProgramTab, FlowTab)):
            self.last_prog = w
            if isinstance(w, FlowTab) and w.scene.stale():  # un programme a changé d'entrées/sorties
                was = w.dirty
                w.scene.rebuild()
                self.set_dirty(w, was)
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
        if isinstance(w, FlowTab):
            return self.save_flow(w)
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
        if name == FLOW_ENTRY:
            return self.flow_data()
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
        """Point d'entrée du projet : le flux (FLOW_ENTRY) ou un programme."""
        names = self.program_names()
        m = self.manifest.get("main")
        if m == FLOW_ENTRY and (self.flow_data() or {}).get("nodes"):
            return FLOW_ENTRY
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
        self.msg("Le « Flux du projet » est maintenant le point d'entrée." if name == FLOW_ENTRY
                 else f"« {name} » est maintenant le programme principal.", 5000)

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
        self.setWindowTitle(f"Code Node — {self.ws.name}")
        if not self.program_names():
            self.program_path("principal").write_text(
                json.dumps(blank_program(), indent=2, ensure_ascii=False), encoding="utf-8")
        self.refresh_explorer()
        main = self.main_program_name()
        if main == FLOW_ENTRY:
            self.open_flow()
        elif main:
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
            self.ws_label.setText(tr("Aucun projet ouvert"))
            it = QTreeWidgetItem([tr("Fichier ▸ Nouveau projet…")])
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
        flow_item = QTreeWidgetItem([("★ " if main == FLOW_ENTRY else "") + tr("Flux du projet")])
        flow_item.setIcon(0, color_icon("#f59e0b"))
        flow_item.setData(0, Qt.UserRole, "flow:main")
        flow_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        bold(flow_item)
        tree.addTopLevelItem(flow_item)
        root_p = QTreeWidgetItem([tr("Programmes")])
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

        root_d = QTreeWidgetItem([tr("Documents")])
        root_d.setIcon(0, st.standardIcon(QStyle.SP_DirIcon))
        root_d.setData(0, Qt.UserRole, "dir:documents")
        bold(root_d)
        tree.addTopLevelItem(root_d)
        if (self.ws / "documents").is_dir():
            add_dir(root_d, self.ws / "documents")
        tree.expandAll()

    def explorer_open(self, item, _col=0):
        key = item.data(0, Qt.UserRole) or ""
        if key == "flow:main":
            self.open_flow()
        elif key.startswith("prog:"):
            self.open_program(key[5:])
        elif key.startswith("doc:"):
            self.open_doc(key[4:])

    def explorer_menu(self, pos):
        item = self.explorer.itemAt(pos)
        key = (item.data(0, Qt.UserRole) or "") if item else ""
        menu = TMenu(self)

        def add(text, fn):
            menu.addAction(text).triggered.connect(lambda _=False, f=fn: f())

        if not self.ws:
            add("Nouveau projet…", self.new_project)
            add("Ouvrir un projet…", self.open_project)
        elif key == "flow:main":
            add("Ouvrir le flux du projet", self.open_flow)
            add("Définir comme point d'entrée du projet", lambda: self.set_main(FLOW_ENTRY))
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
        ftab = self.open_tab_for(self.flow_path()) if self.ws else None
        if isinstance(ftab, FlowTab):
            changed = False
            for n in ftab.scene.nodes():
                if n.kind == "prog" and n.params.get("program") == old:
                    n.params["program"] = new
                    changed = True
            if changed:
                ftab.scene.rebuild()
                self.set_dirty(ftab, True)
        elif self.ws and self.flow_path().exists():
            try:
                fdata = json.loads(self.flow_path().read_text(encoding="utf-8"))
                changed = False
                for d in fdata.get("nodes", []):
                    if d.get("kind") == "prog" and (d.get("params") or {}).get("program") == old:
                        d["params"]["program"] = new
                        changed = True
                if changed:
                    self.flow_path().write_text(json.dumps(fdata, indent=2, ensure_ascii=False),
                                                encoding="utf-8")
            except (OSError, ValueError):
                pass
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
            it = QTreeWidgetItem([tr(name)])
            it.setIcon(0, st.standardIcon(QStyle.SP_DirIcon))
            it.setData(0, Qt.UserRole + 1, "user" if user else "builtin")
            it.setData(0, Qt.UserRole + 2, name)
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
                    child = QTreeWidgetItem([tr(spec["label"])])
                    child.setIcon(0, color_icon(spec["color"]))
                    child.setData(0, Qt.UserRole, f"block:{kind}")
                    child.setFlags(leaf)
                    top.addChild(child)
        top = folder_item("Flux du projet", False)
        for fkey, flabel, fcolor in (("flow:value", "Valeur", "#a855f7"), ("flow:show", "Afficher", "#06b6d4")):
            child = QTreeWidgetItem([tr(flabel)])
            child.setIcon(0, color_icon(fcolor))
            child.setData(0, Qt.UserRole, fkey)
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
        menu = TMenu(self)

        def add(text, fn):
            menu.addAction(text).triggered.connect(lambda _=False, f=fn: f())

        if key.startswith("tpl:"):
            idx = int(key[4:])
            add("Modifier le modèle…", lambda: self.edit_template(idx))
            add("Déplacer vers un dossier…", lambda: self.move_template(idx))
            add("Supprimer le modèle", lambda: self.delete_template(idx))
            menu.addSeparator()
        elif item is not None and item.parent() is None and item.data(0, Qt.UserRole + 1) == "user":
            name = item.data(0, Qt.UserRole + 2) or item.text(0)
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
        if isinstance(tab, FlowTab):
            if kind == "flow" and rest in ("value", "show"):
                self.add_flow_node(tab, rest, pos)
            elif kind == "prog":
                self.add_flow_node(tab, "prog", pos, {"program": rest})
            elif kind == "doc":
                self.add_flow_node(tab, "doc", pos, {"path": rest})
            else:
                self.msg("Ici : glissez des programmes, des documents, « Valeur » ou « Afficher ». "
                         "Les autres blocs servent dans les programmes.", 7000)
            return
        if kind == "flow":
            self.msg("Cet élément sert dans « Flux du projet » (explorateur ▸ Flux du projet).", 6000)
        elif kind == "block" and rest in BLOCKS:
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
            menu = TMenu(self)
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
        if not isinstance(tab, ProgramTab):
            return
        if kind == "start" and any(n.kind == "start" for n in tab.scene.nodes()):
            self.msg("Il n'y a qu'un seul bloc « Début » par programme.", 5000)
            return
        n = tab.scene.create_node(kind, params or {}, pos, None, label, color)
        tab.scene.clearSelection()
        n.setSelected(True)
        tab.scene.graph_changed.emit()

    def edit_node(self, tab, node):
        label = node.label or tr(FLOW_KINDS[node.kind]["label"] if node.kind in FLOW_KINDS
                                 else BLOCKS[node.kind]["label"])
        dlg = BlockDialog(self, node.kind, node.params, label, self.doc_files(), self.program_names())
        if dlg.exec() == QDialog.Accepted:
            node.params.update(dlg.values())
            node.update()
            if isinstance(tab, FlowTab) and node.kind == "prog":
                tab.scene.rebuild()  # les ports dépendent du programme choisi
            else:
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
                t.scene.add_edge(mapping[a].out_ports[e.src.index], mapping[b].in_ports[e.dst.index])
        t.scene.graph_changed.emit()

    def select_all(self):
        t = self.tab
        if t:
            for n in t.scene.nodes():
                n.setSelected(True)

    def context_menu(self, tab, pos):
        if isinstance(tab, FlowTab):
            self.flow_context_menu(tab, pos)
            return
        item = tab.view.itemAt(pos)
        node = find_node(item)
        sp = tab.view.mapToScene(pos)
        menu = TMenu(self)
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
        self._syncing = True
        try:
            if t is None:
                self.code_view.setPlainText("# " + tr("Aucun programme ouvert."))
                self.code_view.setExtraSelections([])
                self.code_status.setText("")
                self.code_dock.setWindowTitle(tr("Code Python généré"))
                self.last_code, self.code_ok, self.linemap, self.err = "", False, [], None
                return
            names = self.name_map()
            if isinstance(t, FlowTab):
                code, res, linemap = module_source(FLOW_ENTRY, t.scene.to_dict(), names, self.program_interface)
                title = tr("Flux du projet")
            else:
                code, res, linemap = module_source(t.name, t.scene.to_dict(), names)
                title = t.name
            warnings = list(res["warnings"])
            for c in sorted(res["calls"]):
                if not self.ws:
                    warnings.append("Les appels de programmes nécessitent un projet ouvert.")
                    break
                if c not in names:
                    warnings.append(f"Programme « {c} » introuvable dans le projet.")
            self.last_code, self.linemap = code, linemap
            self.code_view.setPlainText(code)
            bar.setValue(pos)
            self.err = None
            err_nodes = set()
            try:
                compile(code, "<blocs>", "exec")
                self.code_ok = True
                status = tr("✓ Code valide")
            except SyntaxError as e:
                self.code_ok = False
                line, c0, c1 = error_span(e, code.splitlines())
                self.err = (line, c0, c1, e.msg)
                status = tr("✗ Erreur de syntaxe ligne {} : {}").format(line + 1, e.msg)
                nid = linemap[line] if 0 <= line < len(linemap) else None
                node = next((n for n in t.scene.nodes() if n.id == nid), None) if nid is not None else None
                if node is not None:
                    err_nodes = {nid}
                    name = node.label or tr(FLOW_KINDS[node.kind]["label"] if node.kind in FLOW_KINDS
                                            else BLOCKS[node.kind]["label"])
                    status += "\n" + tr("Bloc concerné : {}").format(name)
            if warnings:
                status += "\n⚠ " + "\n⚠ ".join(dict.fromkeys(warnings))
            self.code_status.setText(status)
            self.code_status.setStyleSheet("color: #ef4444; font-weight: 600;" if self.err else "")
            t.scene.error_nodes = err_nodes
            t.scene.update()
            self.code_dock.setWindowTitle(tr("Code Python généré") + " — " + title)
        finally:
            self._syncing = False
        self.apply_highlight(move=False)
        key = (self.err[0], self.err[3]) if self.err else None
        if key is not None and key != self._err_key:  # nouvelle erreur : on amène la ligne fautive à l'écran
            self._syncing = True
            try:
                self.code_view.setTextCursor(QTextCursor(self.code_view.document().findBlockByNumber(self.err[0])))
                self.code_view.centerCursor()
            finally:
                self._syncing = False
        self._err_key = key

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
        name = FLOW_ENTRY if isinstance(t, FlowTab) else t.name
        if not self.code_ok and QMessageBox.question(
                self, "Exporter", "Le code contient une erreur de syntaxe.\nL'exporter quand même ?"
        ) != QMessageBox.Yes:
            return
        names = self.name_map()
        base = "flux" if name == FLOW_ENTRY else (names.get(name) or py_name(name))
        default = (self.ws / "sortie" if self.ws else Path.cwd()) / f"{base}.py"
        path, _ = QFileDialog.getSaveFileName(self, "Exporter le programme", str(default), "Python (*.py)")
        if path and self.write_text_file(path, self.last_code):
            _c, res, _lm = module_source(name, t.scene.to_dict(), names, self.program_interface)
            extra = ""
            if any(c != name for c in res["calls"]):
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
            code, _res, _lm = module_source(name, data, names)
            if self.write_text_file(Path(d) / f"{names[name]}.py", code):
                count += 1
        flow = self.flow_data()
        if flow and flow.get("nodes"):
            code, _res, _lm = module_source(FLOW_ENTRY, flow, names, self.program_interface)
            if self.write_text_file(Path(d) / "flux.py", code):
                count += 1
        docs = self.ws / "documents"
        if docs.is_dir():
            try:
                shutil.copytree(docs, Path(d) / "documents", dirs_exist_ok=True)
            except OSError as e:
                QMessageBox.warning(self, "Documents", f"Copie des documents impossible :\n{e}")
        main = self.main_program_name()
        entry_file = None if main is None else ("flux" if main == FLOW_ENTRY else names.get(main))
        self.msg(f"{count} fichier(s) exporté(s) dans {d}"
                 + (f" — lancez : python {entry_file}.py" if entry_file else ""), 10000)

    def make_bundle(self):
        """Fusionne tout en un seul fichier. Retourne (code, avertissements, nom du principal) ou None."""
        if self.ws:
            main = self.main_program_name()
            if main is None:
                self.msg("Le projet ne contient aucun programme.")
                return None
            code, warns = compile_bundle(main, self.program_data, self.name_map(), self.program_interface)
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
        base = "flux" if main == FLOW_ENTRY else py_name(main)
        script = Path(tmp) / f"{base}.py"
        script.write_text(code, encoding="utf-8")
        args = ["-m", "PyInstaller", "--onefile", "--noconfirm", "--clean", "--name", base,
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

        self.start_process(child_python(), args, cwd=tmp, on_done=done, tmp=tmp,
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

        self.start_process(child_python(), ["-m", "pip", "install", *pkgs], on_done=done,
                           banner=f"⬇ Installation : {' '.join(pkgs)} …")

    # -------------------------------------------------------- exécution
    def run_code(self):
        """F5 : exécute ce qui est affiché dans l'onglet (programme ou flux)."""
        t = self.need_program()
        if t is None:
            return
        self.stop_code()
        if not self.code_ok:
            QMessageBox.warning(self, "Exécution", "Le code contient une erreur de syntaxe : "
                                "corrigez-le avant de l'exécuter.")
            return
        if isinstance(t, FlowTab):
            self.run_named(FLOW_ENTRY, t.scene.to_dict(), tr("Flux du projet"))
        else:
            self.run_named(t.name, t.scene.to_dict(), t.name)
        self.stdin.setFocus()

    def run_project(self):
        """F6 : exécute le point d'entrée du projet (flux ou programme principal)."""
        if not self.ws:
            self.run_code()
            return
        main = self.main_program_name()
        data = self.program_data(main) if main else None
        if data is None:
            self.msg("Le projet ne contient rien à exécuter.")
            return
        self.stop_code()
        self.run_named(main, data, tr("Flux du projet") if main == FLOW_ENTRY else main)
        self.stdin.setFocus()

    def run_named(self, entry_name, data, label):
        names = self.name_map()
        files, warns, entry = compile_modules(entry_name, data, self.program_data, names,
                                              self.program_interface)
        tmp = tempfile.mkdtemp(prefix="blocs_run_")
        for fn, code in files.items():
            (Path(tmp) / fn).write_text(code, encoding="utf-8")
        cwd = self.ws or Path.cwd()
        banner = tr("▶ Exécution de « {} »…").format(label)
        if warns:
            banner += "\n⚠ " + "\n⚠ ".join(dict.fromkeys(warns))
        self.start_process(child_python(), ["-u", str(Path(tmp) / entry)], cwd=cwd,
                           env={"BLOCS_BASE": str(cwd)}, tmp=tmp, banner=banner)

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
        self.append_console("\n" + tr("■ Terminé (code {})").format(code) + "\n")
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


SPLASH_REF = {}


def install_excepthook():
    """Journal des erreurs + message visible, même quand la console est masquée."""
    log = Path.home() / ".editeur_code_blocs_erreurs.log"
    state = {"shown": 0, "busy": False}

    def hook(etype, value, tb):
        text = "".join(traceback.format_exception(etype, value, tb))
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError:
            pass
        sp = SPLASH_REF.get("w")
        if sp is not None:  # l'écran de chargement ne doit jamais cacher un message d'erreur
            sp.finish_now()
        try:
            if QApplication.instance() is not None and state["shown"] < 3 and not state["busy"]:
                state["busy"] = True
                state["shown"] += 1
                QMessageBox.critical(None, "Erreur", text[-1800:] + f"\n(journal : {log})")
                state["busy"] = False
        except Exception:
            state["busy"] = False
        try:
            if sys.__stderr__ is not None:
                sys.__stderr__.write(text)
        except Exception:
            pass

    sys.excepthook = hook


def main():
    global _EARLY
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    install_excepthook()
    splash = None
    if PREFS.get("splash", True):
        splash = SplashScreen()
        splash.show()
        splash.step(5, tr("Chargement…"))
    SPLASH_REF["w"] = splash
    if _EARLY is not None:  # le mini écran de démarrage laisse la place au vrai
        for action in ("withdraw", "destroy"):
            try:
                getattr(_EARLY, action)()
            except Exception:
                pass
        _EARLY = None
    try:
        win = MainWindow(splash)
        win.show()
        win.raise_()
        win.activateWindow()
    finally:  # quoi qu'il arrive, l'écran de chargement disparaît
        if splash is not None:
            splash.finish_now()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        _fatal(traceback.format_exc())
        sys.exit(1)
