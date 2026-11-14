<!-- surface-only: bundle — contenu d'orientation dans l'application ; à peine abordé par le texte d'introduction d'index.md du site, sans page dédiée du site par conception -->
# Premiers pas et espace de travail

![PixelArt Creator](pac-logo.png)

Bienvenue dans **PixelArt Creator** — un studio de pixel art de bureau doté d'un canvas 8K,
d'un système de calques non destructif, d'une ligne temporelle d'animation, d'un éditeur de
tilesets et de tilemaps, d'un pipeline d'exportation, d'outils d'automatisation et de script,
d'aides visuelles, ainsi que d'outils de cloud et de collaboration. Cette rubrique vous
présente l'espace de travail pour que le reste du guide soit clair.

## La fenêtre principale en un coup d'œil

- **Barre de menus** (en haut) — le point d'entrée de toutes les commandes, regroupées en
  menus tels que **Fichier**, **Édition**, **Affichage**, **Cloud** et **Aide**. Le Guide de
  l'utilisateur intégré à l'application, que vous lisez en ce moment, s'ouvre depuis
  **Aide ▸ Guide de l'utilisateur** (ou en appuyant sur **F1**).
- **Canvas** (au centre) — la surface de dessin. Voir
  [Le canvas : zoom, déplacement et grille](canvas-and-view.md).
- **Panneaux** (sur les côtés) — le panneau des calques, la ligne temporelle d'animation, le
  panneau Éditeur de tileset et les panneaux de cloud et de collaboration. La plupart des
  panneaux peuvent être affichés ou masqués et disposés selon votre façon de travailler.
- **Barre d'état** (en bas) — des indicateurs de progression pour les tâches en arrière-plan
  (exportation, préparation de la lecture, enregistrements dans le cloud) et de brefs avis.

## Documents et onglets

Chaque dessin ouvert est un **document** affiché dans son propre **onglet**. Un document a
une taille, un mode de couleur (**RGBA** ou **indexé**), une palette, une arborescence de
calques et — si vous l'animez — une liste d'images. Vous pouvez garder plusieurs documents
ouverts à la fois ; voir [Plusieurs canvas (plans de travail)](multi-canvas.md). Les
documents sont enregistrés sous forme de fichiers de projet **`.pixproj`**, le format
d'enregistrement validé et versionné que toute l'application (et la couche cloud) utilise.

## Annuler et rétablir

Presque toute modification — la peinture, un changement de calque, une transformation, une modification d'image d'animation, une exécution d'automatisation — est placée sur la **pile
d'annulation** du document comme **exactement une** étape. **Annuler** revient sur la
dernière étape et **Rétablir** la réapplique. L'historique d'annulation est **propre à chaque
onglet** : annuler dans un document n'atteint donc jamais un autre. Quelques actions ne sont
volontairement *pas* annulables, car elles relèvent de l'état de la vue plutôt que de
modifications : sélectionner ou parcourir une image de l'animation, activer la pelure d'oignon, ajouter un
repère et ouvrir les panneaux de cloud et de collaboration.

## Thèmes (style, clair et sombre)

Tout ce qui concerne l'apparence de l'application se trouve dans le menu **Thème**. Chaque
choix s'applique immédiatement et est mémorisé pour la prochaine fois que vous démarrez
l'application.

- **Style** — un sous-menu proposant trois styles visuels : **Washi & Kintsugi** (le style par
  défaut), **Edo Night** et **Arcade Kikko**. Chacun est un aspect complet pour les
  panneaux, les boîtes de dialogue, les bordures et les zones à motifs de la fenêtre.
- **Clair** / **Sombre** — le mode de couleur, choisi indépendamment du style. Chaque
  panneau, chaque boîte de dialogue, chaque élément en surimpression et ce Guide de
  l'utilisateur s'affichent correctement et restent lisibles dans les deux modes. Les
  couleurs sont définies une seule fois par rôle, si bien que le thème est cohérent partout.
- **Utiliser la police système** — remplace la police pixel intégrée de l'interface (Nifen
  Art) par la police d'interface de votre système d'exploitation.
- **Interface pixel perfect** — activée par défaut. Elle met l'interface à l'échelle par
  nombres entiers uniquement, afin que le pixel art reste net sur les écrans à échelle
  fractionnaire (par exemple 125 % ou 150 %). Une modification prend effet au prochain
  démarrage de l'application.

## Version et À propos

Le titre de la fenêtre affiche toujours **PixelArt Creator** suivi de la version en cours
d'exécution — le numéro exact de votre build — sans aucune étape supplémentaire pour la
trouver. Pour en savoir plus, choisissez **Aide ▸ À propos de PixelArt Creator** (sous
macOS : le menu de l'application, à côté de Quitter — la plateforme y place l'entrée). La
boîte de dialogue À propos affiche le nom de l'application, sa version (sélectionnable, pour
que vous puissiez la copier à la main), la licence, des liens vers le dépôt du code source,
le site de documentation et la page des versions publiées, ainsi qu'un bouton **Copier** qui
place dans le presse-papiers, sur une seule ligne, la version accompagnée de celles de votre
système d'exploitation, de Python et de Qt/PySide6 — prête à être collée directement dans un
rapport de bogue.

## Langue

L'interface est entièrement traduisible. Lorsque vous changez la langue active, chaque menu,
chaque libellé et chaque message se retraduit en direct — vous n'avez pas besoin de
redémarrer. Le cadre de ce Guide de l'utilisateur (son titre, ses libellés de section, sa
zone de recherche et sa navigation) suit la langue active ; le contenu du guide s'affiche
dans votre langue lorsqu'une version localisée est fournie, sinon il se rabat sur le texte
par défaut (anglais).

## Raccourcis clavier

Voici le tableau complet des raccourcis clavier de l'application — chaque touche d'outil, les
deux commutateurs, les deux façons d'effacer une sélection et les actions de base de fichier,
d'édition et d'aide. Toute autre page de ce guide qui mentionne un raccourci clavier renvoie
à ce tableau au lieu de le répéter.

| Raccourci | Action |
| --- | --- |
| **A** | Outil Crayon — peinture libre de pixels. |
| **Shift+A** | Outil Pipette — prélever une couleur sur le canvas. |
| **Q** | Outil Gomme. |
| **S** | Outil Rectangle. |
| **W** | Outil Ligne. |
| **Shift+W** | Outil Ellipse. |
| **D** | Outil Sélection rectangulaire. |
| **F** | Outil Pot de peinture. |
| **Shift+F** | Outil Tramage. |
| **E** | Outil Sélection au lasso (à main levée). |
| **Shift+E** | Outil Baguette magique (couleur contiguë). |
| **Shift+S** | Activer ou désactiver **Formes remplies**, option partagée par les outils Rectangle et Ellipse. |
| **Shift+R** | Activer ou désactiver **Pixel perfect** sur la vue du canvas de chaque onglet ouvert. |
| **Shift+Q** | Effacer le contenu de la sélection. |
| **Delete** | Effacer le contenu de la sélection (second raccourci de la même action). |
| **Ctrl+N** | Nouveau document. |
| **Ctrl+O** | Ouvrir un projet existant. |
| **Ctrl+S** | Enregistrer le projet actif. |
| **Ctrl+Z** | Annuler la dernière opération réversible. |
| **Ctrl+Y** | Rétablir la dernière opération annulée. |
| **F1** | Ouvrir ce Guide de l'utilisateur. |

Les onze touches d'outil ci-dessus se trouvent sur la rangée de base du clavier et ses
voisines, par conception, afin que votre main n'ait jamais à quitter la position de frappe
pendant que vous dessinez. **Shift+Q** et **Delete** font la même chose — effacer le contenu
d'une sélection — donc celui des deux qui est le plus proche de votre main convient.

Quelques autres raccourcis figurent sur la page à laquelle ils appartiennent, car ils n'ont
de sens qu'une fois la fonctionnalité connue : **Ctrl+Shift+E** ouvre l'exportation, voir
[Exportation et intégration au pipeline](export-and-pipeline.md) ; **Ctrl++** / **Ctrl+-**
zooment le canvas, et des gestes du pointeur permettent de déplacer la vue, de zoomer et de
prélever des couleurs à la molette ou au clic central, voir [Le canvas](canvas-and-view.md) ;
**Ctrl+A** / **Ctrl+I** / **Ctrl+Shift+A** / **Shift+H** / **Shift+V** et les gestes de
glissement de la sélection, voir
[Sélection et déplacement/copie flottants](selection-and-transform.md) ; **Ctrl+wheel**,
**Ctrl+middle-click**, **Ctrl+left-click** et **Ctrl+right-click** sur la ligne temporelle,
voir [La ligne temporelle d'animation](animation-timeline.md). **Space** lance ou met en
pause l'animation et n'est pas du tout un raccourci de menu — il ne fonctionne que lorsqu'un
document de plus d'une image est ouvert. **Esc** annule et **Enter** valide toute action en
cours (le plus souvent un déplacement de sélection flottante) — voir
[Sélection et déplacement/copie flottants](selection-and-transform.md) pour savoir
exactement ce que cela couvre.

## Pour la suite

- Dessinez sur le [canvas](canvas-and-view.md) et choisissez vos couleurs dans le
  [centre de couleurs](colour-hub.md).
- Organisez votre travail avec les [calques](layers.md) et les [modes de fusion](blend-modes.md).
- [Sélectionnez et déplacez](selection-and-transform.md) des zones de votre œuvre.
- Animez avec la [ligne temporelle](animation-timeline.md), construisez des niveaux avec
  l'[éditeur de tilesets et de tilemaps](tileset-and-tilemap.md) et livrez vos ressources
  grâce à l'[exportation](export-and-pipeline.md).
- Accélérez les tâches répétitives avec l'[automatisation et les scripts](automation-and-scripting.md),
  dessinez plus précisément avec les [aides visuelles](visual-aids.md) et essayez les outils
  de [cloud](cloud-and-collaboration.md) et de [collaboration](collaboration.md) intégrés à
  la session (dans cette version, ils s'exécutent en mémoire à l'intérieur d'une seule
  fenêtre d'application et ne vous connectent pas à d'autres fenêtres ni à d'autres
  personnes).
