# Notice technique — livrables des étapes 1 et 2

**Version 1.0.0 — 30 juillet 2026**
Périmètre : ERP (arrêté du 25 juin 1980) · code du travail, quatrième partie · habitation (CCH + arrêté du 31 janvier 1986).

---

## Avertissement

Les références d'articles portées dans ces fichiers sont des **points d'entrée** dans le corpus, destinés à amorcer la recherche et à servir de vérité-terrain provisoire. Chaque notion porte un champ `confiance_reference` valant `haute` ou `a_verifier`. **Aucune référence de ces fichiers ne doit être restituée à un utilisateur final avant validation experte**, et la validation elle-même doit être faite sur le texte consolidé en vigueur, pas sur ces fichiers.

Deux recodifications doivent être traitées comme des règles de conversion et non comme des variantes de rédaction :

| Corpus | Ancien | Nouveau | Depuis |
|---|---|---|---|
| CCH | R. 111-13 et s. | R. 142-1 et s. | 01/07/2021 |
| CCH | R. 123-x | R. 143-x | 01/07/2021 |
| CCH | L. 129-8 (détecteurs de fumée) | L. 142-2 et s. | 01/07/2021 |
| Code du travail | R. 232-12 et s. | R. 4227-1 et s. | 01/05/2008 |

---

## Étape 1 — Thésaurus contrôlé

**Fichiers** : `thesaurus_incendie_v1.json` (référence machine) · `thesaurus_incendie_v1.csv` (vue de curation).

**Contenu** : 96 notions réparties en 9 thèmes, 20 assertions négatives, 17 variables déterminantes, 6 niveaux de normativité.

### Schéma d'une notion

| Champ | Rôle dans le système |
|---|---|
| `id`, `theme` | Identifiant stable et regroupement |
| `terme_prefere` | Forme normative retenue pour la réécriture de requête |
| `definition` | Contexte injecté dans le prompt de reformulation |
| `synonymes_usage` | **Pont lexical principal** : expansion déterministe de la requête utilisateur |
| `termes_obsoletes` | Conversion CF → EI, M1 → euroclasse, SF → R, CHSCT → CSE |
| `faux_amis` | Empêche le transfert d'une notion d'un corpus à l'autre |
| `corpus.ERP / CT / HAB` | **Pré-filtrage par métadonnées avant la recherche sémantique** |
| `autres_sources` | Textes hors corpus principaux (CGCT, RSD, loi de 1989, ICPE, IT, normes) |
| `variables_determinantes` | Déclenche le refus de répondre tant qu'elles ne sont pas résolues |
| `niveau_normativite` | Qualifie l'opposabilité dans la réponse rendue |
| `stade`, `profils` | Aide à la détection de profil et au choix du registre |
| `note_preventionniste` | Consigne métier injectée dans la réponse quand la notion est piégeuse |
| `confiance_reference` | Priorise la file de validation experte |

### Les quatre pièges instrumentés

Ils sont portés à la fois par `termes_obsoletes`, `faux_amis` et `note_preventionniste`, et testés dans le jeu adverse (familles P2 et P1).

1. **catégorie** — ERP, ICPE ou famille selon l'interlocuteur.
2. **coupe-feu** — absent des textes postérieurs à 2004, omniprésent dans le langage.
3. **issue de secours** — terme de chantier ; le texte raisonne en dégagements.
4. **alarme / alerte** — occupants contre secours.

### Assertions négatives

Vingt énoncés du type « cette notion n'existe pas dans ce corpus », avec l'orientation correspondante. **Ils doivent être indexés comme des documents à part entière**, faute de quoi le système ne peut structurellement pas répondre « ce n'est pas là » : un moteur de similarité trouve toujours quelque chose.

Répartition : 8 sur l'habitation (commission de sécurité, registre, EAS, extincteurs, alarme, exercices, unités de passage, sprinkleur), 5 sur le code du travail, 3 sur l'ERP, 4 transverses (CF, point de rassemblement, EPI, RVRAT, APSAD).

---

## Étape 2 — Jeux d'évaluation

**Fichiers** : `jeu_reference_v1.csv` (150 items) · `jeu_adverse_v1.csv` (60 items).

### Jeu de référence

Cinquante items par profil, tracés sur les trois séries de questions et leurs transpositions normatives : `REF-A-xx` architecte, `REF-E-xx` dirigeant, `REF-G-xx` gestionnaire.

Colonnes : question en langage courant · reformulation normative · corpus attendu · articles attendus · notions attendues (libellés et identifiants) · variables requises · comportement attendu · difficulté · commentaire · deux colonnes de saisie experte.

Distribution des comportements attendus :

| Comportement | Items | Ce qu'il mesure |
|---|---|---|
| `repondre` | 93 | Rappel et exactitude |
| `demander_precision` | 22 | Refus de répondre sans variable déterminante |
| `orienter_corpus` | 19 | Détection de la superposition des corpus |
| `orienter_expertise` | 8 | Renvoi au décisionnel (commission, expertise, visite) |
| `signaler_absence` | 4 | Connaissance négative |
| `signaler_non_reglementaire` | 4 | Qualification du niveau de normativité |

Qu'un tiers des items attende autre chose qu'une réponse directe n'est pas un artefact : c'est la structure réelle du domaine.

### Jeu adverse

Soixante items construits pour faire échouer le système, répartis en sept familles :

| Famille | Items | Objet |
|---|---|---|
| P1 — absence | 12 | La bonne réponse est « cette notion n'existe pas ici » |
| P2 — lexique | 10 | Termes obsolètes, faux amis, sigles de métier |
| P3 — version | 8 | Références abrogées, recodifiées, textes datés |
| P4 — normativité | 8 | Exigence contractuelle ou normative présentée comme réglementaire |
| P5 — variable | 10 | Variable déterminante absente : le système doit demander |
| P6 — croisement | 7 | Deux corpus concurrents, résolution par le plus contraignant |
| P7 — dégradé | 5 | Formulation orale, télégraphique, fautive |

Un système obtenant d'excellents scores sur le jeu de référence et s'effondrant sur le jeu adverse est plus dangereux qu'un système médiocre, parce qu'il inspire confiance.

---

## Protocole de validation experte

1. **Thésaurus d'abord.** Valider terme par terme dans l'onglet `Thésaurus` du classeur, en commençant par les notions `confiance_reference = a_verifier`. Corriger les références sur texte consolidé, pas sur le fichier.
2. **Assertions négatives ensuite.** Ce sont elles qui produiront les réponses les plus contre-intuitives : leur formulation doit être irréprochable.
3. **Jeux d'évaluation en dernier.** Valider les articles attendus et, surtout, contester les comportements attendus : un désaccord d'expert sur un `demander_precision` révèle un choix produit, pas une erreur de saisie.
4. **Gel.** Une fois validés, les deux jeux sont figés et versionnés. Toute question ajoutée après le gel va dans un jeu v2, jamais dans le jeu de référence courant.

**Règle absolue** : ces 210 items servent à **mesurer**, jamais à entraîner. Les paires d'entraînement pour l'ajustement d'embeddings doivent être générées séparément — et une paire d'entraînement ne doit jamais reprendre une question d'évaluation, sous peine de rendre les métriques inopérantes.

---

## Métriques et seuils proposés

| Métrique | Jeu | Calcul | Seuil de mise en production |
|---|---|---|---|
| Rappel@10 des articles attendus | Référence | articles trouvés / articles attendus | ≥ 0,90 |
| Précision des citations | Les deux | références citées existantes et en vigueur / références citées | 1,00 — tolérance zéro |
| Exactitude de la réponse | Référence (échantillon expert) | jugement binaire | ≥ 0,85 |
| Conformité du comportement | Les deux | comportement observé = comportement attendu | ≥ 0,95 |
| Résistance aux pièges | Adverse | items traités correctement | ≥ 0,95, dont **1,00 sur P1 et P4** |
| Taux d'abstention | Les deux | items sans réponse produite | strictement > 0 ; un taux nul est un signal d'alarme |

Les métriques de recherche (rappel) se mesurent **avant** toute génération : c'est le seul moyen de savoir si un échec vient du moteur ou de la rédaction.

Non-régression : les deux jeux sont rejoués intégralement à chaque modification du corpus, du thésaurus, des filtres ou du modèle. Les écarts s'examinent item par item.

---

## Limites connues de la version 1

- **Couverture** : 96 notions couvrent le tronc commun des trois corpus. Atteindre les 300 notions cibles suppose d'ajouter les dispositions particulières par type ERP (J, L, M, N, O, P, R, S, T, U, V, W, X, Y, PA, CTS, PS, GA, REF), le régime IGH et les rubriques ICPE les plus fréquentes.
- **Références** : établies à titre d'amorce, non vérifiées article par article sur texte consolidé.
- **Corpus absents** : DECI départementale (variable d'un département à l'autre), doctrines et notes de service départementales, jurisprudence.
- **Jeu adverse** : ne couvre pas encore les questions à prémisse fausse construite (« l'article CO 62 impose… », alors que l'article n'existe pas), qui constituent une famille P8 à ajouter en v2.
- **Rien n'est mesuré** tant que le protocole de validation n'a pas été exécuté : en l'état, ces fichiers sont une hypothèse de travail structurée, pas une vérité-terrain.
