# Importation par glisser-déposer

Faites glisser un fichier directement depuis l'explorateur de fichiers de votre système
d'exploitation (Explorateur de fichiers de Windows, Finder de macOS, Nautilus de Linux)
**dans** la fenêtre de PixelArt Creator, et l'application fait ce qu'il faut pour ce type de
fichier. Inutile de passer par Fichier ▸ Ouvrir — déposez-le n'importe où dans la fenêtre et
l'application l'aiguille **selon le type de fichier**, et non selon l'endroit de la fenêtre où
vous le relâchez.

> **L'aiguillage se fait selon le type, jamais selon l'emplacement du dépôt.** Une image
> s'ouvre *toujours* comme un nouveau document, un `.pixproj` s'ouvre *toujours* comme un
> projet, et un fichier de palette se charge *toujours* dans la palette active — quel que
> soit l'endroit de la fenêtre où vous le déposez. En un seul dépôt, vous pouvez mélanger les
> types et même déposer plusieurs fichiers à la fois.

## Déposer une image → un nouvel onglet de document

Déposez un fichier **`.png`, `.jpg`, `.jpeg`, `.bmp` ou `.gif`** et il s'ouvre dans un
**tout nouvel onglet de canvas / de document** qui devient actif. Il est importé comme un
nouveau document, **et non** comme un calque du document que vous modifiez — votre document
actuel reste intact.

- Le nouveau document est en **RGBA**, avec la largeur et la hauteur propres à l'image. Un
  PNG ou un GIF à palette (indexé) est converti en RGBA à l'importation.
- Pour un **GIF animé**, c'est la **première image de l'animation** qui est importée.
- L'importation est en **lecture seule sur le disque** — déposer un fichier ne modifie jamais
  la source.

> **Limite de taille d'image.** Une image plus grande que le maximum du canvas
> (**7680 × 4320**) est **rejetée** avec une notification d'erreur — elle n'est jamais rognée
> ni mise à l'échelle en silence. Convertissez-la ou redimensionnez-la d'abord en dehors de
> l'application.

## Déposer un `.pixproj` → ouvrir le projet (avec une protection contre la perte des modifications)

Déposez un fichier **`.pixproj`** et il s'ouvre comme un projet.

Si le document que vous modifiez actuellement contient des **modifications non
enregistrées**, l'application affiche d'abord une invite **Enregistrer / Ne pas tenir compte
/ Annuler** afin que vous ne perdiez jamais de travail par accident :

| Choix | Résultat |
| --- | --- |
| **Enregistrer** | Enregistre le document actuel, puis ouvre le projet déposé. |
| **Ne pas tenir compte** | Ouvre le projet déposé sans enregistrer. |
| **Annuler** | Abandonne l'ouverture — rien ne change. |

Si le document actuel ne contient **aucune** modification non enregistrée (ou si aucun
document n'est ouvert), le projet s'ouvre immédiatement, sans invite.

## Déposer une palette → la charger dans la palette active (annulable)

Déposez un fichier de palette **`.gpl` (GIMP), `.hex` (liste hexadécimale simple) ou `.pal`
(texte JASC-PAL)** et ses couleurs **remplacent** la palette du document actif.

- Le remplacement constitue une **seule étape annulable** : un seul **Annuler** restaure
  exactement votre palette précédente.
- Si aucun document n'est ouvert, le dépôt est sans effet ni conséquence, avec une brève
  notification.

> **Quels formats de palette ?** Le jeu de formats est celui des formats **texte** courants
> du pixel art : `.gpl`, `.hex` et `.pal`. Les formats binaires **`.aco`** (Adobe) et
> **`.aseprite`** (le format propre à Aseprite) **ne sont pas encore pris en charge** — ils
> sont pour l'instant signalés comme un type non pris en charge.

## Déposer plusieurs fichiers à la fois

Un dépôt de plusieurs fichiers traite chaque fichier **indépendamment, selon son type, dans
l'ordre où ils ont été déposés** :

- plusieurs images ouvrent plusieurs nouveaux onglets ;
- un `.pixproj` s'ouvre (en respectant sa protection contre les modifications non
  enregistrées) ;
- les palettes se chargent l'une après l'autre — c'est la **dernière** palette déposée qui
  finit par être active (chacune constitue sa propre étape d'annulation).

Un fichier inconnu ou illisible dans le lot est ignoré avec une notification ; les autres
sont tout de même traités. Déposer zéro fichier ne fait rien.

## Quand un fichier ne peut pas être importé

Le glisser-déposer ne fait jamais planter l'application :

- un **type non pris en charge** (par exemple un `.txt`, ou une palette `.aco`/`.aseprite`)
  est **ignoré**, avec une brève notification d'état non bloquante ;
- une image **corrompue, impossible à décoder ou trop grande**, une palette **mal formée**
  ou un `.pixproj` **invalide** affiche une **notification d'erreur** qui nomme le fichier et
  le problème, et laisse votre travail **exactement tel qu'il était** — pas d'onglet à moitié
  créé, pas de palette à moitié chargée.

Toutes les invites et notifications sont traduisibles, accessibles au clavier et lisibles
dans les thèmes clair et sombre.

## Ce qui n'est pas couvert

- **Importer comme calque** — une image s'ouvre toujours comme un nouveau document, jamais
  comme un calque du document actuel.
- **Importation indexée** d'une image source à palette — les images sont décodées en RGBA ;
  appliquez ensuite **Palette ▸ Convertir en indexé** (voir
  [Le panneau des calques](layers.md)) si vous voulez un document indexé.
- **Importation d'un GIF animé** — seule la première image est importée.
- Le côté **exportation / enregistrement** du pipeline — voir
  [Exportation et intégration au pipeline](export-and-pipeline.md).
