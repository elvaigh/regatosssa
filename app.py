"""
Application Streamlit v2 - RAG Sécurité Incendie avec Thésaurus et Justifications
"""

import streamlit as st
import json
from pathlib import Path
from datetime import datetime
import base64

from rag import get_rag_engine_v2, ComportementAttendu, NiveauNormativite
from config import (
    get_thesaurus,
    get_jeu_reference,
    CORPUS_MAPPING,
    PIEGES,
)

# =====================================================
# Configuration Streamlit
# =====================================================

st.set_page_config(
    page_title="RAG Sécurité Incendie v2",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé amélioré
st.markdown("""
<style>
    /* Couleurs */
    :root {
        --primary: #DC143C;
        --secondary: #FF6B6B;
        --success: #2ECC71;
        --warning: #F39C12;
        --info: #3498DB;
        --dark: #2C3E50;
    }
    
    /* Header */
    .main-header {
        font-size: 2.5em;
        color: #DC143C;
        text-align: center;
        margin-bottom: 5px;
        font-weight: bold;
    }
    
    .subheader-main {
        font-size: 1.1em;
        text-align: center;
        color: #555;
        margin-bottom: 30px;
    }
    
    /* Boîtes */
    .box-reponse {
        background: linear-gradient(135deg, #e8f4f8 0%, #f0fafb 100%);
        padding: 20px;
        border-radius: 8px;
        border-left: 5px solid #3498DB;
        margin-bottom: 20px;
    }
    
    .box-citation {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 6px;
        border-left: 4px solid #FF6B6B;
        margin-bottom: 10px;
        font-size: 0.95em;
    }
    
    .box-piege {
        background: #fff3cd;
        padding: 12px;
        border-radius: 6px;
        border-left: 4px solid #F39C12;
        margin-bottom: 8px;
    }
    
    .box-variable {
        background: #e7f3ff;
        padding: 12px;
        border-radius: 6px;
        border-left: 4px solid #3498DB;
        margin-bottom: 8px;
    }
    
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85em;
        margin-right: 8px;
        margin-bottom: 8px;
    }
    
    .badge-erp {
        background: #FFE5E5;
        color: #DC143C;
    }
    
    .badge-ct {
        background: #E5F4FF;
        color: #3498DB;
    }
    
    .badge-hab {
        background: #E5FFE5;
        color: #27AE60;
    }
    
    .badge-confiance {
        background: #2ECC71;
        color: white;
    }
    
    .badge-confiance-low {
        background: #E74C3C;
        color: white;
    }
    
    .metric-card {
        background: white;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #ecf0f1;
        text-align: center;
    }
    
    .metric-value {
        font-size: 2em;
        font-weight: bold;
        color: #DC143C;
    }
    
    .metric-label {
        font-size: 0.9em;
        color: #7f8c8d;
    }
    
    /* Texte */
    .texte-alerte {
        color: #E74C3C;
        font-weight: bold;
    }
    
    .texte-success {
        color: #2ECC71;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# En-tête principal
# =====================================================

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown(
        '<p class="main-header">🔥 RAG Sécurité Incendie v2</p>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<p class="subheader-main">Réponses réglementaires justifiées et tracées</p>',
        unsafe_allow_html=True
    )

st.divider()

# =====================================================
# Sidebar - Configuration
# =====================================================

with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Initialiser RAG
    engine = get_rag_engine_v2()
    engine.construire_index("LEGISCTA000020303815.pdf")
    # Status index
    st.subheader("📊 État du système")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">96</div>
            <div class="metric-label">Notions</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">20</div>
            <div class="metric-label">Assertions</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.info("✅ Thésaurus chargé\n✅ Jeux d'évaluation disponibles")
    
    st.divider()
    
    # Sélection corpus
    st.subheader("📋 Corpus applicable")
    corpus_selected = st.multiselect(
        "Choisir corpus(es):",
        options=list(CORPUS_MAPPING.keys()),
        default=["ERP"],
        help="Multi-sélection possible"
    )
    
    # Options avancées
    st.subheader("🔍 Options")
    show_reformulation = st.toggle("Afficher reformulation", value=True)
    show_pieges = st.toggle("Afficher pièges détectés", value=True)
    show_jeu_evals = st.toggle("Afficher jeu de tests", value=False)
    k_results = st.slider("Nombre de documents", 3, 15, 8)
    
    st.divider()
    
    # À propos
    st.subheader("ℹ️ Version")
    st.markdown("""
    **RAG v2.0.0**
    
    **Intégrations:**
    - ✅ Thésaurus (96 notions)
    - ✅ Jeu référence (150 items)
    - ✅ Jeu adverse (60 items)
    - ✅ Few-shot learning
    - ✅ Assertions négatives
    - ✅ Traçabilité
    
    **Corpus:**
    - ERP (Arrêté 25/06/1980)
    - Habitation (CCH+1986)
    - Code du travail
    - IGH
    
    [Notice technique](https://www.legifrance.gouv.fr)
    """)

# =====================================================
# Zone de saisie
# =====================================================

st.subheader("❓ Votre question")

col1, col2 = st.columns([0.85, 0.15])
with col1:
    question = st.text_area(
        "Posez votre question réglementaire:",
        placeholder="Ex: Quelle est la largeur minimale d'une porte de secours en ERP?",
        height=100,
        label_visibility="collapsed"
    )

with col2:
    search_button = st.button(
        "🔍 Chercher",
        use_container_width=True,
        type="primary",
        key="search_btn"
    )

st.divider()

# =====================================================
# Traitement de la question
# =====================================================

if search_button and question:
    with st.spinner("⏳ Traitement en cours..."):
        try:
            # Traiter question
            reponse = engine.traiter_question(question, corpus_selected or None, k=k_results)
            
            # =====================================================
            # Affichage Reformulation
            # =====================================================
            
            if show_reformulation and reponse.reponse != "":
                with st.expander("🔄 Reformulation normative", expanded=False):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write(f"**Question reformulée:**")
                        st.info("Question reformulée via thésaurus (à implémenter)")
                    with col2:
                        confiance_color = "success" if reponse.confiance >= 0.8 else "warning"
                        st.metric(
                            "Confiance",
                            f"{reponse.confiance:.0%}",
                            delta=None
                        )
            
            # =====================================================
            # Affichage Pièges
            # =====================================================
            
            if show_pieges and reponse.pieges_evites:
                with st.expander("⚠️ Pièges détectés & évités", expanded=False):
                    for piege in reponse.pieges_evites:
                        piege_info = PIEGES.get(piege, {})
                        st.markdown(f"""
                        <div class="box-piege">
                        <strong>{piege_info.get('nom', piege)}</strong><br/>
                        {piege_info.get('description', '')}
                        </div>
                        """, unsafe_allow_html=True)
            
            # =====================================================
            # Affichage Variables manquantes
            # =====================================================
            
            if reponse.variables_manquantes:
                st.warning("ℹ️ Variables requises:")
                for var in reponse.variables_manquantes:
                    st.markdown(f"""
                    <div class="box-variable">
                    📌 <strong>{var}</strong> - Valeur requise pour préciser la réponse
                    </div>
                    """, unsafe_allow_html=True)
            
            # =====================================================
            # Affichage Réponse principale
            # =====================================================
            
            st.subheader("✅ Réponse")
            
            # Badges corpus et confiance
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                for corpus in (reponse.corpus_applique.split(",") if "," in reponse.corpus_applique else [reponse.corpus_applique]):
                    corpus = corpus.strip()
                    badge_class = f"badge-{corpus.lower()}" if corpus.lower() in ["erp", "ct", "hab"] else ""
                    st.markdown(f"""
                    <span class="badge {badge_class}">{corpus}</span>
                    """, unsafe_allow_html=True)
            
            with col2:
                if reponse.confiance >= 0.85:
                    st.success(f"Confiance: {reponse.confiance:.0%}")
                else:
                    st.warning(f"Confiance: {reponse.confiance:.0%}")
            
            with col3:
                st.info(f"Niveau: {reponse.niveau_normativite.value}")
            
            # Réponse
            st.markdown(f"""
            <div class="box-reponse">
            {reponse.reponse}
            </div>
            """, unsafe_allow_html=True)
            
            # =====================================================
            # Affichage Citations
            # =====================================================
            
            if reponse.citations:
                st.subheader("📑 Citations d'articles")
                
                for i, citation in enumerate(reponse.citations, 1):
                    with st.expander(f"📄 {citation.article} - {citation.titre}", expanded=(i == 1)):
                        st.markdown(f"""
                        <div class="box-citation">
                        <strong>Article:</strong> {citation.article}<br/>
                        <strong>Corpus:</strong> {citation.corpus}<br/>
                        <strong>Normativité:</strong> {citation.niveau_normativite.value}<br/>
                        <strong>Pertinence:</strong> {citation.score_pertinence:.0%}<br/>
                        <br/>
                        <strong>Extrait:</strong><br/>
                        {citation.texte}
                        """, unsafe_allow_html=True)
                        
                        if citation.url:
                            st.markdown(f"[🔗 Lire la source]({citation.url})")
            
            # =====================================================
            # Affichage Documents sources
            # =====================================================
            
            if reponse.documents_sources:
                with st.expander(f"📚 Documents sources ({len(reponse.documents_sources)})", expanded=False):
                    for i, doc in enumerate(reponse.documents_sources, 1):
                        st.markdown(f"""
                        **Document {i}** (Page {doc.page}) - Score: {doc.score:.2f}
                        
                        {doc.texte[:250]}...
                        """)
                        st.divider()
            
            # =====================================================
            # Affichage Justification
            # =====================================================
            
            if reponse.justification:
                with st.expander("📋 Justification complète", expanded=False):
                    st.write(reponse.justification)
            
            # =====================================================
            # Actions post-réponse
            # =====================================================
            
            st.divider()
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📋 Copier réponse"):
                    st.write("```\n" + reponse.reponse + "\n```")
            
            with col2:
                if st.button("📥 Exporter JSON"):
                    export_data = {
                        "timestamp": datetime.now().isoformat(),
                        "question": question,
                        "reponse": reponse.to_dict()
                    }
                    st.json(export_data)
            
            with col3:
                if st.button("🔄 Nouvelle question"):
                    st.rerun()
        
        except Exception as e:
            st.error(f"❌ Erreur: {e}")
            import traceback
            st.code(traceback.format_exc())

# =====================================================
# Affichage jeu d'évaluation
# =====================================================

if show_jeu_evals:
    st.divider()
    st.subheader("🧪 Jeu d'évaluation")
    
    jeu_ref = get_jeu_reference()
    
    tab1, tab2, tab3 = st.tabs(["📊 Statistiques", "✅ Exemples positifs", "❌ Pièges"])
    
    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total items", len(jeu_ref))
        with col2:
            st.metric("Profils", jeu_ref['profil'].nunique())
        with col3:
            repondre_count = len(jeu_ref[jeu_ref['comportement_attendu'] == 'repondre'])
            st.metric("Répondre", repondre_count)
        with col4:
            precision_count = len(jeu_ref[jeu_ref['comportement_attendu'] == 'demander_precision'])
            st.metric("Préciser", precision_count)
    
    with tab2:
        for idx, row in jeu_ref.head(5).iterrows():
            with st.expander(f"📌 {row['question_utilisateur'][:60]}..."):
                st.write(f"**Reformulation:** {row['reformulation_normative']}")
                st.write(f"**Corpus:** {row['corpus_attendu']}")
                st.write(f"**Articles:** {row['articles_attendus']}")
                st.write(f"**Comportement:** {row['comportement_attendu']}")
    
    with tab3:
        st.info("Section pièges - À implémenter")

# =====================================================
# Footer
# =====================================================

st.divider()


def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

logo1_base64 = get_base64_image("atossa.png")
logo2_base64 = get_base64_image("rimtech.png")

st.markdown(
    f"""
    <div style="text-align: center; padding: 20px;">
        <div style="display: flex; justify-content: center; align-items: center; gap: 30px; margin-bottom: 10px;">
            <img src="data:image/png;base64,{logo1_base64}" width="80">
            <img src="data:image/png;base64,{logo2_base64}" width="80">
        </div>
        <p style="color: #999; font-size: 0.9em;">
        🔒 Sécurité Incendie ERP/Habitation/Code du travail | v2.0.0
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)