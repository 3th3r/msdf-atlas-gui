# msdf-atlas-gui

Interface graphique simple pour msdf-atlas-gen (https://github.com/Chlumsky/msdf-atlas-gen).
L'outil construit une ligne de commande à partir des champs, l'affiche, puis l'exécute via `subprocess`.

## Contraintes
- Python 3, bibliothèque standard uniquement, interface en **Tkinter** (ttk). Aucune dépendance pip.
- Cible : Windows. Un seul fichier principal : `msdf_atlas_gui.py`.
- Le chemin de `msdf-atlas-gen.exe` est saisi dans un champ et mémorisé dans `settings.json`
  (à côté du script, ignoré par Git et Perforce), avec les derniers réglages utilisés.
- Git est la référence. Ne jamais faire de commit ni toucher à Perforce sans demande explicite.

## Champs de l'interface → options CLI
| Champ | Option |
|---|---|
| Exécutable msdf-atlas-gen (Parcourir…) | — |
| Font (.ttf / .otf, Parcourir…) | `-font <path>` |
| Type (liste : hardmask, softmask, sdf, psdf, msdf, mtsdf ; défaut msdf) | `-type <type>` |
| Charsets : cases à cocher sur **une seule ligne** | `-chars "<plages>"` |
| Taille des glyphes (px/em) | `-size <n>` |
| Cellules uniformes : bouton on/off + X Y | `-uniformgrid -uniformcell <X> <Y>` (rien si off) |
| Range SDF (px) | `-pxrange <n>` |
| Dimensions atlas X Y + case « Square » (si cochée : un seul champ X) | `-dimensions <X> <Y>` ou `-dimensions <X> <X>` |
| Sortie image (Parcourir… + case « Nom auto ») | `-imageout <path>.png` |
| Case CSV (+ nom auto ou chemin libre) | `-csv <path>.csv` |
| Case JSON (+ nom auto ou chemin libre) | `-json <path>.json` |

## Charsets (syntaxe `-chars`, plages séparées par des virgules)
| Case | Nom court | Plages |
|---|---|---|
| Majuscules | `upper` | `[0x41, 0x5A]` |
| Minuscules | `lower` | `[0x61, 0x7A]` |
| Chiffres | `digits` | `[0x30, 0x39]` |
| Ponctuation ASCII (espace inclus) | `punct` | `[0x20, 0x2F], [0x3A, 0x40], [0x5B, 0x60], [0x7B, 0x7E]` |
| Latin-1 | `latin1` | `[0xA0, 0xFF], 0x20AC` (€ ajouté) |
| Latin Extended-A | `latinExtA` | `[0x100, 0x17F]` |
| Grec | `greek` | `[0x370, 0x3FF]` |
| Cyrillique | `cyrillic` | `[0x400, 0x4FF]` |

Au moins une case doit être cochée.

## Nom automatique
- Format : `<NomDeLaFont>_<charsets>`. Par exemple `Roboto-Regular_upper-lower-digits`.
- Si les quatre cases de base (upper, lower, digits, punct) sont cochées, elles sont regroupées sous `ascii`.
  Par exemple `Roboto-Regular_ascii-latin1`.
- Le dossier de sortie reste choisi par l'utilisateur. Seul le nom de fichier est automatique.
- Le CSV et le JSON prennent le même nom de base que l'image, sauf si leur case « Nom auto » est décochée.
- Le nom se met à jour en direct quand la font ou les charsets changent.

## Comportement
- Aperçu de la commande complète, en lecture seule et copiable, mis à jour en direct.
- Bouton « Générer » : exécution dans un thread, avec stdout et stderr affichés dans une zone de log.
  L'interface ne doit pas se figer.
- Validation avant exécution : exe et font existants, valeurs numériques valides, au moins un charset.
- Le comportement de `-dimensions` combiné à `-uniformcell` a été vérifié : si la grille ne tombe pas juste,
  msdf-atlas-gen arrondit à l'inférieur et passe à la ligne suivante. Aucun traitement particulier n'est nécessaire.
