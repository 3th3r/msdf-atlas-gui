# msdf-atlas-gui

Interface graphique simple pour msdf-atlas-gen (https://github.com/Chlumsky/msdf-atlas-gen).
L'outil construit une ligne de commande à partir des champs, l'affiche, puis l'exécute via `subprocess`.

## Règle absolue
Ne rien écrire, créer, modifier, exécuter, déplacer ni supprimer sans avoir d'abord décrit précisément
l'action et obtenu l'accord explicite de l'utilisateur. Une demande de travail n'est pas une autorisation :
présenter le changement (diff), demander, attendre le « oui ».

## Contraintes
- Python 3, bibliothèque standard uniquement, interface en **Tkinter** (ttk). Aucune dépendance pip.
- Cible : Windows. Un seul fichier principal : `msdf_atlas_gui.py`.
- Toute l'interface est en **anglais** (libellés, messages, log, boîtes de dialogue).
- Le chemin de `msdf-atlas-gen.exe` est saisi dans un champ et mémorisé dans `settings.json`
  (à côté du script, ignoré par Git et Perforce), avec les derniers réglages utilisés.
- Git est la référence. Ne jamais faire de commit ni toucher à Perforce sans demande explicite.

## Chemins
- Dossier de base : **dossier qui contient `msdf_atlas_gui.py`**
  (`os.path.dirname(os.path.abspath(__file__))`), quel que soit le dossier depuis lequel il est lancé.
  Il sert de point de départ pour que rien ne renvoie par défaut vers `C:\` ou le dossier courant.
- Les chemins sont **enregistrés et affichés en absolu** (pas de conversion en chemin relatif).
- Les sélecteurs de fichiers s'ouvrent dans le dossier du chemin courant, ou dans le dossier de base si le champ est vide.
- Dossier de sortie par défaut : `<dossier de base>\output`.
- Un chemin relatif saisi à la main est résolu depuis le dossier de base. Les chemins relatifs d'un ancien
  `settings.json` sont convertis en absolu au chargement.
- Le process msdf-atlas-gen est lancé avec `cwd` = dossier de base. Un exe sans dossier est préfixé par `.\`.

## Valeurs par défaut
| Champ | Défaut |
|---|---|
| Type | `psdf` |
| Glyph size | `64` |
| Uniform cells | activé, `96` × `96` |
| SDF range | `8` |
| Atlas dimensions | `4096`, Square coché |

Ces valeurs ne s'appliquent que sans `settings.json` (ou pour une clé absente).

## Tests
- Exe msdf-atlas-gen à utiliser pour les tests (machine de l'utilisateur) :
  `D:\git\msdf-atlas-gen\Release\msdf-atlas-gen-1.4-win64\msdf-atlas-gen\msdf-atlas-gen.exe`
- **Uniquement pour les tests** : ce chemin ne doit jamais être écrit en dur dans le code ni servir de valeur par défaut.

## Champs de l'interface → options CLI
| Champ | Option |
|---|---|
| msdf-atlas-gen executable (Browse…) | — |
| Font (.ttf / .otf, Browse…) | `-font <path>` |
| Type (liste : hardmask, softmask, sdf, psdf, msdf, mtsdf ; défaut psdf) | `-type <type>` |
| Charsets : cases à cocher en **grille de 6 colonnes** + boutons All / None / Order… | `-chars "<plages>"` |
| Glyph size (px/em) | `-size <n>` |
| Uniform cells : bouton on/off + X Y | `-uniformgrid -uniformcell <X> <Y>` (rien si off) |
| SDF range (px) | `-pxrange <n>` |
| Atlas dimensions X Y + case « Square » (si cochée : un seul champ X) + liste « Preset » | `-dimensions <X> <Y>` ou `-dimensions <X> <X>` |
| Image output (Browse… + case « Auto name ») | `-imageout <path>.png` |
| Case CSV (+ auto name ou chemin libre) | `-csv <path>.csv` |
| Case JSON (+ auto name ou chemin libre) | `-json <path>.json` |

- Liste « Preset » (`ttk.Combobox` en lecture seule) : 256, 512, 1024, 2048, 4096.
  Choisir un preset coche « Square » et met X (et Y) à cette valeur. La liste affiche le preset
  correspondant aux valeurs courantes, ou reste vide si elles ne correspondent à aucun preset.

## Charsets
Ordre par défaut : **fréquence d'usage pour un utilisateur européen**, du plus commun au moins commun.
msdf-atlas-gen stocke le charset dans un `std::set` : les recouvrements entre plages sont sans effet.

| # | Case | Nom court | Abréviation | Plages |
|---|---|---|---|---|
| 1 | Basic Latin | `ascii` | `asc` | `[0x20, 0x7E]` |
| 2 | Latin-1 | `latin1` | `lt1` | `[0xA0, 0xFF]` |
| 3 | General Punct. | `punct` | `pun` | `[0x2000, 0x206F]` |
| 4 | Currency | `currency` | `cur` | `[0x20A0, 0x20BF]` |
| 5 | Latin Ext-A | `latinExtA` | `lxa` | `[0x100, 0x17F]` |
| 6 | Latin Ext-B | `latinExtB` | `lxb` | `[0x180, 0x24F]` |
| 7 | Greek | `greek` | `grk` | `[0x370, 0x3FF]` |
| 8 | Cyrillic | `cyrillic` | `cyr` | `[0x400, 0x4FF]` |
| 9 | Letterlike | `letterlike` | `let` | `[0x2100, 0x214F]` |
| 10 | Super/Subscripts | `supsub` | `sup` | `[0x2070, 0x209F]` |
| 11 | Number Forms | `numforms` | `num` | `[0x2150, 0x218F]` |
| 12 | Arrows | `arrows` | `arr` | `[0x2190, 0x21FF]` |
| 13 | Math Operators | `math` | `mth` | `[0x2200, 0x22FF]` |
| 14 | Geometric Shapes | `shapes` | `shp` | `[0x25A0, 0x25FF]` |
| 15 | Cyrillic Sup. | `cyrillicSup` | `cys` | `[0x500, 0x52F]` |
| 16 | Vietnamese | `vietnamese` | `vie` | voir ci-dessous |
| 17 | Combining marks | `combining` | `cmb` | `[0x300, 0x36F]` |

**Vietnamese** (doit fonctionner seul) :
- A-Z, a-z : `[0x41, 0x5A], [0x61, 0x7A]`
- voyelles accentuées Latin-1 : `0xC0-0xC3, 0xC8-0xCA, 0xCC, 0xCD, 0xD2-0xD5, 0xD9, 0xDA, 0xDD`
  et leurs minuscules `0xE0-0xE3, 0xE8-0xEA, 0xEC, 0xED, 0xF2-0xF5, 0xF9, 0xFA, 0xFD`
- ă Ă đ Đ ĩ Ĩ ũ Ũ : `0x102, 0x103, 0x110, 0x111, 0x128, 0x129, 0x168, 0x169`
- ơ Ơ ư Ư : `0x1A0, 0x1A1, 0x1AF, 0x1B0`
- voyelles précomposées avec ton : `[0x1EA0, 0x1EF9]`
- ₫ : `0x20AB`
- **Pas** de marques combinantes (sans ancres, elles s'affichent mal) : elles restent disponibles via « Combining marks ».

Au moins une case doit être cochée.

## Comptage des glyphes
- La font est lue en Python pur (`struct`) : table `cmap` (formats 4 et 12 ; pour un `.ttc`, la première font).
  Lecture refaite uniquement quand le chemin de la font change.
- **Glyphes d'un charset** = codepoints du charset présents dans la font, **moins les glyphes vides**
  (msdf-atlas-gen ne leur donne pas de cellule, cf. plus bas).
  - Font TrueType (`glyf`) : glyphe vide = entrée `loca` de longueur 0 (exact).
  - Font CFF (`.otf`) : liste fixe des codepoints blancs/invisibles Unicode
    (`0x20, 0xA0, [0x2000, 0x200F], 0x2028, 0x2029, 0x202F, 0x205F, [0x2060, 0x2064]`) (approché).
- **Glyphes d'un atlas** = union dédoublonnée des glyphes de ses charsets.
  Un glyphe présent dans deux atlas compte dans les deux.
- Font absente ou illisible : on compte les codepoints demandés (majorant) et on l'indique.
- **Capacité d'un atlas** (cellules uniformes actives) : `floor(dimX / cellX) × floor(dimY / cellY)`.
  Sans cellules uniformes, la capacité n'est pas calculable (packing serré, dépend des glyphes) : affichée `n/a`.

## Atlas multiples
Quand les glyphes ne tiennent pas dans un atlas, on en génère plusieurs, avec les mêmes options.

- Un charset n'est **jamais coupé** : il est entièrement dans un seul atlas.
- **Mode auto** (par défaut) : répartition recalculée en direct. On parcourt les charsets cochés dans l'ordre
  courant et on remplit l'atlas 1 tant que ça tient, puis l'atlas 2, etc. (un charset qui ne tient plus ouvre l'atlas suivant).
- **Mode manuel** : dès que l'utilisateur change un charset d'atlas dans la fenêtre « Charset order ».
  Le bouton « Auto split » revient au mode auto.
- Sans cellules uniformes : un seul atlas en mode auto (capacité inconnue). Le mode manuel reste possible.
- Erreurs bloquantes pour « Generate » (affichées en rouge dans la fenêtre et la ligne d'information) :
  - un atlas dépasse sa capacité (mode manuel) ;
  - un charset seul dépasse la capacité d'un atlas → augmenter les dimensions ou réduire les cellules.
- Sauvegarde dans `settings.json` : `charset_order` (ordre des 17), `charset_atlas` (nom court → numéro d'atlas),
  `atlas_mode` (`auto` / `manual`). Les noms inconnus sont ignorés, les charsets absents ajoutés à la fin (atlas 1).

### Fenêtre « Charset order »
- Ouverte par le bouton « Order… » (fenêtre modale `Toplevel`).
- Tableau (`ttk.Treeview`) à sections :
  - une section par atlas, en-tête `Atlas N — <glyphes> / <capacité> glyphs` (rouge si dépassement) ;
  - une section `Not selected` en bas pour les charsets non cochés (on peut quand même les ordonner).
- Colonnes des charsets : # | Charset | Abréviation | Chars (codepoints du charset) | Glyphs (présents dans la font, non vides).
- Réorganisation :
  - boutons Move up / Move down (sélection conservée) ; en haut ou en bas d'une section, le charset passe
    dans l'atlas précédent / suivant ;
  - glisser-déposer d'une ligne à la souris (déplacement en direct), y compris d'un atlas à l'autre ;
    déposer sur un en-tête d'atlas place le charset à la fin de cet atlas ;
  - « New atlas » ajoute une section vide en fin de liste ; les atlas vides sont supprimés à la validation
    et les suivants renumérotés ;
  - « Auto split », « Reset to default » (ordre du tableau ci-dessus, mode auto), OK / Cancel.
- Les compteurs se mettent à jour en direct pendant les déplacements.
- L'ordre détermine **l'ordre d'affichage des cases**, **l'ordre des noms dans le nom auto** et la répartition auto.
- À l'intérieur d'un atlas, l'ordre n'a **aucun effet sur l'image** (vérifié dans le code de msdf-atlas-gen :
  le charset est un `std::set`, les glyphes sont chargés et placés par codepoint croissant).

## Nom automatique
- Format : `<NomDeLaFont>_<charsets>` (abréviations dans l'ordre courant, séparées par `-`).
  Exemple : `Roboto-Regular_asc-lt1-pun`.
- Si **toutes** les cases sont cochées et qu'il n'y a qu'un atlas : `<NomDeLaFont>_all`.
- Plusieurs atlas : chaque atlas prend les abréviations de **ses** charsets, suivies de `_<numéro>`.
  Exemple : `Roboto-Regular_asc-lt1-pun_1`, `Roboto-Regular_grk-cyr_2`. Un seul atlas : pas de numéro.
- Nom libre (« Auto name » décoché) avec plusieurs atlas : `_<numéro>` ajouté avant l'extension.
- Le dossier de sortie reste choisi par l'utilisateur. Seul le nom de fichier est automatique.
- Le CSV et le JSON prennent le même nom de base que l'image, sauf si leur case « Auto name » est décochée.
- Le nom se met à jour en direct quand la font, les charsets, leur ordre ou leur répartition changent.
- Les noms de charsets inconnus d'un ancien `settings.json` sont ignorés au chargement.

## Ligne d'information (mise à jour en direct)
- Nombre de glyphes demandés (cf. « Comptage des glyphes »), nombre d'atlas, et pour chaque atlas
  `<glyphes> / <capacité>` (`n/a` sans cellules uniformes).
- Erreurs de répartition en rouge (cf. « Atlas multiples »).

## Comportement
- Aperçu de la commande complète, en lecture seule et copiable, mis à jour en direct.
  Plusieurs atlas : une commande par ligne.
- Bouton « Generate » : exécution dans un thread, avec stdout et stderr affichés dans une zone de log.
  L'interface ne doit pas se figer. Plusieurs atlas : commandes lancées l'une après l'autre,
  arrêt à la première en échec, chaque bloc de log précédé de `Atlas N/M`.
- Validation avant exécution : exe et font existants, valeurs numériques valides, au moins un charset,
  dossier de sortie existant, aucune erreur de répartition.

## Comportement de msdf-atlas-gen (vérifié dans main.cpp et GridAtlasPacker.cpp)
- Grille uniforme : les glyphes vides (espaces) n'occupent **pas** de cellule (`if (!glyph->isWhitespace())`).
- Grille qui ne tombe pas juste (`-dimensions` + `-uniformcell`) : arrondi à l'inférieur, passage à la ligne suivante.
- Atlas trop petit : `Error: Could not fit N out of M glyphs into the atlas.`, code de sortie 1, **aucun fichier écrit**.
  Un ancien atlas de même nom reste donc dans le dossier de sortie.
  N compte aussi les glyphes vides restants (`return end-glyph-1` dans GridAtlasPacker) : il peut dépasser
  de 1 ou 2 le nombre de glyphes calculé par l'outil, ce n'est pas une erreur de comptage.
- Glyphe vide (`isWhitespace`) = forme sans contour (`shape.contours.empty()`), quel que soit le codepoint.
- Cellule trop petite pour un glyphe : `Warning: Grid cell too constrained… some may be cut off!`, l'atlas est généré quand même.
- Toujours affiché : `Loaded geometry of X out of Y glyphs.`, puis la liste des codepoints manquants dans la font.
