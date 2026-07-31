"""
Moteur RAG v2 - Avec thésaurus, few-shot learning, assertions négatives et traçabilité
"""

import json
import asyncio
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
import streamlit as st
import fitz
import faiss
import tiktoken
import re

from sentence_transformers import SentenceTransformer
from openai import OpenAI
from pathlib import Path

from config import (
    get_thesaurus,
    get_jeu_reference,
    get_jeu_adverse,
    get_assertions_negatives,
    get_synonymes_dict,
    get_variables_determinantes,
    get_few_shot_examples,
    get_negative_examples,
    CORPUS_MAPPING,
    PIEGES,
    REFORMULATION_PROMPT_V2,
    ANSWER_PROMPT_V2,
    MODEL_SETTINGS,
    get_recodifications,
    OPENAI_API_KEY,
)


# =====================================================
# Types et énums
# =====================================================

class NiveauNormativite(str, Enum):
    REGLEMENTAIRE = "reglementaire"
    INTERPRETATIF = "interpretatif"
    NORMATIF = "normatif"
    CONTRACTUEL = "contractuel"
    DOCTRINAL = "doctrinal"
    USAGE_PROFESSIONNEL = "usage_professionnel"


class ComportementAttendu(str, Enum):
    REPONDRE = "repondre"
    DEMANDER_PRECISION = "demander_precision"
    ORIENTER_CORPUS = "orienter_corpus"
    ORIENTER_EXPERTISE = "orienter_expertise"
    SIGNALER_ABSENCE = "signaler_absence"
    SIGNALER_NON_REGLEMENTAIRE = "signaler_non_reglementaire"


@dataclass
class Citation:
    """Représente une citation d'article"""
    article: str
    titre: str
    texte: str
    niveau_normativite: NiveauNormativite
    corpus: str
    url: Optional[str] = None
    score_pertinence: float = 1.0
    
    def to_dict(self):
        return {
            "article": self.article,
            "titre": self.titre,
            "texte": self.texte[:200] + "..." if len(self.texte) > 200 else self.texte,
            "niveau": self.niveau_normativite.value,
            "corpus": self.corpus,
            "url": self.url,
            "score": self.score_pertinence
        }


@dataclass
class Document:
    """Représente un document trouvé"""
    page: int
    texte: str
    score: float
    sources: List[Citation]


@dataclass
class ReformulatioResult:
    """Résultat de reformulation"""
    reformulation: str
    termes_normatifs: List[str]
    variables_requises: Dict[str, Optional[str]]
    corpus_presume: List[str]
    confiance: float
    notes: str
    faux_amis_detectes: List[Dict]


@dataclass
class ReponseJustifiee:
    """Réponse structurée et justifiée"""
    reponse: str
    comportement: ComportementAttendu
    citations: List[Citation]
    documents_sources: List[Document]
    niveau_normativite: NiveauNormativite
    confiance: float
    variables_manquantes: List[str]
    justification: str
    pieges_evites: List[str]
    corpus_applique: str
    
    def to_dict(self):
        return {
            "reponse": self.reponse,
            "comportement": self.comportement.value,
            "citations": [c.to_dict() for c in self.citations],
            "n_sources": len(self.documents_sources),
            "niveau": self.niveau_normativite.value,
            "confiance": self.confiance,
            "variables_manquantes": self.variables_manquantes,
            "pieges_evites": self.pieges_evites,
            "corpus": self.corpus_applique
        }


# =====================================================
# Moteur RAG v2
# =====================================================

class RAGEnginev2:
    """Moteur RAG avancé avec thésaurus, few-shot et assertions négatives"""
    
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.embedding_model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.encoder = tiktoken.get_encoding("cl100k_base")
        self.vector_store = VectorStorev2()
        self.chunks = []
        
        # Données du thésaurus
        self.thesaurus = get_thesaurus()
        self.synonymes = get_synonymes_dict()
        self.assertions_negatives = get_assertions_negatives()
        self.variables_determinantes = get_variables_determinantes()
        self.recodifications = get_recodifications()
        
        print("✅ RAG Engine v2 initialisé")

    # =====================================================
    # 1 - Détection assertions négatives
    # =====================================================

    def detecter_assertion_negative(self, question: str) -> Optional[Dict]:
        """
        Vérifie si la question correspond à une assertion négative
        (= cette notion n'existe pas)
        """
        question_lower = question.lower()
        
        for assertion in self.assertions_negatives:
            keywords = assertion.get("keywords", [])
            if any(kw.lower() in question_lower for kw in keywords):
                return {
                    "type": assertion.get("type"),
                    "corpus": assertion.get("corpus"),
                    "assertion": assertion.get("assertion"),
                    "explication": assertion.get("explication")
                }
        
        return None

    # =====================================================
    # 2 - Détection des pièges
    # =====================================================

    def detecter_pieges(self, question: str, termes: List[str]) -> List[str]:
        """Détecte les pièges potentiels dans la question"""
        pieges_detectes = []
        
        question_lower = question.lower()
        
        # P2: Lexique obsolète
        for terme in termes:
            if terme in self.synonymes:
                synonymes = self.synonymes[terme]
                if any("obsolete" in s.lower() for s in synonymes):
                    pieges_detectes.append("P2_lexique_obsolete")
                    break
        
        # P3: Références recodifiées
        for recodif in self.recodifications:
            if recodif["ancien"].lower() in question_lower:
                pieges_detectes.append("P3_version_recodifiee")
                break
        
        # P7: Dégradé (sigles inconnus)
        sigles = re.findall(r'\b[A-Z]{2,}\b', question)
        sigles_connus = [s for s in sigles if s in self.synonymes]
        if len(sigles) > len(sigles_connus):
            pieges_detectes.append("P7_degraded")
        
        return list(set(pieges_detectes))

    # =====================================================
    # 3 - Reformulation améliorée
    # =====================================================

    def reformuler_question_v2(self, question: str) -> ReformulatioResult:
        """
        Reformule la question avec aide du thésaurus et few-shot
        """
        # Few-shot examples
        examples = get_few_shot_examples("repondre")
        few_shot_text = "\n".join([
            f"Q: {ex['question']}\nR: {ex['reformulation']}"
            for ex in examples[:3]
        ])
        
        # Snippet thésaurus
        notions_sample = self.thesaurus.get("notions", [])[:3]
        thesaurus_snippet = json.dumps(notions_sample, ensure_ascii=False, indent=2)
        
        # Variables déterminantes
        variables_snippet = json.dumps(
            list(self.variables_determinantes.values())[:3],
            ensure_ascii=False,
            indent=2
        )
        
        prompt = REFORMULATION_PROMPT_V2.format(
            thesaurus_snippet=thesaurus_snippet,
            variables_snippet=variables_snippet,
            question=question,
            few_shot_examples=few_shot_text
        )
        
        try:
            response = self.client.chat.completions.create(
                model=MODEL_SETTINGS["reformulation"]["model"],
                temperature=MODEL_SETTINGS["reformulation"]["temperature"],
                messages=[{"role": "user", "content": prompt}],
            )
            
            result_text = response.choices[0].message.content
            
            # Parser JSON
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result_json = json.loads(json_match.group())
            else:
                result_json = {"reformulation": result_text}
            
            return ReformulatioResult(
                reformulation=result_json.get("reformulation", question),
                termes_normatifs=result_json.get("termes_normatifs", []),
                variables_requises=result_json.get("variables_requises", {}),
                corpus_presume=result_json.get("corpus_presume", ["ERP"]),
                confiance=result_json.get("confiance", 0.7),
                notes=result_json.get("notes", ""),
                faux_amis_detectes=[]
            )
        
        except Exception as e:
            print(f"Erreur reformulation: {e}")
            return ReformulatioResult(
                reformulation=question,
                termes_normatifs=[],
                variables_requises={},
                corpus_presume=["ERP"],
                confiance=0.5,
                notes=f"Erreur: {e}",
                faux_amis_detectes=[]
            )

    # =====================================================
    # 4 - Recherche intelligente
    # =====================================================

    def rechercher_documents(
        self,
        question: str,
        corpus_filter: Optional[List[str]] = None,
        k: int = 8
    ) -> List[Document]:
        """Recherche vectorielle avec filtrage corpus"""
        
        results = self.vector_store.search(question, k)
        
        # Filtrer par corpus si spécifié
        if corpus_filter:
            results = [r for r in results if r.get("corpus") in corpus_filter]
        
        documents = []
        for result in results:
            documents.append(Document(
                page=result.get("page"),
                texte=result.get("text"),
                score=result.get("score", 1.0),
                sources=[]  # À remplir avec citations
            ))
        
        return documents

    # =====================================================
    # 5 - Génération réponse justifiée
    # =====================================================

    def generer_reponse_v2(
        self,
        question: str,
        reformulation: ReformulatioResult,
        documents: List[Document],
        corpus_applique: str
    ) -> ReponseJustifiee:
        """
        Génère une réponse avec justifications complètes
        """
        
        # Vérifier assertions négatives
        assertion = self.detecter_assertion_negative(question)
        if assertion:
            return ReponseJustifiee(
                reponse=f"❌ {assertion['assertion']}\n\n💡 {assertion['explication']}",
                comportement=ComportementAttendu.SIGNALER_ABSENCE,
                citations=[],
                documents_sources=[],
                niveau_normativite=NiveauNormativite.DOCTRINAL,
                confiance=1.0,
                variables_manquantes=[],
                justification="Assertion négative trouvée dans le thésaurus",
                pieges_evites=["P1_absence"],
                corpus_applique=corpus_applique
            )
        
        # Vérifier variables manquantes
        variables_manquantes = []
        # for var_name, var_value in reformulation.variables_requises.items():
        #     if var_value is None:
        #         variables_manquantes.append(var_name)
        
        if variables_manquantes:
            return ReponseJustifiee(
                reponse=f"⚠️ Pour vous répondre précisément, j'ai besoin de précisions:\n" + 
                       "\n".join([f"- {v}" for v in variables_manquantes]),
                comportement=ComportementAttendu.DEMANDER_PRECISION,
                citations=[],
                documents_sources=documents,
                niveau_normativite=NiveauNormativite.DOCTRINAL,
                confiance=0.5,
                variables_manquantes=variables_manquantes,
                justification="Variables déterminantes manquantes",
                pieges_evites=["P5_variable"],
                corpus_applique=corpus_applique
            )
        
        # Détecter pièges
        pieges_detectes = self.detecter_pieges(question, reformulation.termes_normatifs)
        
        # Few-shot examples
        examples = get_few_shot_examples("repondre")
        few_shot_text = "\n".join([
            f"Q: {ex['question']}\nRéf: {ex['articles']}"
            for ex in examples[:2]
        ])
        
        # Contexte
        context = "\n\n".join([
            f"Page {doc.page}:\n{doc.texte[:300]}..."
            for doc in documents[:5]
        ])
        
        # Prompt de génération
        prompt = ANSWER_PROMPT_V2.format(
            corpus=corpus_applique,
            notions=", ".join(reformulation.termes_normatifs),
            # variables=json.dumps(reformulation.variables_requises),
            few_shot_examples=few_shot_text,
            context=context,
            question=question
        )
        
        try:
            response = self.client.chat.completions.create(
                model=MODEL_SETTINGS["answer"]["model"],
                temperature=MODEL_SETTINGS["answer"]["temperature"],
                messages=[{"role": "user", "content": prompt}],
            )
            
            result_text = response.choices[0].message.content
            
            # Parser résultat
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result_json = json.loads(json_match.group())
            else:
                result_json = {"reponse": result_text}
            
            # Construire citations
            citations = []
            for citation_data in result_json.get("citations", []):
                citations.append(Citation(
                    article=citation_data.get("article", ""),
                    titre=citation_data.get("titre", ""),
                    texte=citation_data.get("texte", ""),
                    niveau_normativite=NiveauNormativite.REGLEMENTAIRE,
                    corpus=corpus_applique,
                    url=citation_data.get("url")
                ))
            
            return ReponseJustifiee(
                reponse=result_json.get("reponse", result_text),
                comportement=ComportementAttendu.REPONDRE,
                citations=citations,
                documents_sources=documents,
                niveau_normativite=NiveauNormativite(
                    result_json.get("niveau_normativite", "reglementaire")
                ),
                confiance=result_json.get("confiance", 0.7),
                variables_manquantes=[],
                justification=result_json.get("justification", ""),
                pieges_evites=pieges_detectes,
                corpus_applique=corpus_applique
            )
        
        except Exception as e:
            print(f"Erreur génération: {e}")
            return ReponseJustifiee(
                reponse=f"❌ Erreur génération: {e}",
                comportement=ComportementAttendu.ORIENTER_EXPERTISE,
                citations=[],
                documents_sources=documents,
                niveau_normativite=NiveauNormativite.DOCTRINAL,
                confiance=0.0,
                variables_manquantes=[],
                justification=f"Exception: {e}",
                pieges_evites=[],
                corpus_applique=corpus_applique
            )

    # =====================================================
    # 6 - Pipeline complet
    # =====================================================

    def traiter_question(
        self,
        question: str,
        corpus_filtre: Optional[List[str]] = None
    ) -> ReponseJustifiee:
        """
        Pipeline complet: assertion → reformulation → recherche → génération
        """
        
        # Assertion négative?
        assertion = self.detecter_assertion_negative(question)
        if assertion:
            return ReponseJustifiee(
                reponse=f"❌ {assertion['assertion']}",
                comportement=ComportementAttendu.SIGNALER_ABSENCE,
                citations=[],
                documents_sources=[],
                niveau_normativite=NiveauNormativite.DOCTRINAL,
                confiance=1.0,
                variables_manquantes=[],
                justification="Assertion négative du thésaurus",
                pieges_evites=["P1_absence"],
                corpus_applique="Multi"
            )
        
        # Reformuler
        reformulation = self.reformuler_question_v2(question)
        
        # Rechercher
        corpus_applique = corpus_filtre or reformulation.corpus_presume
        documents = self.rechercher_documents(question, corpus_applique, k=8)
        
        # Générer réponse
        reponse = self.generer_reponse_v2(
            question,
            reformulation,
            documents,
            corpus_applique[0] if corpus_applique else "ERP"
        )
        
        return reponse

    # =====================================================
    # 7 - Construction de l'index
    # =====================================================

    def extraire_pdf(self, path: str) -> List[Dict]:
        """Extrait PDF"""
        try:
            doc = fitz.open(path)
            pages = []
            for page_num, page in enumerate(doc):
                text = page.get_text("text")
                if text.strip():
                    pages.append({"page": page_num + 1, "text": text})
            doc.close()
            return pages
        except Exception as e:
            print(f"Erreur extraction PDF: {e}")
            return []

    def chunker_semantique(self, pages: List[Dict], max_tokens: int = 500) -> List[Dict]:
        """Chunking sémantique"""
        chunks = []
        for page in pages:
            paragraphs = [p.strip() for p in page["text"].split("\n\n") if p.strip()]
            current = []
            current_tokens = 0
            
            for paragraph in paragraphs:
                size = len(self.encoder.encode(paragraph))
                if current_tokens + size > max_tokens and current:
                    chunks.append({"text": "\n\n".join(current), "page": page["page"]})
                    current = current[-1:] if current else []
                    current_tokens = sum(len(self.encoder.encode(x)) for x in current)
                
                current.append(paragraph)
                current_tokens += size
            
            if current:
                chunks.append({"text": "\n\n".join(current), "page": page["page"]})
        
        return chunks

    def construire_index(self, pdf_path: str):
        """Construit l'index complet"""
        st.info("📖 Extraction du PDF...")
        pages = self.extraire_pdf(pdf_path)
        st.success(f"✅ {len(pages)} pages")
        
        st.info("✂️ Chunking sémantique...")
        self.chunks = self.chunker_semantique(pages)
        st.success(f"✅ {len(self.chunks)} chunks")
        
        st.info("🔍 Création embeddings...")
        self.vector_store.construire(self.chunks, self.embedding_model)
        st.success("✅ Index créé")


# =====================================================
# Vector Store v2
# =====================================================

class VectorStorev2:
    """Gère l'index FAISS v2"""
    
    def __init__(self):
        self.index = None
        self.chunks = []
        
    
    def construire(self, chunks: List[Dict], embedding_model):
        """Construit l'index"""
        texts = [c["text"] for c in chunks]
        vectors = embedding_model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True
        )
        vectors = np.asarray(vectors, dtype="float32")
        
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)
        self.chunks = chunks
        
        faiss.write_index(self.index, "faiss_index_v2.bin")
    
    def search(self, question: str,embedding_model, k: int = 8) -> List[Dict]:
        """Recherche les chunks similaires"""
        if self.index is None:
            return []
        
        query_vector = embedding_model.encode([question], normalize_embeddings=True)
        query_vector = np.asarray(query_vector, dtype="float32")
        
        scores, indexes = self.index.search(query_vector, k)
        
        results = []
        for score, idx in zip(scores[0], indexes[0]):
            if idx >= 0:
                results.append({
                    **self.chunks[idx],
                    "score": float(score)
                })
        
        return results


@st.cache_resource
def get_rag_engine_v2():
    """Initialise le moteur RAG v2 avec cache"""
    return RAGEnginev2()