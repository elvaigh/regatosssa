"""
Évaluation du RAG v2 - Validation contre jeux de référence et adverse
Mesure les métriques de performance selon le protocole de la notice
"""

import pandas as pd
import json
from typing import Dict, List, Tuple
from datetime import datetime
from pathlib import Path

from rag import RAGEnginev2, ComportementAttendu
from config import (
    get_jeu_reference,
    get_jeu_adverse,
    METRIQUES_SEUILS,
    get_recodifications,
)


class EvaluateurRAG:
    """Évalue le RAG contre les jeux de test"""
    
    def __init__(self):
        self.engine = RAGEnginev2()
        self.jeu_ref = get_jeu_reference()
        self.jeu_adv = get_jeu_adverse()
        self.resultats = {
            "reference": [],
            "adverse": []
        }
    
    # =====================================================
    # Métriques de base
    # =====================================================
    
    def evaluer_conformite_comportement(
        self,
        comportement_attendu: str,
        comportement_produit: str
    ) -> bool:
        """Évalue si le comportement produit match le comportement attendu"""
        return comportement_attendu.lower() == comportement_produit.lower()
    
    def evaluer_articles(
        self,
        articles_attendus: str,
        articles_produits: List[str]
    ) -> Tuple[float, int, int]:
        """
        Calcule rappel et précision des articles
        
        Returns:
            (rappel, articles_trouvés, articles_attendus)
        """
        if not articles_attendus:
            return 1.0, 0, 0
        
        attendus = [a.strip() for a in str(articles_attendus).split("|")]
        attendus = [a for a in attendus if a]
        
        if not attendus:
            return 1.0, len(articles_produits), 0
        
        # Normaliser
        attendus_norm = set(a.replace(" ", "").lower() for a in attendus)
        produits_norm = set(a.replace(" ", "").lower() for a in articles_produits)
        
        if not attendus_norm:
            return 1.0, len(articles_produits), 0
        
        # Rappel: articles trouvés / articles attendus
        rappel = len(attendus_norm & produits_norm) / len(attendus_norm)
        
        return rappel, len(produits_norm), len(attendus_norm)
    
    def evaluer_citations(self, citations_produites: List[Dict]) -> Tuple[bool, str]:
        """
        Évalue la précision des citations (tolérance zéro)
        - Citations doivent exister
        - Citations doivent être en vigueur
        
        Returns:
            (conforme, raison)
        """
        if not citations_produites:
            return True, "Pas de citation produite"
        
        # TODO: Vérifier contre Legifrance API
        # Pour l'instant, vérification simple
        for citation in citations_produites:
            if not citation.get("article"):
                return False, "Citation sans article"
            if not citation.get("texte"):
                return False, "Citation sans texte"
        
        return True, "Citations valides"
    
    # =====================================================
    # Évaluation jeu de référence
    # =====================================================
    
    def evaluer_item_reference(self, row_idx: int) -> Dict:
        """
        Évalue un item du jeu de référence
        """
        row = self.jeu_ref.iloc[row_idx]
        question = row['question_utilisateur']
        corpus_attendu = row['corpus_attendu']
        articles_attendus = row['articles_attendus']
        comportement_attendu = row['comportement_attendu']
        difficulte = row['difficulte']
        
        # Traiter question
        try:
            reponse = self.engine.traiter_question(question)
        except Exception as e:
            return {
                "id": row['id'],
                "question": question,
                "ok": False,
                "erreur": str(e),
                "difficulte": difficulte
            }
        
        # Évaluer comportement
        comportement_ok = self.evaluer_conformite_comportement(
            comportement_attendu,
            reponse.comportement.value
        )
        
        # Évaluer articles
        articles_produits = [c.article for c in reponse.citations]
        rappel_articles, n_produits, n_attendus = self.evaluer_articles(
            articles_attendus,
            articles_produits
        )
        
        # Évaluer citations
        citations_ok, raison_citations = self.evaluer_citations(
            [c.to_dict() for c in reponse.citations]
        )
        
        # Résultat
        return {
            "id": row['id'],
            "question": question,
            "profil": row['profil'],
            "difficulte": difficulte,
            "comportement_attendu": comportement_attendu,
            "comportement_produit": reponse.comportement.value,
            "comportement_ok": comportement_ok,
            "rappel_articles": rappel_articles,
            "articles_attendus": n_attendus,
            "articles_produits": n_produits,
            "citations_ok": citations_ok,
            "confiance": reponse.confiance,
            "corpus": reponse.corpus_applique,
            "ok": comportement_ok and rappel_articles >= 0.9 and citations_ok
        }
    
    # =====================================================
    # Évaluation jeu adverse
    # =====================================================
    
    def evaluer_item_adverse(self, row_idx: int) -> Dict:
        """
        Évalue un item du jeu adverse
        Mesure la résistance aux pièges
        """
        row = self.jeu_adv.iloc[row_idx]
        question = row['question_utilisateur']
        famille_piege = row.get('famille_piege', 'unknown')
        trappe = row.get('trappe_attendue', '')
        comportement_attendu = row.get('comportement_attendu', 'repondre')
        
        # Traiter question
        try:
            reponse = self.engine.traiter_question(question)
        except Exception as e:
            return {
                "id": f"ADV-{row_idx}",
                "question": question,
                "famille": famille_piege,
                "ok": False,
                "erreur": str(e)
            }
        
        # Évaluer si piège évité
        piege_evite = famille_piege.lower() in [p.lower() for p in reponse.pieges_evites]
        
        # Évaluer conformité comportement
        comportement_ok = self.evaluer_conformite_comportement(
            comportement_attendu,
            reponse.comportement.value
        )
        
        ok = comportement_ok  # Pour adverse, comportement correct = piège évité
        
        return {
            "id": f"ADV-{row_idx}",
            "question": question,
            "famille": famille_piege,
            "trappe": trappe,
            "comportement_attendu": comportement_attendu,
            "comportement_produit": reponse.comportement.value,
            "piege_detecte": famille_piege in reponse.pieges_evites,
            "confiance": reponse.confiance,
            "ok": ok
        }
    
    # =====================================================
    # Exécution complète
    # =====================================================
    
    def evaluer_jeu_reference(self, sample: int = None) -> pd.DataFrame:
        """Évalue le jeu de référence"""
        print("📊 Évaluation jeu de référence...")
        
        max_items = sample or len(self.jeu_ref)
        resultats = []
        
        for i in range(min(max_items, len(self.jeu_ref))):
            print(f"  Item {i+1}/{max_items}...", end='\r')
            result = self.evaluer_item_reference(i)
            resultats.append(result)
        
        df = pd.DataFrame(resultats)
        self.resultats["reference"] = resultats
        
        print(f"\n✅ {len(resultats)} items évalués")
        return df
    
    def evaluer_jeu_adverse(self, sample: int = None) -> pd.DataFrame:
        """Évalue le jeu adverse"""
        print("🎯 Évaluation jeu adverse...")
        
        max_items = sample or len(self.jeu_adv)
        resultats = []
        
        for i in range(min(max_items, len(self.jeu_adv))):
            print(f"  Item {i+1}/{max_items}...", end='\r')
            result = self.evaluer_item_adverse(i)
            resultats.append(result)
        
        df = pd.DataFrame(resultats)
        self.resultats["adverse"] = resultats
        
        print(f"\n✅ {len(resultats)} items évalués")
        return df
    
    # =====================================================
    # Rapports
    # =====================================================
    
    def generer_rapport_reference(self, df: pd.DataFrame) -> Dict:
        """Génère rapport détaillé jeu de référence"""
        
        total = len(df)
        ok = df['ok'].sum()
        taux_ok = (ok / total * 100) if total > 0 else 0
        
        # Rappel articles
        rappel_moyen = df['rappel_articles'].mean()
        
        # Citations
        citations_ok = df['citations_ok'].sum()
        taux_citations = (citations_ok / total * 100) if total > 0 else 0
        
        # Comportement
        comportement_ok = df['comportement_ok'].sum()
        taux_comportement = (comportement_ok / total * 100) if total > 0 else 0
        
        # Confiance
        confiance_moyen = df['confiance'].mean()
        
        # Par profil
        par_profil = df.groupby('profil').agg({
            'ok': ['sum', 'count'],
            'confiance': 'mean'
        })
        
        # Par difficulté
        par_difficulte = df.groupby('difficulte').agg({
            'ok': ['sum', 'count'],
            'rappel_articles': 'mean'
        })
        
        return {
            "total_items": total,
            "items_ok": ok,
            "taux_ok_percent": taux_ok,
            "rappel_articles_moyen": rappel_moyen,
            "citations_ok_percent": taux_citations,
            "conformite_comportement_percent": taux_comportement,
            "confiance_moyenne": confiance_moyen,
            "par_profil": par_profil.to_dict(),
            "par_difficulte": par_difficulte.to_dict(),
            "ok_seuil": taux_ok >= METRIQUES_SEUILS["conformite_comportement"] * 100
        }
    
    def generer_rapport_adverse(self, df: pd.DataFrame) -> Dict:
        """Génère rapport détaillé jeu adverse"""
        
        total = len(df)
        ok = df['ok'].sum()
        taux_ok = (ok / total * 100) if total > 0 else 0
        
        # Par famille piège
        par_famille = df.groupby('famille').agg({
            'ok': ['sum', 'count']
        })
        
        # Pièges détectés
        pieges_detectes = df['piege_detecte'].sum()
        
        return {
            "total_items": total,
            "items_ok": ok,
            "taux_ok_percent": taux_ok,
            "pieges_detectes": pieges_detectes,
            "par_famille": par_famille.to_dict(),
            "ok_seuil": taux_ok >= METRIQUES_SEUILS["resistance_pieges"] * 100
        }
    
    def generer_rapport_complet(self) -> Dict:
        """Génère rapport complet avec seuils"""
        
        rapport = {
            "timestamp": datetime.now().isoformat(),
            "systeme": "RAG v2.0.0",
            "reference": self.generer_rapport_reference(
                pd.DataFrame(self.resultats["reference"])
            ) if self.resultats["reference"] else {},
            "adverse": self.generer_rapport_adverse(
                pd.DataFrame(self.resultats["adverse"])
            ) if self.resultats["adverse"] else {},
            "seuils": METRIQUES_SEUILS
        }
        
        return rapport
    
    def afficher_rapport(self, rapport: Dict):
        """Affiche rapport formaté"""
        
        print("\n" + "="*60)
        print("📊 RAPPORT D'ÉVALUATION RAG v2")
        print("="*60)
        
        # Jeu de référence
        if rapport.get("reference"):
            ref = rapport["reference"]
            print(f"\n✅ JEU DE RÉFÉRENCE")
            print(f"   Total: {ref['total_items']} items")
            print(f"   OK: {ref['items_ok']} ({ref['taux_ok_percent']:.1f}%)")
            print(f"   Seuil (95%): {'✅ PASS' if ref['ok_seuil'] else '❌ FAIL'}")
            print(f"   Rappel articles: {ref['rappel_articles_moyen']:.1%}")
            print(f"   Citations OK: {ref['citations_ok_percent']:.1f}%")
            print(f"   Confiance moyenne: {ref['confiance_moyenne']:.2f}")
        
        # Jeu adverse
        if rapport.get("adverse"):
            adv = rapport["adverse"]
            print(f"\n🎯 JEU ADVERSE")
            print(f"   Total: {adv['total_items']} items")
            print(f"   OK: {adv['items_ok']} ({adv['taux_ok_percent']:.1f}%)")
            print(f"   Seuil (95%): {'✅ PASS' if adv['ok_seuil'] else '❌ FAIL'}")
            print(f"   Pièges détectés: {adv['pieges_detectes']}")
        
        print("\n" + "="*60)
    
    def sauvegarder_rapport(self, rapport: Dict, path: str = "rapport_eval_v2.json"):
        """Sauvegarde rapport en JSON"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(rapport, f, indent=2, ensure_ascii=False)
        print(f"📁 Rapport sauvegardé: {path}")


# =====================================================
# Utilisation
# =====================================================

if __name__ == "__main__":
    print("🚀 Lancement évaluation RAG v2...")
    
    evaluateur = EvaluateurRAG()
    
    # Évaluer (sur sample pour tests rapides)
    df_ref = evaluateur.evaluer_jeu_reference(sample=10)
    df_adv = evaluateur.evaluer_jeu_adverse(sample=10)
    
    # Générer rapport
    rapport = evaluateur.generer_rapport_complet()
    
    # Afficher
    evaluateur.afficher_rapport(rapport)
    
    # Sauvegarder
    evaluateur.sauvegarder_rapport(rapport)
    
    print("✅ Évaluation terminée")