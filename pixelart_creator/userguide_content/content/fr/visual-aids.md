# Aides visuelles et ergonomie

La **couche d'aides visuelles** vous aide à *voir et placer* votre travail avec précision,
sans jamais modifier l'œuvre elle-même. Elle ajoute un **aperçu à taille réelle**, des
**repères et règles**, une **grille isométrique**, une **grille en perspective**, une
**planche de référence** à la PureRef, l'**édition multivue** et la **capture de timelapse**.

Chaque aide est **non destructive** : activer une grille, déposer un repère, ajouter une image
de référence, ouvrir une deuxième vue ou capturer un timelapse ne crée **aucune** étape
d'annulation et ne touche jamais à vos pixels. Seules les vraies modifications de dessin sont
annulables, et cette couche ne les change en rien.

> **De la géométrie testée, pas un bricolage d'interface.** Tout l'alignement, les
> graduations des règles et l'échelle de taille réelle proviennent d'un **moteur de géométrie
> pur, testé unitairement et sans aucun Qt**. Les surimpressions ne font que *rendre* ce que
> la géométrie renvoie — le calcul d'alignement est le même code que celui qu'exercent les
> tests, de sorte que l'alignement est correct et reproductible.

## Aperçu à taille réelle

Le panneau **Aperçu à taille réelle** montre votre document à sa **vraie taille physique**,
afin que vous puissiez juger de l'aspect réel d'un sprite ou d'une icône.

- L'aperçu met le document à l'échelle d'exactement `screen_DPI / doc_PPI` — les pixels par
  pouce du document (**72** par défaut) rapportés au DPI physique du moniteur. Rien d'autre
  n'est appliqué.
- C'est une vue en **lecture seule** du document **partagé** : elle **reflète vos
  modifications en direct** — dessinez sur le canvas et l'aperçu se met à jour en même temps que la modification, sans bouton d'actualisation.

> **Si la taille réelle semble fausse, étalonnez.** Certains moniteurs signalent une taille
> physique incorrecte (ou aucune), si bien que le DPI interrogé est faux. Cliquez sur
> **Étalonner…**, placez une règle contre la barre affichée à l'écran et saisissez sa
> longueur mesurée ; l'aperçu utilise alors le DPI que vous avez mesuré. L'échelle est aussi
> recalculée automatiquement quand vous déplacez la fenêtre vers un moniteur de résolution
> différente.

> **Le HiDPI est géré pour vous.** L'échelle est indépendante de l'appareil et Qt applique
> lui-même le rapport de pixels de l'appareil de l'écran — l'aperçu ne multiplie **pas** par le DPR (le
> faire doublerait l'échelle sur les écrans HiDPI).

## Repères et règles

Activez les **règles** pour obtenir une règle horizontale et une règle verticale avec un
**affichage des coordonnées** en direct, puis faites glisser des **repères** hors de celles-ci
pour aligner des éléments.

- **Créer un repère** — faites glisser depuis la règle du haut pour un repère horizontal, ou
  depuis la règle de gauche pour un repère vertical.
- **Alignement** — votre curseur s'aligne sur le repère le plus proche dans une petite
  tolérance. La tolérance est exprimée en **pixels d'écran** (**8 px** par défaut) et
  convertie en espace document selon le zoom actuel, si bien que l'« adhérence » est la même à
  tous les niveaux de zoom.
- Les graduations des règles suivent une échelle de **nombres ronds** `1 / 2 / 5 × 10ⁿ`, avec
  des libellés entiers simples, indépendants des paramètres régionaux.

Les repères relèvent de l'état de la vue (jusqu'à **256**). Ajouter, déplacer ou supprimer un
repère n'est jamais annulable.

## Grille isométrique

Activez la commande **Grille isométrique** pour dessiner sur un réseau de losanges **dimétrique 2:1**
(la norme isométrique du pixel art).

- La grille est tracée en projetant les cellules du réseau par une transformation
  monde↔écran **inversible**, et votre curseur **s'aligne sur le sommet de grille le plus
  proche** (avec un départage déterministe des égalités par arrondi au supérieur, de sorte
  qu'un point situé exactement entre deux sommets se résout toujours de la même manière).
- L'espacement de la grille (largeur de tuile) est limité à **2–1024 px**.
- L'**isométrique vrai** (environ `1.732:1`) est configurable si vous le préférez au
  dimétrique 2:1.
- Ouvrez **Aides visuelles ▸ Configurer la grille isométrique…**, juste à côté de la commande
  Grille isométrique, pour définir des valeurs exactes au lieu de les évaluer à l'œil : la **Largeur de tuile**, le **Rapport de tuile (W:H)** (2,0 pour le dimétrique, ~1,732 pour
  l'isométrique vrai) et les champs **Origine X** et **Origine Y** du réseau. Cliquez sur **OK** pour appliquer la
  nouvelle configuration à l'onglet actif, ou sur **Annuler** pour la laisser inchangée.

> **Les grilles s'estompent lorsque le zoom est réduit, pour des raisons de performance.** Quand le bord d'une
> tuile à l'écran passe sous **32 px**, le réseau est trop dense pour être lisible : la
> surimpression **n'est donc plus tracée** plutôt que de faire dépasser le budget de 16 ms par
> image rendue. Zoomez de nouveau et elle réapparaît.

## Grille en perspective

Activez la commande **Grille en perspective** pour dessiner en perspective à **1, 2 ou 3 points**.

- Vous placez les **points de fuite** (jusqu'à **3**) ; la surimpression trace depuis chacun
  un **faisceau de lignes de guidage** déterministe, ainsi que la ligne d'horizon.
- La direction de votre curseur **se verrouille sur la ligne de fuite la plus proche**
  lorsqu'elle se trouve dans la tolérance d'alignement ; au-delà de la tolérance, il n'y a
  **aucun alignement**, de sorte que vous pouvez toujours dessiner librement.

## Planche de référence

La **planche de référence** est une planche à la PureRef, dans sa **propre** fenêtre, où vous
pouvez rassembler de l'inspiration à côté de votre canvas.

- **Ajoutez** des images, puis **déplacez**-les, **mettez-les à l'échelle** et réglez leur
  **ordre d'empilement** une par une ; déplacez et zoomez toute la planche ; et gardez au besoin la fenêtre au premier plan avec **Toujours au premier plan**.
- La planche contient jusqu'à **256** images et est **totalement distincte de votre
  œuvre** — les images de référence ne sont jamais composées dans le document et n'apparaissent
  jamais dans une exportation.
- **Enregistrez / ouvrez** une planche sous la forme d'un fichier `.pixboard`. La disposition
  fait l'aller-retour à l'identique. Un fichier de planche mal formé produit un message
  d'erreur clair — il ne fait jamais planter l'application et n'exécute jamais rien de ce qui
  se trouve dans le fichier.

## Édition multivue

Ouvrez **plusieurs vues du même document** à la fois — par exemple une vue de détail zoomée
à côté d'une vue d'ensemble ajustée à la fenêtre.

- Chaque vue supplémentaire affiche l'**unique document partagé**, si bien qu'une
  modification faite dans le canvas principal apparaît dans **chaque** vue (et dans l'aperçu
  à taille réelle) **immédiatement, sans actualisation manuelle**.
- Chaque vue conserve son **propre** zoom et son propre déplacement — ils sont définis par vue et **ne sont pas** synchronisés.
- Jusqu'à **8** vues simultanées (le canvas principal compte pour une). Les vues
  supplémentaires servent uniquement à la navigation (défilement / zoom) ; la peinture reste
  sur le canvas principal.

> **Plusieurs *vues* ou plusieurs *canvas*.** C'est différent de
> [plusieurs canvas](multi-canvas.md) : ceux-ci sont des onglets **isolés**, chacun étant un
> document *différent* avec ses propres calques et son propre historique d'annulation.
> L'édition multivue ouvre plusieurs fenêtres sur **un seul** document, qui restent
> synchronisées.

## Capture de timelapse

Ouvrez le panneau **Timelapse** depuis **Aides visuelles ▸ Timelapse** pour capturer et relire
un timelapse de votre session d'édition, afin de partager la façon dont une œuvre a été
réalisée.

- Appuyez sur **Lancer la capture** pour commencer ; la capture ajoute **une image de capture par modification validée** (chaque commande annulable). Appuyez de nouveau dessus pour
  arrêter.
- La capture relève de l'**état de la vue ou de la session** — elle n'est jamais annulable et
  ne modifie jamais le document.
- Les boutons **Enregistrer…** et **Ouvrir…** enregistrent ou ouvrent la session sous la forme
  d'un fichier `.pixtimelapse` (ils ouvrent les boîtes de dialogue de fichier
  **Enregistrer le timelapse** et **Ouvrir un timelapse**). La session conserve un manifeste
  ordonné de **références de commandes, et non de pixels**, de sorte qu'elle reste petite et
  se **rejoue de façon déterministe** : une même session capturée, rejouée deux fois, donne la
  **même** séquence d'images. Les sessions sont limitées à **4096** images capturées ; un fichier mal
  formé produit une erreur visible.

### Lecture

Une fois qu'une session est capturée ou ouverte, le même panneau la relit :

- **Lecture** / **Pause** bascule la lecture de la séquence d'images reconstituée ;
  **Arrêter** l'interrompt. Un contrôle de **position** absolue saute directement à
  n'importe quelle image, et un sélecteur de **vitesse** (0.25x, 0.5x, 1x, 2x, 4x) change la
  vitesse d'avancement des images — rien de tout cela ne touche à votre document, et tant que
  la lecture est en cours (ou en pause au milieu de la séquence), les modifications du
  document sont refusées jusqu'à ce que vous arrêtiez.
- Lire une session que vous avez **ouverte** depuis un fichier `.pixtimelapse` (plutôt
  qu'une session que vous venez de capturer) affiche une bannière **Capture rouverte**, qui
  vous rappelle qu'elle rejoue la capture enregistrée, et non votre document actuel.
- La lecture peut refuser de reconstituer une image donnée plutôt que d'en montrer une
  fausse. Vous pouvez voir apparaître : la capture ne contient aucune donnée reconstituable ;
  les données d'une image sont incomplètes ; une position demandée dépasse la plage
  capturée ; l'historique de la capture ne correspond plus à l'historique d'annulation actuel
  du document ; ou une image n'a pas l'identité stable dont la lecture a besoin. Chaque refus
  est signalé par un message clair et précis — jamais par un saut silencieux ni un plantage.

> **L'exportation en vidéo ou en GIF est une étape ultérieure.** Cette version produit la
> **séquence d'images** reproductible et sa propre lecture. L'encoder en vidéo ou en GIF
> partageable réutilise le [pipeline d'exportation](export-and-pipeline.md) dans une évolution ultérieure — la séquence capturée en est l'entrée.

## Accessibilité, thèmes et langues

Chaque contrôle d'aide visuelle porte un nom accessible (et une description lorsqu'elle
n'est pas évidente), s'utilise au clavier avec un indicateur de focus visible, s'affiche
correctement dans les thèmes **clair et sombre** (les couleurs des surimpressions et des
repères sont définies une seule fois par rôle et restent lisibles par-dessus l'œuvre), et son texte peut être **entièrement traduit** et se met à jour lors d'un changement de
langue.

## Ce qui n'est pas couvert

- **Exporter un timelapse en vidéo ou en GIF** — reporté au pipeline d'exportation ; cette
  version fournit la séquence reproductible.
- Une **bibliothèque d'images de référence hébergée / dans le cloud** — la planche proposée
  ici est locale.
- L'**inférence de perspective assistée par IA / la détection automatique des points de
  fuite** — phase ultérieure.
