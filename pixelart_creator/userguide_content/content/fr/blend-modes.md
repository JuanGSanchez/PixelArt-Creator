# Modes de fusion

Chaque calque (et chaque groupe) est composé à l'aide d'un **mode de fusion** choisi dans la
liste déroulante propre à chaque calque du [panneau des calques](layers.md). PixelArt Creator
propose **douze** modes — **Normal** plus les onze modes **séparables** non normaux de la
spécification *Compositing and Blending Level 1* du W3C (le même ensemble et les mêmes
résultats que dans Photoshop, Krita ou SVG).

Le mélange s'effectue sur un **alpha direct (non prémultiplié)** dans un espace de travail en
virgule flottante normalisé, puis le résultat est réécrit en RGBA 8 bits. **Normal** est la
composition alpha directe de type source-over.

## Les douze modes

| Mode | Effet |
| --- | --- |
| **Normal** | Alpha direct de type source-over. Un calque entièrement opaque remplace ce qui se trouve en dessous ; un calque entièrement transparent le laisse inchangé. |
| **Produit** | Multiplie le calque par ce qui se trouve en dessous — assombrit toujours. Le blanc est neutre ; le noir donne du noir. |
| **Superposition** | Inverse du produit — éclaircit toujours. Le noir est neutre ; le blanc donne du blanc. |
| **Incrustation** | Produit dans les tons sombres, superposition dans les tons clairs — renforce le contraste (par rapport à ce qui se trouve en dessous). |
| **Assombrir** | Conserve la plus sombre des deux valeurs de canal. |
| **Éclaircir** | Conserve la plus claire des deux valeurs de canal. |
| **Densité de couleur -** | Éclaircit ce qui se trouve en dessous pour refléter le calque ; éclaircissement marqué. |
| **Densité de couleur +** | Assombrit ce qui se trouve en dessous pour refléter le calque ; assombrissement marqué. |
| **Lumière crue** | Incrustation dont les rôles du calque et de l'arrière-plan sont échangés — un projecteur dur. |
| **Lumière tamisée** | Une lumière crue plus douce — éclaircissement ou assombrissement doux selon la valeur du calque. |
| **Différence** | Différence absolue des deux valeurs — des couleurs égales s'annulent en noir. |
| **Exclusion** | Comme la différence, mais avec un contraste plus faible dans les tons moyens. |

> **L'opacité et le mode de fusion se combinent.** L'opacité d'un calque pondère sa
> contribution **pour tous** les modes de fusion, pas seulement pour Normal. Un calque caché
> ne contribue en rien, quel que soit le mode.

## Comment la pile est composée

Les calques sont composés **de bas en haut** sur un résultat cumulé : les pixels de chaque
calque visible sont fusionnés avec ce qui se trouve en dessous, en utilisant le mode de
fusion et l'opacité de ce calque (et son masque, s'il en a un). Une pile de calques en mode
Normal équivaut exactement à appliquer successivement, de bas en haut, la composition alpha directe de type source-over. La
composition ne modifie jamais les tampons des calques sources — elle est non destructive.

Une seule modification ne recompose que la **région affectée**, si bien que peindre sur un
grand canvas reste réactif.

## Performances

Sur un canvas 8K (7680 × 4320), la peinture d'un seul pixel recompose sa petite région
modifiée en environ **1 ms**, bien à l'intérieur du budget de 16 ms / 60 images par seconde.
Certaines interactions plus lourdes à faible zoom — faire glisser le curseur d'opacité, ou un
changement d'attribut qui repeint une grande fenêtre d'affichage sur de nombreux calques —
sont actuellement limitées par le processeur et peuvent dépasser ce budget ; une composition
complète par shaders GPU est une amélioration prévue pour plus tard.

## Sujets connexes

- Définissez le mode de fusion et l'opacité d'un calque dans [Le panneau des calques](layers.md).
