# Plusieurs canvas (plans de travail)

Vous pouvez ouvrir plusieurs documents ou plans de travail à la fois, chacun dans son propre
**onglet**.

## Onglets isolés

Chaque canvas ouvert est entièrement **isolé quant à son état**. Un onglet possède en propre :

- son arborescence de calques (calques, groupes, masques, calques de référence ou
  intelligents) ;
- sa palette et son mode de couleur ;
- son historique d'annulation / de rétablissement ;
- sa vue composée et la géométrie de son canvas.

Passer à un onglet fait de ce canvas le contexte actif — son arborescence de calques, sa
palette, sa pile d'annulation et sa composition deviennent celles en cours, et le panneau des
calques se remplit de nouveau pour s'y accorder.

Les onglets étant isolés, une opération dans un canvas n'affecte **jamais** un autre :
peindre, changer des attributs de calque, réorganiser, grouper ou annuler dans l'onglet A
laisse l'arborescence, la composition et l'historique d'annulation de l'onglet B intacts.

## Travailler entre plans de travail

- Chaque plan de travail peut avoir une taille de canvas, une palette et un mode de couleur
  différents.
- L'annulation est propre à chaque onglet : annuler ne franchit pas les plans de travail.
- Enregistrer un document écrit l'arborescence de calques propre à cet onglet dans son
  fichier `.pixproj`.

> **Astuce.** Utilisez des plans de travail séparés pour les variantes d'un même sprite (par
> exemple des échanges de couleurs ou des poses) afin que leurs historiques de modification
> restent indépendants.

## Plusieurs *canvas* ou plusieurs *vues*

Plusieurs canvas sont des onglets **isolés** — chacun étant un document *différent*. C'est
différent de l'**édition multivue**, qui ouvre plusieurs fenêtres synchronisées sur **un seul**
document partagé. Voir [Aides visuelles et ergonomie](visual-aids.md) pour l'édition
multivue.
