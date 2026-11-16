<!-- surface-only: bundle — contenu d'orientation dans l'application ; sans page de site, par conception -->
# Le canvas : zoom, déplacement et grille

Le **canvas** est la principale surface de dessin — une grande scène qui prend en charge des
documents allant jusqu'au maximum de la plateforme, **7680 × 4320 (8K)**. Il affiche votre
œuvre avec une mise à l'échelle au **plus proche voisin** et l'**anticrénelage désactivé**,
de sorte que les pixels restent toujours nets et carrés à n'importe quel zoom, exactement
comme doit se présenter le pixel art.

## Naviguer : zoom et déplacement

- **Zoom** — agrandissez pour travailler sur des pixels individuels et réduisez pour voir
  l'ensemble de l'œuvre. Le zoom est centré de sorte que le point situé sous le curseur ne
  bouge pas, ce qui vous garde repéré pendant que vous agrandissez et réduisez. Le zoom est
  une action de **vue** ; il ne modifie jamais votre œuvre et n'est pas une étape d'annulation.
- **100 % est le niveau de zoom le plus bas.** Vous ne pouvez plus réduire au-delà de 1:1,
  même sur un document plus grand que la fenêtre. En dessous de 100 %, un seul pixel du
  document peut tomber entre deux points d'échantillonnage de l'écran et tout simplement ne
  pas être dessiné — les traits semblaient disparaître lorsque vous réduisiez le zoom. Explorez plutôt un
  grand document en **déplaçant la vue** : chaque coin du canvas peut ainsi être amené au centre
  de la vue.
- **Déplacement** — faites défiler la vue horizontalement et verticalement pour atteindre
  n'importe quelle partie d'un grand canvas. La scène étant préparée une seule fois pour la
  taille complète du document, le déplacement sur un canvas 8K reste fluide — seule la partie
  du canvas visible dans la fenêtre d'affichage est dessinée, de sorte que les zones hors
  écran ne coûtent rien à parcourir.
- **Zoom avant** / **Zoom arrière** — **Ctrl++** et **Ctrl+-** passent d'un palier
  prédéfini à l'autre parmi les mêmes paliers fixes (100 %, 200 %, 400 %, 800 %, 1600 %,
  3200 %, 6400 %) : **Ctrl++** passe au palier suivant et **Ctrl+-** au palier précédent. Il
  s'agit d'un saut discret, à la différence du zoom continu ancré sur le curseur que vous
  obtenez avec **Shift+wheel** ci-dessous.

> **Les grands canvas restent réactifs.** Le moteur de rendu ne dessine que la région
> actuellement exposée dans la fenêtre d'affichage et ne repeint que la petite zone qu'une
> modification change réellement, si bien que peindre sur un canvas 8K reste dans le budget
> de 60 images par seconde.

## Le damier délimite votre canvas

Le damier de transparence n'est pas une décoration derrière l'œuvre — il **est le réseau de
pixels** : un carré alterné du damier correspond exactement à un pixel du document. Le damier
est aussi borné : il s'arrête exactement au bord du canvas, une couleur d'espace de travail
unie remplit la zone environnante et une fine bordure trace la limite entre les deux, de
sorte que vous voyez toujours où s'arrête la surface de dessin. Auparavant, le damier se
prolongeait au-delà du canvas sans rien pour marquer le bord, ce qui permettait de prendre
facilement un carré du damier pour un pixel.

## La grille de pixels

La **grille de pixels** vous aide à placer les pixels avec précision ; elle est **activée par
défaut** pour un nouveau document.

- **Activez ou désactivez la grille** avec **Affichage ▸ Afficher la grille**. C'est une
  surimpression dessinée par-dessus l'œuvre — elle ne devient jamais une partie de vos pixels
  et n'apparaît jamais dans une exportation.
- La grille est lisible dans les thèmes clair et sombre, et elle est dessinée de façon à se
  distinguer nettement sur n'importe quelle couleur de l'œuvre.
- **Activée ne veut pas dire dessinée.** La grille n'apparaît qu'à partir du moment où le
  bord d'un pixel à l'écran mesure au moins 8 pixels d'écran de large. À un zoom de 100 %, un
  pixel du document est plus petit que cela ; vous ne verrez donc aucune ligne de grille même
  avec la grille activée — agrandissez et elles apparaissent. Si vous activez la grille et
  que rien ne change, c'est la raison ; il ne s'agit pas d'un bogue.
- Lorsque le zoom est très réduit, une grille dense serait illisible ; la surimpression cesse donc
  élégamment de s'afficher jusqu'à ce que vous agrandissiez de nouveau.

## Alignement

Avec **Affichage ▸ Aligner sur la grille** activé, les outils s'alignent sur la grille afin
qu'un trait se place exactement sur les limites des pixels. C'est particulièrement utile pour
placer des tuiles ou aligner des formes. L'alignement est un réglage de vue ou d'outil, pas
une modification.

## Peindre sur le canvas

- **Clic gauche** (et glisser) peint avec l'outil actif et la couleur active. La couleur
  active vient du [centre de couleurs](colour-hub.md) ou de la palette. Chaque trait compte
  pour une seule étape d'annulation.
- **Clic droit** ouvre le [centre de couleurs](colour-hub.md) contextuel au niveau du
  curseur, afin que vous puissiez choisir ou changer de couleur sans quitter le canvas.

## Redimensionner le canvas

**Image ▸ Taille du canvas…** modifie les dimensions du canvas elles-mêmes — sans
rééchantillonner un seul pixel. Saisissez une nouvelle largeur et une nouvelle hauteur
(chacune jusqu'au plafond de la plateforme, **7680 × 4320**, soit le 8K) et cliquez sur
**OK** ; chaque calque et chaque masque de chaque image d'animation est rogné ou complété à la nouvelle
taille, ancré en haut à gauche, de sorte que l'œuvre existante ne bouge jamais et que toute
zone nouvellement exposée est transparente. Cliquez sur **Annuler** pour laisser le document
exactement tel qu'il était. Le redimensionnement s'applique en une seule étape annulable.

Il s'agit d'une opération différente du rééchantillonnage de l'œuvre à une nouvelle
taille — la commande Taille du canvas ne modifie que la quantité de canvas ; elle n'étire ni
ne réduit jamais les pixels que vous avez déjà.

## Raccourcis du clavier et du pointeur

Ces raccourcis figurent ici plutôt que seulement dans le tableau de
[Notions de base de l'application](app-basics.md), car ce sont des opérations de vue du
canvas, et non des outils :

| Raccourci | Action |
| --- | --- |
| **Ctrl++** | Agrandir le canvas actif d'un palier prédéfini. |
| **Ctrl+-** | Réduire le canvas actif d'un palier prédéfini. |

Le canvas répond aussi à quelques gestes du pointeur qui ne touchent jamais votre œuvre —
chacun est une action de **vue**, exactement comme Zoom, et aucun n'est donc une étape
d'annulation :

| Geste | Résultat |
| --- | --- |
| **Wheel** | Avance la position courante dans les **Favoris**, la même que celle du [centre de couleurs](colour-hub.md), et définit la couleur active — un moyen de parcourir vos couleurs favorites sans même ouvrir le centre. |
| **Shift+wheel** | Le zoom continu ancré sur le curseur mentionné plus haut — le point situé sous le curseur ne bouge pas pendant que vous agrandissez ou réduisez. |
| **Shift+middle-click** | Cadre la vue sur les pixels peints, de sorte qu'une œuvre dont vous vous êtes éloigné par défilement ou par zoom n'est plus qu'à un geste de revenir dans la vue. |

## Sujets connexes

- Choisissez et gérez les couleurs dans [Le centre de couleurs du clic droit](colour-hub.md).
- Empilez et composez votre travail avec les [calques](layers.md).
- Sélectionnez et repositionnez des zones dans
  [Sélection et déplacement/copie flottants](selection-and-transform.md).
- Ajoutez des [grilles, repères et autres aides visuelles](visual-aids.md) non destructifs
  pour un placement précis.
