# Exportation et intégration au pipeline

Le **système d'exportation** transforme un projet en ressources qu'un pipeline de jeu peut
consommer : un seul **PNG**, un **GIF animé**, une **feuille de sprites** ou un **atlas de
textures** compact, chacun avec des métadonnées **JSON de type Aseprite** facultatives et des
**préréglages de moteur** prêts à l'emploi pour **Unity** et **Godot**. Vous pouvez exporter une
cible depuis la boîte de dialogue d'exportation, en mettre plusieurs en file d'attente avec le
panneau d'exportation par lot, ou lancer le tout sans interface depuis la ligne de commande
`pixelart-export` — et chaque voie produit **exactement les mêmes octets**. Ouvrez la boîte de
dialogue d'exportation avec **Fichier ▸ Exporter…** ou avec **Ctrl+Shift+E**.

> **Exportation reproductible à l'octet près.** L'exportation est **déterministe** : pour un
> document d'entrée donné et les mêmes paramètres, les octets produits sont identiques à chaque
> fois — les images sont parcourues dans un ordre explicite, le GIF utilise une palette partagée
> fixe sans tramage, et les encodeurs sont figés. L'interface graphique et la ligne de commande
> pilotent le **même** moteur : une exportation faite dans l'interface et une exportation faite
> en ligne de commande du même document sont donc **identiques à l'octet près**. La garantie
> vaut *dans un même environnement* (une chaîne d'outils figée), elle n'est pas assurée d'une
> machine à l'autre.

| Raccourci | Action |
| --- | --- |
| **Ctrl+Shift+E** | Ouvrir la boîte de dialogue d'exportation. |

## Exportation raster (PNG / GIF)

- **PNG** exporte l'**image d'animation 0** (la première) sous la forme d'une seule image RGBA —
  la cible pour une image fixe.
- **GIF** exporte l'animation : toutes les images dans l'ordre, chacune affichée pendant sa
  propre **durée par image** (les durées définies sur la
  [ligne temporelle d'animation](animation-timeline.md)), le nombre de boucles, le mode
  d'élimination des images et la transparence étant écrits dans le fichier. Toutes les images
  partagent **une seule palette fixe** (une réduction par coupe médiane sur l'ensemble de
  l'animation) et le tramage est **désactivé**, ce qui permet de conserver au GIF sa reproductibilité à l'octet près.

> **Nombre de boucles du GIF.** L'option `--loop` (ligne de commande) / le champ **Nombre de
> boucles** (boîte de dialogue) définit combien de fois le GIF se répète ; **`0` signifie boucle
> infinie**.

## Feuilles de sprites et atlas de textures

- Une **feuille de sprites** dispose chaque image sur une **grille uniforme**, ligne par ligne —
  l'image `k` se place à la colonne `k % columns`, ligne `k // columns`, avec une **marge**
  configurable entre les sprites et sans bordure extérieure. Réglez le nombre de colonnes pour
  contrôler la forme de la feuille.
- Un **atlas de textures** range les images au plus serré avec l'algorithme d'empaquetage
  **MaxRects** commun (la rotation est désactivée, si bien que les sprites restent toujours
  alignés sur les axes). L'atlas est l'option la plus économe en espace quand le contenu des
  images varie.

> **Plafond de taille de l'atlas.** L'atlas est limité au plafond de dimension **8K** de la
> plateforme. Si un ensemble de sprites ne tient pas dans ce plafond, l'exportation **échoue
> proprement** avec une erreur d'atlas explicite (jamais un chevauchement, une troncature ni un plantage passés sous silence) — réduisez la marge entre les sprites, la taille des images ou leur nombre, puis
> réessayez.

## Métadonnées JSON

Les exportations de feuille de sprites et d'atlas peuvent produire un **fichier annexe de
métadonnées JSON** au format **Aseprite *Array*** : un tableau `frames[]` (le rectangle de
chaque image, sa taille source et sa durée) plus un bloc `meta{}` qui porte les **étiquettes**
d'images et les durées par image. Le JSON est **déterministe** — les clés sont triées, les
séparateurs sont fixes et les coordonnées sont des entiers — de sorte qu'il se relit à
l'identique et produit des différences nettes d'une version à l'autre. Activez ou désactivez-le avec la case
**Écrire les métadonnées JSON** de la boîte de dialogue, ou avec `--json` / `--no-json` en ligne
de commande (activé par défaut).

## Préréglages de moteur (Unity / Godot)

En plus de l'image et du JSON, l'exportation peut écrire un **préréglage prêt pour le moteur**,
afin que la ressource se glisse directement dans un projet :

| Préréglage | Ce qu'il écrit |
| --- | --- |
| **Unity** | Un fichier annexe `.meta` de sprite — mode de sprite **Multiple**, `pixelsPerUnit`, pivot et `filterMode = Point` (pixels nets, sans lissage bilinéaire). |
| **Godot** | Une ressource `SpriteFrames` `.tres` (Godot 4.2) construite à partir des images exportées. |

Choisissez le préréglage dans la boîte de dialogue, ou passez `--preset unity` /
`--preset godot` en ligne de commande (`--preset none` — la valeur par défaut — n'écrit aucun
préréglage). Les fichiers de préréglage sont construits de façon déterministe à partir des mêmes
métadonnées de disposition que l'image.

## Exportation par lot

Le **panneau d'exportation par lot** met **plusieurs cibles en file d'attente à la fois** — par
exemple un PNG, un GIF et un atlas Unity issus d'un même projet, en une seule exécution.
L'exportation par lot **se poursuit malgré les échecs** : si une cible échoue (par exemple un
atlas qui ne tient pas), les autres cibles sont tout de même exportées et l'échec n'est signalé
que pour cette cible, si bien qu'une mauvaise cible n'interrompt jamais le lot. Le bouton
**Tout exporter** exporte le document de l'onglet actif vers chaque cible de la file
d'attente, en une seule exécution.

## Inscrire un fichier exporté dans la bibliothèque

La boîte de dialogue d'exportation comporte une case à cocher, **Ajouter aussi à la bibliothèque
de ressources**, qui inscrit le fichier exporté dans la
[bibliothèque de ressources](asset-library.md) au cours de la même opération que l'exportation — une option à
activer, et non un comportement par défaut. La cocher ouvre l'invite **Inscrire une ressource**
partagée (nom, type, étiquettes) après une exportation réussie ; la laisser décochée exporte sans
toucher à la bibliothèque, exactement comme avant que cette option existe.

## Réactivité

Tout le travail d'exportation s'exécute **hors du fil d'exécution de l'interface**, sur une tâche
d'arrière-plan, derrière un **indicateur de progression que vous pouvez annuler** — exporter une
grande animation ou un grand atlas ne fige donc jamais la fenêtre. L'exportation est en
**lecture seule** sur votre document : elle ne le modifie jamais et n'ajoute aucune étape
d'annulation.

> **Annuler une grande cible isolée.** L'annulation prend effet rapidement entre deux cibles ;
> annuler **au milieu de l'encodage d'une seule grande cible** est moins fin — l'encodage en
> cours se termine avant que l'annulation soit prise en compte.

## La ligne de commande `pixelart-export`

Pour l'automatisation et l'intégration continue, `pixelart-export` exécute **exactement le même**
chemin d'exportation en mode sans fenêtre (sans interface graphique) — sa sortie est identique, octet
pour octet, à celle de l'exportation faite dans l'interface avec le même document et les mêmes
paramètres. Il charge le `.pixproj` avec le même chargeur de projet défensif et validé que
l'application.

```
pixelart-export --input PROJECT.pixproj --format FORMAT --output OUT [options]
```

| Option | Signification |
| --- | --- |
| `--input PATH` | **(obligatoire)** le projet `.pixproj` source à exporter. |
| `--format FORMAT` | **(obligatoire)** l'un de `png`, `gif`, `sprite-sheet`, `atlas`. |
| `--output PATH` | **(obligatoire)** le chemin de l'image de sortie. |
| `--preset PRESET` | préréglage de moteur : `none` (par défaut), `unity`, `godot`. |
| `--columns N` | nombre de colonnes de la feuille de sprites. |
| `--padding N` | marge entre les sprites, en pixels. |
| `--loop N` | nombre de boucles du GIF (`0` = boucle infinie). |
| `--tag NAME` | n'exporter que la plage d'une étiquette d'images nommée (par défaut : le document entier). |
| `--json` / `--no-json` | produire ou non le fichier annexe JSON de la feuille de sprites / de l'atlas (par défaut : activé). |

**Codes de sortie :** `0` succès ; `1` une erreur d'exportation / d'empaquetage / d'écriture (par
exemple un atlas qui ne tient pas, ou un échec d'écriture sur le système de fichiers) ; `2` des
arguments incorrects ou un projet d'entrée mal formé / illisible.

> **Le même chemin que l'interface.** Comme la ligne de commande et la boîte de dialogue
> appellent le même moteur, vous pouvez prototyper une exportation de façon interactive, puis la
> reproduire exactement dans un script de build en passant les mêmes paramètres sous forme
> d'options.

## Ce qui n'est pas couvert

- **APNG** (PNG animé) — **différé** ; cette version exporte le PNG fixe (image 0) et le GIF
  animé.
- Une sortie **identique à l'octet près d'une machine à l'autre** — la garantie de
  reproductibilité à l'octet près vaut *dans un même environnement* (une chaîne d'outils figée) ;
  la chaîne d'outils d'une autre machine peut produire des octets différents.
- L'**annulation fine au milieu de l'encodage** d'une seule grande cible — l'annulation est
  prise en compte entre les cibles, et non en plein encodage d'une cible.

## Sujets connexes

- Automatisez les exportations dans le cadre d'un pipeline scripté avec
  [Automatisation et scripts](automation-and-scripting.md).
