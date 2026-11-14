# Automatisation, macros, scripts et plugins

Le **système d'automatisation** vous permet de capturer, de scripter, de rejouer et de traiter
par lot les propres opérations de l'éditeur, de générer du contenu de façon procédurale et
d'étendre l'application avec des plugins de confiance — le tout via **un seul** moteur que
partagent l'interface graphique et la ligne de commande sans interface `pixelart-run`, si bien
qu'une automatisation s'exécute **de la même façon**, que vous la déclenchiez depuis un panneau
ou depuis un script de build.

> **Sécurité dès la conception — jamais d'`eval`.** Le scriptage est un **DSL de commandes
> borné et piloté par les données**, et non du Python arbitraire. Une automatisation est une
> *liste validée d'opérations* (`{name, params, seed}`), jamais un langage : il n'y a **aucun
> `eval` / `exec` / `compile` / `__import__` appliqué à vos entrées** nulle part sur ce chemin —
> il n'y a pas d'interpréteur dont s'échapper. Un unique répartiteur de confiance compare le nom
> de chaque opération à une **liste d'autorisation** et ses paramètres à un schéma déclaré avant
> de construire la commande réversible correspondante.

## Macros — capture, relecture et format `.pixmacro`

Le panneau **Macros** capture les opérations que vous effectuez et les rejoue plus tard :

- **La capture** enregistre les *entrées* de chaque étape — les paramètres résolus et, pour toute
  étape aléatoire, la **graine** — et non une différence de pixels. Ce que vous capturez est ce
  qu'une relecture réexécute.
- **Rejouer** réapplique les opérations capturées au document actuel **en une seule étape
  d'annulation**, si bien que l'annulation défait toute la macro d'un seul coup.

Une macro est stockée dans un fichier **`.pixmacro`** — du JSON brut avec une enveloppe
versionnée :

```
{
  "format": "pixmacro",
  "schema_version": "1",
  "min_app_version": "0.8.0",
  "api_version": "1",
  "ops": [
    { "op": "batch_recolour", "params": { }, "seed": null },
    { "op": "procgen",        "params": { }, "seed": 12345 }
  ]
}
```

- **`schema_version` / `api_version` / `min_app_version`** sont vérifiés au chargement : une
  version inconnue ou non prise en charge **échoue explicitement** avec une erreur claire, plutôt
  que de rejouer la macro de travers.
- **`params`** sont natifs JSON : enregistrer puis charger une macro redonne donc une macro
  **identique** — les couleurs et les cartes d'indices circulent sous forme de listes.
- **`seed`** est enregistré pour chaque étape aléatoire afin que la relecture soit reproductible.

> **Relecture déterministe.** Rejouer deux fois la même macro sur le même document de départ
> donne un document **dans exactement le même état**. Chaque étape aléatoire ne puise que dans sa graine
> enregistrée — ni horloge système, ni aléa sans graine, ni dépendance aux paramètres
> régionaux. C'est ce qui permet d'exécuter une macro sans risque dans un pipeline de build.

Le chargement d'un `.pixmacro` est **défensif** : chaque champ est vérifié en type, en bornes et
en version, un document mal formé ou hors bornes lève une erreur claire, et le contenu n'est
**jamais** transmis à `eval`/`exec`.

## Exécuter des scripts

L'**Exécuteur de scripts** transmet une liste d'opérations au même répartiteur de confiance
que celui d'une relecture de macro. Une exécution de script est **atomique** :

1. **Chaque opération est validée d'emblée** — tous les noms d'opération sont comparés à la
   liste d'autorisation et tous les paramètres à leur schéma **avant que quoi que ce soit ne
   soit appliqué**.
2. L'exécution entière est appliquée comme **une seule commande groupée et réversible**.
3. Si une opération échoue en cours de route, les opérations déjà appliquées sont **annulées
   dans l'ordre inverse**, si bien qu'une exécution de plusieurs opérations qui échoue laisse le
   document **inchangé** — jamais à moitié appliquée.

Comme l'exécution est une seule commande groupée, un script terminé constitue **une seule étape
d'annulation**.

## Plugins — le gestionnaire, le consentement et le modèle de confiance

Le panneau **Plugins** détecte, active et désactive les plugins. Les plugins étendent l'éditeur
en ajoutant de nouvelles opérations au DSL — et rien d'autre.

- **La détection est inerte.** Les plugins installés sont *trouvés* (via les points d'entrée
  Python standard), mais **rien n'est chargé ni exécuté** du seul fait qu'un plugin est installé.
  Vous les voyez listés ; ils ne font rien tant que vous n'agissez pas.
- **Refus par défaut, avec consentement explicite.** Activer un plugin lui remet un **objet de
  capacités dont la seule surface est le registre de commandes du DSL**. À travers cet objet, un
  plugin ne peut rien faire de ce qu'il n'a pas déclaré — **toute capacité qu'il n'a pas déclarée
  est refusée**. Vous approuvez en bloc les permissions déclarées d'un plugin, ou vous ne
  l'activez pas. Activer un plugin dans le panneau n'exécute pas, en soi, le code du plugin. Ses
  opérations sont placées dans l'espace de noms du plugin, si bien qu'un plugin ne peut pas
  supplanter une opération intégrée. Cela limite ce que le plugin peut faire *à travers
  l'application* ; cela ne restreint pas le code propre du plugin (voir la note ci-dessous).
- **La désactivation est propre.** Désactiver un plugin retire les opérations qu'il avait
  ajoutées.

> **Confiance et consentement, dans cette version.** Comme *charger* un plugin Python
> revient déjà à exécuter du code, le modèle de capacités, qui s'applique dans le même processus
> que le code du plugin, n'offre qu'une protection **non contraignante** : elle limite ce que le plugin peut faire à travers l'application, mais pas ce que fait le code propre du plugin. Cette protection convient aux
> **extensions de confiance que vous installez et auxquelles vous consentez**, et non à du code
> arbitraire issu d'une place de marché non fiable. Le code d'un plugin s'exécute dans le même
> processus que l'éditeur, avec le même accès à vos fichiers et au réseau que l'application
> elle-même. N'installez que des plugins auxquels vous faites confiance.

## Recoloration par lot

La fonction **Recoloration par lot** applique une même correspondance de couleurs à **de nombreuses
cibles à la fois**, sous la forme d'**une seule commande transactionnelle et réversible** :

- Pour les cibles **indexées**, elle remappe les indices de palette (`old_index → new_index`) ;
  pour les cibles **RGBA**, elle remappe les couleurs (`old_rgba → new_rgba`). Elle réutilise les
  opérations de recoloration existantes de l'éditeur, si bien qu'une cible traitée par lot est
  **identique à l'octet près** à la même cible recolorée seule avec la même correspondance.
- Elle est **transactionnelle** : chaque cible est validée et son étape propre est construite
  **avant que quoi que ce soit ne soit appliqué**. Une cible invalide fait échouer l'opération en
  nommant la cible fautive, **sans aucune modification**. Le lot entier constitue **une seule étape
  d'annulation**.

## Génération procédurale

Le panneau **Génération procédurale** remplit une région avec du contenu généré. Cinq
générateurs internes, **à graine**, sont disponibles :

| Générateur | Ce qu'il produit |
| --- | --- |
| **Bruit de valeur** | Un bruit de grille de valeurs, à graine. |
| **Bruit de gradient** | Un bruit de gradient de type Perlin. |
| **Bruit OpenSimplex** | Un bruit de gradient sur grille simplexe, sans risque de brevet. |
| **Automates cellulaires** | Des motifs d'automates cellulaires. |
| **Dégradé tramé** | Un dégradé bicolore lisse, tramé sur la palette du document, de sorte que le résultat reste dans la palette. |

Chaque générateur est une **fonction pure et déterministe de ses paramètres et de sa graine** —
la même graine et les mêmes paramètres produisent toujours la même sortie. Le contenu généré est
écrit par le **chemin des commandes réversibles**, si bien que toute génération constitue une
seule étape d'annulation. La sortie est bornée sur chaque axe par le plafond de dimension de la
génération procédurale de la plateforme.

## Réversibilité et réactivité

Chaque automatisation — relecture de macro, exécution de script, recoloration par lot,
remplissage procédural — se place sur la **pile d'annulation normale en une seule étape**, si
bien que vous pouvez toutes les annuler. Dans l'interface graphique, l'automatisation s'exécute
sur une **tâche d'arrière-plan** avec un arrêt déterministe, de sorte qu'un long lot ou un grand
remplissage procédural ne fige pas la fenêtre.

## La ligne de commande `pixelart-run`

Pour l'automatisation et l'intégration continue, `pixelart-run` rejoue un `.pixmacro` sur un
`.pixproj` **en mode sans fenêtre** (sans interface graphique), via le **même** répartiteur de confiance
que celui que pilote l'interface graphique — le document obtenu est donc **dans exactement le même état** que celui que produit l'interface en exécutant la même automatisation sur la même entrée.

```
pixelart-run --input PROJECT.pixproj --macro MACRO.pixmacro --output OUT.pixproj [options]
```

| Option | Signification |
| --- | --- |
| `--input PATH` | **(obligatoire)** le projet `.pixproj` source sur lequel exécuter la macro. |
| `--macro PATH` | **(obligatoire)** la macro `.pixmacro` à rejouer. |
| `--output PATH` | **(obligatoire)** le chemin `.pixproj` où écrire le résultat. |
| `--seed N` | remplace la graine des opérations qui n'en ont enregistré aucune (une graine enregistrée l'emporte toujours). |
| `--param KEY=VALUE` | injecte ou remplace un paramètre de macro ; répétable. |

**Codes de sortie :** `0` succès ; `1` un échec d'automatisation (une erreur de script / de macro
/ de plugin / de lot / de génération procédurale, ou un échec d'écriture) ; `2` des arguments
incorrects ou un projet d'entrée mal formé ou illisible, ou une macro mal formée ou illisible.

> **Point d'entrée console.** `pixelart-run` est installé comme script console lors du
> `pip install`.

## Ce qui n'est pas couvert

- **Les scripts Python arbitraires** — **non pris en charge par conception.** Le scriptage est un
  DSL de commandes borné, à liste d'autorisation, et non un interpréteur généraliste ; c'est une
  frontière de sécurité délibérée, et non une limite appelée à disparaître.
- **L'isolation des plugins tiers non fiables** — **différée.** Dans cette version, les plugins sont admis sur la base de votre confiance et de votre consentement ; n'installez que des plugins auxquels vous faites
  confiance.

## Sujets connexes

- Les automatisations composent les mêmes opérations que vous pilotez à la main — voir les
  [calques](layers.md), l'[exportation](export-and-pipeline.md) et le
  [centre de couleurs](colour-hub.md).
