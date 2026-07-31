"""
Configuration v2 - RAG avec thésaurus, jeux d'évaluation et Legifrance
"""


import json
import pandas as pd
from pathlib import Path
from typing import Dict, List
import os
from dotenv import load_dotenv

load_dotenv()

# =====================================================
# Configuration API
# =====================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# =====================================================
# Chemins des données
# =====================================================

DATA_DIR = Path("reapiatossa")

THESAURUS_JSON = DATA_DIR / "thesaurus_incendie_v1.json"
THESAURUS_CSV = DATA_DIR / "thesaurus_incendie_v1.csv"
JEU_REFERENCE = DATA_DIR / "jeu_reference_v1.csv"
JEU_ADVERSE = DATA_DIR / "jeu_adverse_v1.csv"
OUTILLAGE_IA = DATA_DIR / "outillage_ia_incendie_v1.xlsx"
NOTICE = DATA_DIR / "NOTICE_livrables_v1.md"

# =====================================================
# Thésaurus et données
# =====================================================

def load_thesaurus() -> Dict:
    """Charge le thésaurus JSON"""
    with open(THESAURUS_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_jeu_reference() -> pd.DataFrame:
    """Charge le jeu de référence (150 items positifs)"""
    return pd.read_csv(JEU_REFERENCE, sep=';', encoding='utf-8')

def load_jeu_adverse() -> pd.DataFrame:
    """Charge le jeu adverse (60 items négatifs/pièges)"""
    return pd.read_csv(JEU_ADVERSE, sep=';', encoding='utf-8')

def load_outillage_ia() -> Dict:
    """Charge la configuration IA"""
    return pd.read_excel(OUTILLAGE_IA, sheet_name=None)

# Cache global
_THESAURUS_CACHE = None
_JEU_REF_CACHE = None
_JEU_ADV_CACHE = None

def get_thesaurus() -> Dict:
    global _THESAURUS_CACHE
    if _THESAURUS_CACHE is None:
        _THESAURUS_CACHE = load_thesaurus()
    return _THESAURUS_CACHE

def get_jeu_reference() -> pd.DataFrame:
    global _JEU_REF_CACHE
    if _JEU_REF_CACHE is None:
        _JEU_REF_CACHE = load_jeu_reference()
    return _JEU_REF_CACHE

def get_jeu_adverse() -> pd.DataFrame:
    global _JEU_ADV_CACHE
    if _JEU_ADV_CACHE is None:
        _JEU_ADV_CACHE = load_jeu_adverse()
    return _JEU_ADV_CACHE

# =====================================================
# Extraction du thésaurus
# =====================================================

def get_assertions_negatives() -> List[Dict]:
    """Récupère les 20 assertions négatives du thésaurus"""
    thesaurus = get_thesaurus()
    return thesaurus.get("assertions_negatives", [])

def get_vocabulaire_erp() -> Dict[str, str]:
    """Construit un dictionnaire terme → définition ERP"""
    thesaurus = get_thesaurus()
    vocab = {}
    
    for notion in thesaurus.get("notions", []):
        if notion.get("corpus", {}).get("ERP"):
            vocab[notion["terme_prefere"]] = notion["definition"]
            for syno in notion.get("synonymes_usage", []):
                vocab[syno] = notion["definition"]
    
    return vocab

def get_synonymes_dict() -> Dict[str, List[str]]:
    """Construit un dictionnaire terme → synonymes pour expansion requête"""
    thesaurus = get_thesaurus()
    synonymes = {}
    
    for notion in thesaurus.get("notions", []):
        prefere = notion["terme_prefere"]
        synonymes[prefere] = [
            prefere,
            *notion.get("synonymes_usage", []),
            *notion.get("termes_obsoletes", [])
        ]
    
    return synonymes

def get_variables_determinantes() -> Dict[str, Dict]:
    """Récupère les 17 variables déterminantes"""
    thesaurus = get_thesaurus()
    variables = {}
    
    for var in thesaurus.get("variables_determinantes", []):
        variables[var["nom"]] = var
    
    return variables

def get_recodifications() -> List[Dict]:
    """Récupère les règles de recodification (anciennes → nouvelles références)"""
    thesaurus = get_thesaurus()
    return thesaurus.get("meta", {}).get("recodifications_a_traiter", [])

# =====================================================
# Few-shot examples pour prompts
# =====================================================

def get_few_shot_examples(behavior: str = "repondre") -> List[Dict]:
    """
    Récupère des exemples few-shot filtrés par comportement attendu
    
    Comportements:
    - repondre: Réponse directe
    - demander_precision: Demander une variable
    - orienter_corpus: Rediriger vers bon corpus
    - signaler_absence: Absence de notion
    """
    jeu_ref = get_jeu_reference()
    
    # Filtrer par comportement attendu
    filtered = jeu_ref[
        jeu_ref['comportement_attendu'].str.lower() == behavior.lower()
    ].head(5)  # Top 5 exemples
    
    examples = []
    for _, row in filtered.iterrows():
        examples.append({
            "question": row['question_utilisateur'],
            "reformulation": row['reformulation_normative'],
            "corpus": row['corpus_attendu'],
            "articles": row['articles_attendus'],
            "comportement": row['comportement_attendu'],
            "difficulte": row['difficulte']
        })
    
    return examples

def get_negative_examples() -> List[Dict]:
    """Récupère les exemples adverses (pièges à éviter)"""
    jeu_adv = get_jeu_adverse()
    
    examples = []
    for _, row in jeu_adv.iterrows():
        examples.append({
            "question": row.get('question_utilisateur'),
            "famille_piege": row.get('famille_piege'),
            "trappe": row.get('trappe_attendue'),
            "comportement_correct": row.get('comportement_attendu'),
            "corpus": row.get('corpus_attendu')
        })
    
    return examples

# =====================================================
# Corpus multiples
# =====================================================

CORPUS_MAPPING = {
    "ERP": {
        "label": "Établissements Recevant du Public",
        "texte": "arrêté du 25 juin 1980",
        "url_base": "https://www.legifrance.gouv.fr",
        "prefixes": ["GN", "DF", "EM", "EL", "CH", "CO", "GA", "U"]
    },
    "CT": {
        "label": "Code du Travail (4e partie)",
        "texte": "Code du travail - Santé et sécurité",
        "url_base": "https://www.legifrance.gouv.fr",
        "prefixes": ["R. 4", "L. 4"]
    },
    "HAB": {
        "label": "Habitation",
        "texte": "CCH + arrêté du 31 janvier 1986",
        "url_base": "https://www.legifrance.gouv.fr",
        "prefixes": ["R. 14", "L. 14", "R. 12"]
    },
    "IGH": {
        "label": "Immeubles de Grande Hauteur",
        "texte": "RIGHnr arrêté du 30 décembre 2011",
        "url_base": "https://www.legifrance.gouv.fr",
        "prefixes": ["IGH"]
    }
}

# =====================================================
# Pièges instrumentés
# =====================================================

PIEGES = {
    "P1_absence": {
        "nom": "Absence de notion",
        "description": "La bonne réponse est 'cette notion n'existe pas ici'",
        "strategie": "Consulter assertions_negatives avant toute recherche"
    },
    "P2_lexique": {
        "nom": "Termes obsolètes / faux amis",
        "description": "Terme de métier ou abrogé que le système doit reconnaître",
        "strategie": "Mapper via termes_obsoletes et synonymes"
    },
    "P3_version": {
        "nom": "Références abrogées/recodifiées",
        "description": "Article ancien ou nouveau - appliquer recodification",
        "strategie": "Consulter recodifications_a_traiter"
    },
    "P4_normativite": {
        "nom": "Niveau de normativité",
        "description": "Contractuel/normatif présenté comme réglementaire",
        "strategie": "Qualifier avec niveau_normativite"
    },
    "P5_variable": {
        "nom": "Variable déterminante manquante",
        "description": "Demander corpus/type/catégorie plutôt que d'halluciner",
        "strategie": "Vérifier variables_determinantes, demander avant de chercher"
    },
    "P6_croisement": {
        "nom": "Croisement corpus",
        "description": "Deux corpus concurrents → appliquer le plus contraignant",
        "strategie": "Détecter multi-corpus, justifier le choix"
    },
    "P7_dégradé": {
        "nom": "Formulation orale/télégraphique",
        "description": "Question malformée, sigle inconnu",
        "strategie": "Reformuler avant recherche"
    }
}

# =====================================================
# Prompts améliorés
# =====================================================

REFORMULATION_PROMPT_V2 = """Tu es un expert sécurité incendie réglementaire (ERP, habitation, code du travail).

**Contexte**
Tu disposes d'un thésaurus contrôlé de 96 notions et 17 variables déterminantes.
Ton rôle est de transformer la question utilisateur en requête normative exploitable.

**Thésaurus fourni**
{thesaurus_snippet}

**Variables déterminantes requises**
{variables_snippet}

**Tâche**
1. Identifier les termes métier obsolètes ou polysémiques
2. Mapper vers le vocabulaire normative
3. Détecter les variables manquantes qui bloqueront la réponse
4. Produire une reformulation en langage réglementaire

**Format de réponse**
```json
{{
    "reformulation": "...",
    "termes_normatifs": ["...", "..."],
    "variables_requises": {{"corpus": null, "type_erp": null, ...}},
    "corpus_presume": ["ERP", "CT"],
    "confiance": 0.8,
    "notes": "..."
}}
```

**Question utilisateur**
{question}
"""

ANSWER_PROMPT_V2 = """Tu es un assistant expert sécurité incendie réglementaire.

**Corpus applicable**: {corpus}
**Notions clés**: {notions}


**Pièges connus à éviter**
- P1: Ne pas confondre avec absences de notion
- P2: Mapper termes obsolètes (coupe-feu, issue de secours, etc.)
- P4: Qualifier la normativité (réglementaire vs contractuel)

**Exemples de bon comportement**
{few_shot_examples}

**Documents trouvés**
{context}

**Tâche**
1. Répondre avec les informations du corpus fourni UNIQUEMENT
2. Citer les articles/références trouvés (pas d'hallucination)
3. Qualifier le niveau de normativité
4. Si données insuffisantes → demander variable déterminante
5. Si notion absente → utiliser assertion négative
6. TOUJOURS justifier par les textes

**Format de réponse**
```json
{{
    "reponse": "...",
    "citations": [{{"article": "...", "texte": "...", "url": "..."}}],
    "niveau_normativite": "reglementaire|interpretatif|contractuel",
    "confiance": 0.85,
    "variables_manquantes": [],
    "justification": "..."
}}
```

**Question de l'utilisateur**
{question}
"""

# =====================================================
# Métriques d'évaluation
# =====================================================

METRIQUES_SEUILS = {
    "rappel_articles": 0.90,
    "precision_citations": 1.00,
    "exactitude_reponse": 0.85,
    "conformite_comportement": 0.95,
    "resistance_pieges": 0.95,
    "taux_abstention_min": 0.01,  # > 0%
}

# =====================================================
# Legifrance API
# =====================================================

LEGIFRANCE_API = {
    "base_url": "https://www.legifrance.gouv.fr/api",
    "endpoints": {
        "search": "/documents",
        "article": "/articles/{id}",
        "consolidated": "/consolidated"
    },
    "timeout": 5
}

# =====================================================
# Configuration OpenAI v2
# =====================================================

MODEL_SETTINGS = {
    "reformulation": {
        "model": "gpt-4-turbo",
        "temperature": 0,
        "top_p": 0.9,
        "presence_penalty": 0.5,
    },
    "answer": {
        "model": "gpt-4-turbo",
        "temperature": 0.1,
        "top_p": 0.9,
        "presence_penalty": 1.0,  # Éviter hallucinations
    },
    "fact_check": {
        "model": "gpt-4-turbo",
        "temperature": 0,
    }
}

print("✅ Config v2 chargée avec succès")