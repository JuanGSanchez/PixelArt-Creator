"""Real interface strings for the Nifen Art specimen sheets.

Every string is read from the shipped translation catalogues (English is the
catalogue source text, Spanish the catalogue translation). A string that is not
in a catalogue stops the run: nothing on a sheet is invented, except the lines
that are explicitly labelled as specimen lines.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple


class Catalogue:
    """One language of the shipped catalogues."""

    def __init__(self, ts_dir: str, lang: str):
        self.lang = lang
        self.path = os.path.join(ts_dir, "pixelart_%s.ts" % lang)
        self.table: Dict[Tuple[str, str], str] = {}
        self.used: List[Tuple[str, str]] = []
        root = ET.parse(self.path).getroot()
        for ctx in root.findall("context"):
            name = ctx.find("name").text
            for msg in ctx.findall("message"):
                src = msg.find("source").text
                tr = msg.find("translation")
                if tr.get("type") in ("vanished", "obsolete"):
                    continue
                text = tr.text if (tr.text and lang != "en") else src
                self.table[(name, src)] = text

    def get(self, context: str, source: str) -> str:
        """Catalogue text with accelerator markers removed ('&&' is a literal '&')."""
        key = (context, source)
        if key not in self.table:
            raise KeyError(
                "not in the %s catalogue: %s / %r" % (self.lang, context, source)
            )
        self.used.append(key)
        text = self.table[key]
        return text.replace("&&", "\x01").replace("&", "").replace("\x01", "&")


MAIN = "Main_Window"
OVER = "Overwrite_Confirm_Dialog"
RECOVER = "Recovery_Prompt"
ASSET = "Asset_Update_Prompt_Dialog"

MENU_TITLES = [
    "&File",
    "&Edit",
    "&Select",
    "&Image",
    "&View",
    "&Palette",
    "&Cloud",
    "&Help",
]
FILE_MENU = ["&New", "&Open…", "&Save", "Save &As…", "&Export…", None, "&Close"]
FILE_SHORTCUTS = ["Ctrl+N", "Ctrl+O", "Ctrl+S", "", "", None, "Ctrl+W"]
DOCK_LAYERS = "Layers"
DOCK_PALETTE = "Palette"
DOCK_TIMELINE = "Timeline"
LAYER_ROWS = ["Layer 1", "Layer is locked."]

# lines that are not catalogue text; the sheets label them as specimen lines
SPECIMEN_ES = (
    "¡Atención! Lingüística, pingüino y ñandú: ¿qué más? Camión, árbol, éxito, única."
)
SPECIMEN_EN = "The quick brown fox jumps over the lazy dog. 0123456789"


def build(ts_dir: str, lang: str) -> Dict[str, object]:
    """All strings the interface sheets use, for one language."""
    cat = Catalogue(ts_dir, lang)
    g = cat.get
    content: Dict[str, object] = {
        "lang": lang,
        "menu_titles": [g(MAIN, s) for s in MENU_TITLES],
        "file_menu": [None if s is None else g(MAIN, s) for s in FILE_MENU],
        "file_shortcuts": FILE_SHORTCUTS,
        "dock_layers": g(MAIN, DOCK_LAYERS),
        "dock_palette": g(MAIN, DOCK_PALETTE),
        "dock_timeline": g(MAIN, DOCK_TIMELINE),
        "layer_rows": [g(MAIN, s) for s in LAYER_ROWS],
        "dialog_title": g(OVER, "Overwrite Existing Pixels?"),
        "dialog_body": g(
            OVER,
            "The destination already has pixels on it. Continuing replaces that "
            "content. This can be undone.",
        ),
        "dialog_check": g(OVER, "Don't ask again for this project"),
        "dialog_ok": g(OVER, "Continue"),
        "dialog_cancel": g(OVER, "Cancel"),
        "status_left": g(MAIN, "Cloud status: —"),
        "status_right": g(MAIN, "Exporting %1 of %2…")
        .replace("%1", "3")
        .replace("%2", "7"),
        "recovery_title": g(RECOVER, "Recover Unsaved Work"),
        "recovery_body": g(
            RECOVER,
            "Unsaved work from a previous session was found. Recover it into a new "
            "tab? Your last explicit save is not affected.",
        ),
        "recovery_ok": g(RECOVER, "Recover"),
        "recovery_cancel": g(RECOVER, "Discard"),
        "unsaved_title": g(MAIN, "Unsaved Changes"),
        "unsaved_body": g(
            MAIN,
            "The current document has unsaved changes. Save it before opening the "
            "dropped project?",
        ),
        "asset_body": g(
            ASSET,
            'The library asset "%1" has changed since your project last referenced '
            "it. Pick up the change, or keep the version your project already "
            "references?",
        ).replace("%1", "hero_idle"),
    }
    content["provenance"] = sorted(set(cat.used))
    content["catalogue"] = os.path.basename(cat.path)
    return content


ALPHABET_LINES = [
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789 !\"#$%&'()*+,-./:;<=>?@",
    "[\\]^_`{|}~ ¡¢£¤¥¦§¨©ª«¬®¯°±²³´µ¶·¸¹º»¼½¾¿×÷",
    "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞß",
    "àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ",
    "‘’‚“”„‹›–—†‡•… →↔⇒ ∘∩∪≈≤≥ ˆˇ˘˙˚˛˜˝",
    "ĀāĂăĄąĆćĈĉĊċČčĎďĐđĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĦħ",
    "ĨĩĪīĬĭĮįİıĲĳĴĵȷĶķĸĹĺĻļĽľĿŀŁłŃńŅņŇňŉŊŋ",
    "ŌōŎŏŐőŒœŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŦŧ",
    "ŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽžſ",
    "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ ΆΈΉΊΌΎΏΪΫ",
    "αβγδεζηθικλμνξοπρςστυφχψω άέήίόύώϊϋΐΰ ʹ͵;΄΅·",
    "ЀЁЂЃЄЅІЇЈЉЊЋЌЍЎЏАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ Ґ №",
    "ѐёђѓєѕіїјљњћќѝўџабвгдежзийклмнопрстуфхцчшщъыьэюя ґ",
    "ŒœßẞÀÂÇÉÈÊËÎÏÔÙÛÜŸ «»‹›„“‚‘ ( )",
    "あかがこうっアカガヒピクセルトッー・、。「」",
]

# Symbol chart:one family per line, each in Regular then Bold.
SYMBOL_LINES = [
    "▶◀▲▼ ▸◂▴▾ ■□●○◆◇★ ✓✗",
    "→←↑↓↔↕ ⇒⇐⇔",
    "+−×÷±=≠≈<>≤≥ ∞∘∩∪⊆ ° ⁷ⁿ ¹²³ ¼½¾",
    "€£¥¢¤ $% ©®™ §¶†‡ •·… ‹›«» –—",
]

# In-context lines for the symbol sheets (labelled specimen lines, not catalogue text).
SYMBOL_CONTEXT = [
    "Help ▸ User Guide ▸ Layers",
    "Palette ▾   Layers ▴   Timeline ▸",
    "★ Favourites   ✓ Saved   ✗ Failed   ● Recording   ○ Idle",
    "50 × 20 px → 100 %   ≤ 8 ≥ 2 ≠ 0   ± 3 °C   ÷ 4   −5   ∞",
    "Precio: 4,99 €   PixelArt™   § 3.2   Ctrl+Z ← →",
]

# Sample lines in languages that need Latin Extended-A (labelled specimen lines).
EURO_LINES = [
    ("Polski", "Zażółć gęślą jaźń. Pchnąć w tę łódź jeża lub ośm skrzyń fig."),
    ("Čeština", "Příliš žluťoučký kůň úpěl ďábelské ódy."),
    ("Slovenčina", "Kŕdeľ ďatľov učí koňa žrať kôš."),
    ("Türkçe", "Pijamalı hasta yağız şoföre çabucak güvendi. İstanbul, ılık ışık."),
    ("Magyar", "Árvíztűrő tükörfúrógép. Ő és Ű: őrült űrhajós."),
    ("Hrvatski", "Gojazni đačić s biciklom drži hmelj i finu vatu u džepu."),
    ("Latviešu", "Muļķa hipiji mēģina brīvi nogaršot celofāna žņaudzējčūsku."),
    ("Lietuvių", "Įlinkdama fechtuotojo špaga sublykčiojusi pragręžė apvalų arbūzą."),
    ("Esperanto", "Ĉiuj homoj: ĝi, ĥoro, ĵaŭdo, ŝi, ŭ."),
    ("Nederlands", "Het Ĳsselmeer en het ĳs."),
    ("Català", "Col·legi, intel·ligent, Ŀ ŀ."),
    ("Malti", "Ħafna ċ ġ ż: Ċ Ġ Ħ Ż, għajnuna."),
    ("Français", "Œuvre, cœur, sœur, œil, Œ."),
    ("Cymraeg", "Tŷ, dŵr, ŵy, Ŵ Ŷ."),
    ("Afrikaans", "ŉ Man en ŉ vrou."),
    ("Sami, Eng", "Ŋ ŋ Ŧ ŧ Đ đ Š š Ž ž Č č, kra ĸ, long s ſ."),
]

MIXED_LINES = [
    "Ελληνικά Λάμδα",
    "Пиксельная графика",
    "ピクセルアート・がっこう",
]


# ---- Greek, Cyrillic, French and German: labelled specimen lines, not catalogue text
# ----
# The interface scene "ui-ru" uses the same layout as the English and Spanish scenes
# with
# Russian words; those words are specimen text, not a shipped translation.
RUSSIAN_UI = {
    "lang": "ru",
    "menu_titles": [
        "Файл",
        "Правка",
        "Выделение",
        "Изображение",
        "Вид",
        "Палитра",
        "Облако",
        "Справка",
    ],
    "file_menu": [
        "Создать",
        "Открыть…",
        "Сохранить",
        "Сохранить как…",
        "Экспортировать…",
        None,
        "Закрыть",
    ],
    "file_shortcuts": ["Ctrl+N", "Ctrl+O", "Ctrl+S", "", "", None, "Ctrl+W"],
    "dock_layers": "Слои",
    "dock_palette": "Палитра",
    "dock_timeline": "Временная шкала",
    "layer_rows": ["Слой 1", "Слой заблокирован."],
    "dialog_title": "Заменить существующие пиксели?",
    "dialog_body": "В целевой области уже есть пиксели. Продолжение заменит это "
    "содержимое. Действие можно отменить.",
    "dialog_check": "Больше не спрашивать для этого проекта",
    "dialog_ok": "Продолжить",
    "dialog_cancel": "Отмена",
    "status_left": "Состояние облака: —",
    "status_right": "Экспорт 3 из 7…",
    "recovery_title": "Восстановить несохранённую работу",
    "recovery_body": "Найдена несохранённая работа из предыдущего сеанса. "
    "Восстановить её в новой вкладке? Последнее явное сохранение "
    "не затронуто.",
    "recovery_ok": "Восстановить",
    "recovery_cancel": "Отклонить",
    "unsaved_title": "Несохранённые изменения",
    "unsaved_body": "В текущем документе есть несохранённые изменения. Сохранить "
    "его перед открытием перетащенного проекта?",
    "asset_body": "Ресурс библиотеки «hero_idle» изменился с тех пор, как проект на "
    "него ссылался. Принять изменение или оставить версию, на которую "
    "проект уже ссылается?",
    "provenance": [],
    "catalogue": "(specimen text)",
}

CYRILLIC_LINES = [
    (
        "Русский, pangram",
        "Эй, жлоб! Где туз? Прячь юных съёмщиц в шкаф. Съешь же ещё этих мягких "
        "французских булок, да выпей чаю.",
    ),
    ("Русский, capitals", "ФАЙЛ ПРАВКА СЛОИ ПАЛИТРА ВИД СПРАВКА. ЁЖ, ЩУКА, ЪЫЬ, ЭЮЯ."),
    (
        "Русский, interface words",
        "Сохранить как… Открыть проект. Размер холста: 64 × 64 пикселя. Ластик, "
        "кисть, заливка, пипетка. Тема: светлая / тёмная.",
    ),
    (
        "Українська",
        "Чуєш їх, доцю, га? Кумедна ж ти, прощайся без ґольфів! Є, Ї, І, Ґ.",
    ),
    ("Беларуская", "Ён ужо ўсё ведаў. Ў ў, Ё ё, І і."),
    (
        "Српски",
        "Љубазни фењерџија чађавог лица хоће да ми покаже штос. Ђ ђ Ј ј Љ љ Њ њ Ћ ћ "
        "Џ џ.",
    ),
    ("Македонски", "Ѓ ѓ Ќ ќ Ѕ ѕ Љ љ Њ њ Џ џ Ј ј: ѓубре, ќебе, ѕвезда."),
    ("Numero", "№ 1, № 25, № 100"),
]

GREEK_LINES = [
    (
        "Ελληνικά, pangram",
        "Ξεσκεπάζω την ψυχοφθόρα βδελυγμία. Ξεσκεπάζω την ψυχοφθόρα βδελυγμία.",
    ),
    ("Ελληνικά, capitals with tonos", "ΞΕΣΚΕΠΆΖΩ ΤΗΝ ΨΥΧΟΦΘΌΡΑ ΒΔΕΛΥΓΜΊΑ. ΆΈΉΊΌΎΏ ΪΫ."),
    (
        "Ελληνικά, interface words",
        "Αρχείο  Επεξεργασία  Στρώσεις  Παλέτα  Προβολή  Βοήθεια. Αποθήκευση ως…",
    ),
    ("Ελληνικά, tonos and dialytika", "ά έ ή ί ό ύ ώ ϊ ϋ ΐ ΰ Ά Έ Ή Ί Ό Ύ Ώ Ϊ Ϋ ς σ"),
    (
        "Ελληνικά, punctuation",
        "Τι είναι αυτό; Αυτό είναι ένα παράδειγμα· προχωράμε. Ο αριθμός 5ʹ και το "
        "κάτω ͵α.",
    ),
]

FRENCH_GERMAN_LINES = [
    (
        "Français, pangram",
        "Portez ce vieux whisky au juge blond qui fume. Voix ambiguë d’un cœur qui, "
        "au zéphyr, préfère les jattes de kiwis.",
    ),
    (
        "Français, typography",
        "« Où est l’été ? » demanda-t-il : « Ça va ! » Une demi-heure ; un tiers : "
        "50 % ‹ où ›.",
    ),
    ("Français, capitals", "ÉCOLE À ÇÀ ÊÎÔÛÙ NAÏVE ŒUVRE Ÿ Île de France."),
    (
        "Deutsch, pangram",
        "Zwölf Boxkämpfer jagen Viktor quer über den großen Sylter Deich. Falsches "
        "Üben von Xylophonmusik quält jeden größeren Zwerg.",
    ),
    ("Deutsch, capitals", "STRAẞE – GROẞE STRAẞE – Straße – ÄÖÜ äöü ß ẞ."),
    (
        "Deutsch, interface words",
        "Öffnen  Schließen  Größe ändern  „Anführungszeichen“ ‚einfach‘ »Spitze« "
        "›einfach‹.",
    ),
]


# ---- Japanese kana and punctuation: labelled specimen lines, not catalogue text ----
# Kanji are out of scope for this typeface. Where a real Japanese interface would use
# them the
# words below are written in kana and the sheet says so; they are specimen text, not a
# translation.
JAPANESE_UI = {
    "lang": "ja",
    "wrap": "chars",
    "menu_titles": [
        "ファイル",
        "へんしゅう",
        "せんたく",
        "イメージ",
        "ひょうじ",
        "パレット",
        "クラウド",
        "ヘルプ",
    ],
    "file_menu": [
        "あたらしく",
        "ひらく…",
        "ほぞん",
        "なまえをつけてほぞん…",
        "エクスポート…",
        None,
        "とじる",
    ],
    "file_shortcuts": ["Ctrl+N", "Ctrl+O", "Ctrl+S", "", "", None, "Ctrl+W"],
    "dock_layers": "レイヤー",
    "dock_palette": "パレット",
    "dock_timeline": "タイムライン",
    "layer_rows": ["レイヤー 1", "レイヤーはロックされています。"],
    "dialog_title": "ピクセルをうわがきしますか？",
    "dialog_body": "かきこみさきにはすでにピクセルがあります。つづけると、そのないようはおきかえられます。このそうさはもとにもどせます。",
    "dialog_check": "このプロジェクトではもうたずねない",
    "dialog_ok": "つづける",
    "dialog_cancel": "キャンセル",
    "status_left": "クラウドのじょうたい：—",
    "status_right": "エクスポートちゅう 3 / 7…",
    "recovery_title": "ほぞんしていないさぎょうをふっきゅう",
    "recovery_body": "まえのセッションでほぞんされていないさぎょうがみつかりました。あたらしいタブにふっきゅうしますか？"
    "さいごにほぞんしたないようにはえいきょうありません。",
    "recovery_ok": "ふっきゅう",
    "recovery_cancel": "すてる",
    "unsaved_title": "ほぞんされていないへんこう",
    "unsaved_body": "いまのドキュメントにはほぞんされていないへんこうがあります。ドロップされたプロジェクトをひらくまえにほぞんしますか？",
    "asset_body": "ライブラリのアセット「hero_idle」は、プロジェクトがさいごにさんしょうしたあとにかわりました。へんこうをとりこみますか？"
    "それとも、プロジェクトがさんしょうしているバージョンのままにしますか？",
    "provenance": [],
    "catalogue": "(specimen text)",
}

# Kana tables: five rows (a i u e o) by the consonant columns, gojuon order. None is an
# empty cell.
HIRAGANA_TABLE = [
    "あかさたなはまやらわ",
    "いきしちにひみ　りゐ",
    "うくすつぬふむゆるん",
    "えけせてねへめ　れゑ",
    "おこそとのほもよろを",
]
KATAKANA_TABLE = [
    "アカサタナハマヤラワ",
    "イキシチニヒミ　リヰ",
    "ウクスツヌフムユルン",
    "エケセテネヘメ　レヱ",
    "オコソトノホモヨロヲ",
]
HIRAGANA_VOICED = ["がざだばぱ", "ぎじぢびぴ", "ぐずづぶぷ", "げぜでべぺ", "ござどぼぽ"]
KATAKANA_VOICED = ["ガザダバパ", "ギジヂビピ", "グズヅブプ", "ゲゼデベペ", "ゴゾドボポ"]
KANA_SMALL_ROWS = [
    "ぁぃぅぇぉっゃゅょゎゕゖ",
    "ァィゥェォッャュョヮヵヶ",
    "ゔヴヷヸヹヺ ゝゞゟ ヽヾヿ",
    "ー・゛゜",
    "　、。〃々〜～",
    "「」『』〈〉《》【】",
    "！？（）：；，．",
]

JAPANESE_LINES = [
    (
        "Hiragana, words",
        "あいうえお。かきくけこ。さしすせそ。たちつてと。なにぬねの。はひふへほ。まみむめも。やゆよ。らりるれろ。わをん。",
    ),
    (
        "Hiragana, voiced and small kana",
        "がっこう　ちょっと　しゃしん　きょう　ぎゅうにゅう　じゃがいも　ぱぴぷぺぽ　ぼんやり　ぜんぶ　でんしゃ",
    ),
    (
        "Katakana, words",
        "ファイル　フォルダー　キャンセル　エクスポート　パレット　レイヤー　ブラシ　ツール　ウィンドウ　ヴァイオリン",
    ),
    (
        "Katakana, long sound mark and middle dot",
        "ソフトウェア・エンジニア　コンピューター　ユーザー　サーバー　メニュー　ジャズ・ピアノ",
    ),
    (
        "Punctuation",
        "「ひらく」『ほぞん』（キャンセル）【おしらせ】〈ヘルプ〉《ガイド》　ほぞんしますか？　はい！　1〜5　1～5",
    ),
    ("Iteration marks", "ゝゞ ヽヾ 々 ゟ ヿ　こゝろ　いすゞ　ミスヾ"),
]

# Latin and kana in one line (labelled specimen lines).
MIXED_JA_LINES = [
    (
        "Latin and kana",
        "Nifen Art ニフェン・アート: ファイル File, パレット Palette, レイヤー Layers.",
    ),
    (
        "Latin and kana, sizes",
        "12 px フォント / 24 px フォント / Ctrl+S ほぞん / 100 % ズーム",
    ),
    (
        "Latin and kana, sentence",
        "Pixel Art は ピクセル アート の ひとつ です。 Save を おして ほぞん します。",
    ),
]
