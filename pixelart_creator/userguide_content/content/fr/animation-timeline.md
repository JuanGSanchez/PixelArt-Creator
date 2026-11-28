# La ligne temporelle d'animation

Le **système d'animation** transforme la liste des images d'animation d'un document en une
*ligne temporelle* : ajoutez, supprimez, réorganisez et dupliquez des images ; donnez à
chaque image sa propre durée d'affichage à l'écran ; lisez la séquence dans l'un des quatre
modes ; voyez les images voisines grâce à la pelure d'oignon ; et regroupez des plages
d'images en **animations nommées** à l'aide d'étiquettes d'images. Chaque modification d'une
image ou d'une étiquette constitue une seule étape d'annulation.

Cela rejoint **Aseprite** pour la ligne temporelle, la lecture, la pelure
d'oignon et les étiquettes, et le dépasse avec **plusieurs animations nommées indépendantes
dans un même fichier** (marche, course, repos) grâce aux étiquettes d'images.

> **Calques indépendants pour chaque image.** Chaque image possède sa **propre** pile de
> calques, composée avec le même [moteur de calques](layers.md) (la visibilité, l'opacité, le
> mode de fusion, les groupes et les masques sont tous pris en compte image par image). Sur
> un document **indexé**, une image est un unique calque indexé, et la pelure d'oignon n'est
> pas affichée (le compositeur ne gère que le RGBA).

## La bande d'images

Le panneau **Ligne temporelle** présente le document sous la forme d'une bande horizontale
d'images, dans l'ordre de lecture (de gauche à droite) ; chaque cellule comporte une
vignette, son numéro d'image et les marqueurs d'étiquette qui la recouvrent. Le panneau des
calques reflète les calques de l'image actuellement active.

- **Sélectionner une image** — cliquez dessus (ou utilisez les touches fléchées). Le canvas
  affiche la pile de calques composée de cette image. La sélection est une action de vue :
  elle n'est **pas** annulable.
- **Défilement manuel** — appuyez puis faites glisser le long de la bande ; le canvas
  affiche en continu l'image située sous le curseur. Le défilement manuel n'est lui non plus
  **pas** annulable.

## Gérer les images

La barre d'outils de la ligne temporelle modifie la séquence. Chaque action constitue
**exactement une étape d'annulation** :

| Action | Effet |
| --- | --- |
| **Ajouter une image** | Insère une nouvelle image à calque vide après l'image active. |
| **Supprimer l'image** | Supprime l'image active. **Désactivé quand il ne reste qu'une seule image** — un document conserve toujours au moins une image. |
| **Dupliquer l'image** | Insère une **copie profonde et indépendante** après la source (ses calques et sa durée sont copiés). Modifier la copie ne change jamais l'original. |
| **Faire glisser une image** | Faites glisser une cellule vers une nouvelle position pour la **réorganiser**. La lecture et le défilement manuel suivent le nouvel ordre. |

L'annulation restaure exactement la séquence précédente — contenu, ordre et durées.

## Durée de chaque image

Chaque image a sa propre **durée** en millisecondes, affichée dans l'éditeur de durée de la
bande (les nouvelles images prennent par défaut la durée d'image standard). Saisissez une
nouvelle valeur et validez-la (Enter / perte du focus) pour définir le temps d'affichage de
cette image en une seule étape d'annulation. Les durées doivent être **positives** : une
valeur nulle ou négative est refusée. Une image de 500 ms reste affichée environ cinq fois
plus longtemps qu'une image de 100 ms pendant la lecture.

> **Cadence uniforme.** Une cadence uniforme en images par seconde (FPS) revient simplement
> à donner la même durée à chaque image (`duration_ms = round(1000 / fps)`). Les
> millisecondes propres à chaque image restent toujours la source unique du minutage de la
> lecture.

## Lecture

Les **contrôles de lecture** pilotent l'image affichée au fil du temps :

- **Lecture** démarre (ou reprend après une pause) sur l'ensemble du document.
- **Pause** fige l'affichage sur l'image actuelle.
- **Arrêter** interrompt la lecture et revient à l'image qui était active au moment où vous
  avez appuyé sur Lecture.
- **Space** bascule entre lecture et pause.

Le **sélecteur de mode** détermine la façon dont la séquence avance (par défaut **Boucle**) :

| Mode | Comportement sur une plage de 4 images |
| --- | --- |
| **Boucle** | `0,1,2,3,0,1,2,3,…` — revient au début indéfiniment. |
| **Une fois** | `0,1,2,3` puis **s'arrête** sur la dernière image. |
| **Inverse** | `3,2,1,0,3,2,1,0,…` — revient au début à rebours, indéfiniment. |
| **Ping-pong** | `0,1,2,3,2,1,0,1,2,3,…` — fait des allers-retours ; les **extrémités ne sont pas doublées**. |

La lecture respecte la durée propre à chaque image : modifier une durée change donc le temps
d'affichage de cette image au passage suivant.

> **La première lecture d'une grande animation se prépare hors du fil d'exécution principal.** La
> première fois que vous lisez une plage sur un grand document multicalque (par exemple en
> 8K), le composite aplati de chaque image doit être construit une fois. Cela se fait **hors
> du fil d'exécution de l'interface** avec une petite barre de progression **annulable** dans la barre
> d'état — la fenêtre reste réactive, et la lecture **diffuse** les images au fur et à
> mesure qu'elles sont prêtes au lieu de se figer. Une fois les images préparées, elles sont
> mises en cache : la relecture et le défilement manuel tournent alors à 60 images par
> seconde.

## Pelure d'oignon

La pelure d'oignon affiche les **images voisines** derrière celle que vous modifiez, afin
que vous puissiez aligner le mouvement.

- **Activez**-la avec la case **Activer la pelure d'oignon** du panneau Pelure d'oignon. Les
  images fantômes s'affichent derrière l'image active ; l'image active elle-même reste
  inchangée.
- Définissez le nombre d'images **précédentes** et **suivantes** à afficher (chaque `0`
  désactive ce côté ; par défaut **1 précédente / 1 suivante**).
- Définissez la **teinte** de chaque côté — **rouge** pour les images précédentes, **bleu**
  pour les suivantes par défaut. Les images plus éloignées s'estompent.

Les nombres d'images et les teintes de la pelure d'oignon sont des **réglages de vue** — les
modifier met à jour la surimpression en direct et ne crée **aucune** étape d'annulation. La
pelure d'oignon **n'est pas affichée pendant la lecture** (c'est une aide à l'édition, pas un aperçu) ni pendant un défilement manuel.

## Étiquettes d'images (animations nommées)

Une **étiquette d'image** nomme une plage d'images comme sa propre animation. Un même fichier
peut contenir plusieurs étiquettes — par exemple `walk` sur les images 1–4, `idle` sur
l'image 0 — et elles peuvent se chevaucher.

Depuis le panneau **Étiquettes d'images** :

- **Ajouter une étiquette** / **Modifier l'étiquette** — chacune ouvre une boîte de dialogue
  pour le **Nom** de l'étiquette, la plage inclusive (**De l'image** / **À l'image**), le **Mode** de lecture, le champ **Répétitions** (`0` = infini pour les modes en boucle) et la **Couleur**. **Supprimer l'étiquette** supprime immédiatement l'étiquette
  sélectionnée, sans boîte de dialogue, et n'est disponible que lorsqu'une étiquette est
  sélectionnée. Chaque modification constitue **une étape d'annulation**. Une étiquette
  s'affiche sous la forme d'une bande qui s'étend sur les images qu'elle recouvre.
- **Lire l'étiquette** lit l'étiquette sélectionnée comme sa propre animation nommée : elle
  exécute la plage de l'étiquette selon le mode de lecture et les répétitions **propres à
  l'étiquette**, indépendamment du mode de lecture global. Une étiquette **Une fois** avec 3
  répétitions lit sa plage trois fois, puis s'arrête.

Quand vous ajoutez ou supprimez des images, les plages des étiquettes restent
automatiquement valides (ramenées aux limites du nouveau nombre d'images) ; l'annulation restaure
ensemble la modification des images et les plages d'origine des étiquettes.

## Vue en grille (la grille de cels)

Le commutateur **Vue en grille** de la barre d'outils de la ligne temporelle fait passer de
la bande horizontale d'images à une **grille de cels** : les images en colonnes, les pistes de
calques en lignes, dans le même style que la grille de cels d'Aseprite. Elle montre le même
document que la bande — basculer d'un affichage à l'autre ne vous fait jamais perdre votre
place.

- **Déplacer / copier un cel** — faites glisser une cellule contenant un cel pour le
  déplacer vers une autre image ou une autre piste ; maintenez **Ctrl** enfoncé pendant le
  glissement pour le copier plutôt que le déplacer, en laissant la source où elle est. Les deux opérations
  constituent une seule étape d'annulation. C'est un geste **différent** de **Ctrl+glisser**
  sur le canvas, qui copie toujours une sélection flottante — voir
  [Sélection et déplacement/copie flottants](selection-and-transform.md#copy-instead-of-move-hold-ctrl)
  — le modificateur est le même, mais celui qui s'applique dépend de l'endroit où vous
  faites glisser.
- **Confirmation d'écrasement** — déposer sur une cellule qui contient déjà un cel ouvre la
  boîte de dialogue **Écraser le cel existant ?** Cochez sa case
  **« Ne plus demander pour ce projet »** pour ne plus être interrogé pendant le reste de ce
  projet ; voir [Confirmations du projet](#project-confirmations) ci-dessous pour réactiver
  cette confirmation.
- **Basculer la visibilité du cel** — cliquez sur l'indicateur de visibilité d'une cellule
  pour afficher ou cacher le calque de cette image ; c'est une étape d'annulation, comme pour
  toute autre bascule de visibilité.
- **Créer un cel ici** — faites un clic droit (ou utilisez la touche de menu contextuel du
  clavier) sur une cellule vide pour obtenir l'action **« Créer un cel ici »**. Elle n'est
  pas proposée du tout quand la cellule est déjà occupée, ni quand l'image a déjà atteint le
  nombre maximal de calques — le menu ne propose jamais une action qui serait simplement
  refusée.
- **Défilement manuel** — faites glisser sur des cellules vides de la grille pour faire défiler manuellement l'image affichée, exactement comme en faisant glisser le long de la bande.
- **Réorganiser les colonnes** — faites glisser un en-tête de colonne pour réorganiser les
  images, l'équivalent dans la grille du glissement d'une cellule de la bande.

### Confirmations du projet

La confirmation d'écrasement de la vue en grille fait partie des préférences propres à
chaque projet de l'application : une fois masquée avec « Ne plus demander pour ce
projet », elle reste désactivée pour ce projet jusqu'à ce que vous la rétablissiez depuis
**Édition ▸ Confirmations du projet**, qui liste chaque confirmation masquée et permet de
les réactiver une à une.

## Gestes du pointeur

La bande d'images répond à quatre gestes du pointeur combinés à **Ctrl**, en plus des
boutons de la barre d'outils décrits dans [Gérer les images](#managing-frames) ci-dessus :

| Geste | Résultat |
| --- | --- |
| **Ctrl+wheel** | Passe le document actif à l'image suivante / précédente. |
| **Ctrl+middle-click** | Saute directement à l'image 1 du document actif. |
| **Ctrl+left-click** | Ajoute une image après l'image active — la même action annulable que le bouton **Ajouter une image**. |
| **Ctrl+right-click** | Supprime l'image active — la même action annulable que le bouton **Supprimer l'image**, et **propre à la ligne temporelle** : elle n'a aucun équivalent dans la vue en grille. Comme le bouton, elle est refusée sur la dernière image d'un document, car un document en conserve toujours au moins une. |

## Persistance

Les images, leurs durées et les étiquettes d'images sont toutes conservées lors d'un
aller-retour dans un fichier `.pixproj`. Enregistrer puis rouvrir une animation étiquetée
restaure l'ordre des images, la durée de chaque image et l'ensemble des étiquettes à
l'identique. Les projets enregistrés par des versions antérieures (avant l'existence des
étiquettes) s'ouvrent toujours — ils se chargent avec une collection d'étiquettes vide.

## Annuler, rétablir et ce qui n'est *pas* annulable

- **Annulable (une étape par action) :** ajouter / supprimer / réorganiser / dupliquer une
  image, définir la durée d'une image, créer / modifier / supprimer une étiquette et — dans
  la vue en grille — déplacer / copier un cel, basculer la visibilité d'un cel et créer un
  cel.
- **Non annulable (état de la vue) :** sélectionner une image ou la faire défiler
  manuellement, lire / mettre en pause / arrêter, modifier les nombres d'images ou les
  teintes de la pelure d'oignon, et basculer entre la bande et la vue en grille.

## Sujets connexes

- Exportez votre animation en GIF, en feuille de sprites ou en atlas dans
  [Exportation et intégration au pipeline](export-and-pipeline.md).
- Capturez une session pendant que vous animez avec l'outil de timelapse dans
  [Aides visuelles et ergonomie](visual-aids.md).
