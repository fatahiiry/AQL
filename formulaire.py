from datetime import date, datetime
import re
import time
import io
import os
import base64
import pandas as pd
from PIL import Image
import streamlit as st
import database as db
import business as biz
from modeles_match import choisir_modele_base
from grille_mesures import (trier_tailles, construire_grille, options_grille_empilee,
                                hauteur_grille, grille_vers_records, compter_hors_tolerance)
from recontrole_mesures import (extraire_hors_tolerance, construire_grille_recontrole,
                                lire_saisies, bilan, options_grille_recontrole,
                                hauteur_recontrole, enregistrer_recontrole)
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

_SCRIPT_MODE_CAMERA = """
<script>
const doc = window.parent.document;
setTimeout(() => {
    const videos = doc.querySelectorAll('video');
    videos.forEach(video => {
        if (video.srcObject) {
            video.srcObject.getTracks().forEach(track => track.stop());
        }
    });
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "__FACING__" } })
    .then(stream => {
        videos.forEach(video => {
            video.srcObject = stream;
        });
    }).catch(err => console.log(err));
}, 400);
</script>
"""


def _injecter_html(html, hauteur=0):
    """components.html (déprécié dans les Streamlit récents) ; repli sur st.iframe s'il est retiré."""
    try:
        import streamlit.components.v1 as components
        components.html(html, height=hauteur)
    except Exception:
        if hasattr(st, 'iframe'):
            st.iframe(html, height=max(hauteur, 1))


def appliquer_mode_camera(facing_mode):
    """facing_mode = 'environment' (arrière) ou 'user' (avant). À appeler avant st.camera_input."""
    _injecter_html(_SCRIPT_MODE_CAMERA.replace('__FACING__', facing_mode))


def demarrer_reprise(cle):
    """Bouton « Reprendre » : l'ancienne photo reste affichée jusqu'à la nouvelle prise."""
    st.session_state['nc1_reprise'] = cle
    st.session_state['cam_nc_idx'] += 1               # widget caméra tout neuf


def annuler_reprise():
    st.session_state['nc1_reprise'] = None


def etiquette_fichier(texte, max_len=40):
    """'Fil tiré (grand)' -> 'Fil-tiré-grand' : utilisable dans un nom de fichier."""
    t = ''.join(c if c.isalnum() else '-' for c in str(texte).strip())
    t = '-'.join(p for p in t.split('-') if p)
    return t[:max_len].strip('-') or 'defaut'

def actualiser_echantillon():
    qte_pres = st.session_state.get('ctrl_qtepres_widget', 0)

    # 1. Dépaquetage
    qte_ctrl, maj_tolere, min_tolere = db.get_norme_values(qte_pres)

    # 2. Mise à jour de st.session_state
    st.session_state['ctrl_qtectrl_widget'] = qte_ctrl
    st.session_state['limite_maj_max'] = maj_tolere
    st.session_state['limite_min_max'] = min_tolere
    st.session_state['widget_maj'] = maj_tolere
    st.session_state['widget_min'] = min_tolere

def reinitialiser_formulaire():
    """Réinitialise l'état de l'application en toute sécurité pour Streamlit."""
    # Incrémentation du compteur de version pour forcer la remise à neuf des widgets
    st.session_state.form_version = st.session_state.get('form_version', 0) + 1

    # Remise à zéro des compteurs de défauts
    st.session_state.maj_counter = 0
    st.session_state.min_counter = 0
    st.session_state.sec_counter = 0

    # Purge des clés hors-widgets
    keys_a_purger = ['photo_nc_bytes', 'description_nc1_val', 'description_nc2_val', 'sauvegarde_mesures']
    for k in keys_a_purger:
        if k in st.session_state:
            del st.session_state[k]

def render_formulaire():
    # ── 🟢 0. INITIALISATION DE LA VERSION (OBLIGATOIRE AU TOUT DÉBUT) ──
    if "form_version" not in st.session_state:
        st.session_state.form_version = 0

    version = st.session_state.form_version

    tab_ident, tab_defauts, tab_traitement, tab_sur_mesure, tab_pj, tab_facture = st.tabs([
        '📋 1. Identification & Volumes',
        '⚠️ 2. Compteurs de Défauts',
        '🔄 3. Décision & Résultats du Tri',
        '📏 4. Tableau de Mesure',
        "📎 5. Pièces jointes",
        "🧾 6. Numéro facture",
    ])

    # ── ONGLET 1 : Identification & Volumes ──
    with tab_ident:
        st.markdown('<div class="section-header">🔍 Recherche et sélection de l\'OF</div>', unsafe_allow_html=True)
        # Découpage : 1 colonne étroite pour la recherche + 1 colonne large vide
        col_search, col_espace = st.columns([1, 2])

        with col_search:
            of_search_input = st.text_input(
                "Saisissez le N° d'OF à rechercher...",
                value="",
                placeholder="Ex: 958...",
            )

        suggestions = db.search_of_suggestions(of_search_input)
        selected_row = None

        if suggestions:
            chosen_of = st.selectbox("Résultat(s) trouvé(s) - Choisissez l'OF exact :", options=suggestions, key=f'of_exact_select_{version}')
            records_df = db.get_of_records(chosen_of)

            if not records_df.empty:
                if len(records_df) > 1:
                    options_labels = [
                        f"Ligne {i + 1} : Article: {r['article']} | Coloris: {r['coloris']} | Qté Réf (Excel cde_mere): {r['cde_mere']}"
                        for i, r in records_df.iterrows()
                    ]
                    chosen_index = st.selectbox(
                        '⚠️ Plusieurs déclinaisons trouvées pour cet OF. Sélectionnez la bonne ligne :',
                        options=range(len(options_labels)),
                        format_func=lambda x: options_labels[x],
                        key=f'declinaison_select_{version}',
                    )
                    selected_row = records_df.iloc[chosen_index]
                else:
                    selected_row = records_df.iloc[0]
        else:
            if len(of_search_input) >= 1:
                st.warning('⚠️ Aucun OF correspondant trouvé dans la table.')
            else:
                st.info('💡 Saisissez le numéro d\'OF pour activer la recherche automatique.')

        auto_client = biz.clean_val(selected_row, 'client')
        auto_reference = biz.clean_val(selected_row, 'reference')
        auto_of = biz.clean_val(selected_row, 'num_of', default=of_search_input)
        auto_article = biz.clean_val(selected_row, 'article')
        auto_norme = biz.clean_val(selected_row, 'norme')
        auto_coloris = biz.clean_val(selected_row, 'coloris')

        try:
            val_cde_mere = biz.clean_val(selected_row, 'cde_mere', default='0')
            auto_qte_of = int(float(val_cde_mere)) if val_cde_mere else 0
        except ValueError:
            auto_qte_of = 0

        st.markdown('<div class="section-header">📋 Formulaire d\'identification du lot</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            date_controle = st.date_input('📅 Date *', value=date.today(), key='ctrl_date_widget')
            liste_chaines_db = db.fetch_db_chaines()
            chaine = st.selectbox('Chaîne *', options=liste_chaines_db, key='ctrl_chaine_widget')
            client = st.text_input('Client *', value=auto_client, key=f'ctrl_client_{auto_client}_{version}')
        with c2:
            controleur = st.text_input('Contrôleur final *', key='controleur_final')
            of_val = st.text_input('OF *', value=auto_of, disabled=(selected_row is not None), key=f'ctrl_of_{auto_of}_{version}')
            article = st.text_input('Article *', value=auto_article, key=f'ctrl_art_{auto_article}_{version}')
        with c3:
            reference = st.text_input('Référence', value=auto_reference, key=f'ctrl_ref_manual_widget_{auto_reference}_{version}')
            norme = st.text_input('Norme', value=auto_norme, key=f'ctrl_norme_{auto_norme}_{version}')
            coloris = st.text_input('Coloris', value=auto_coloris, key=f'ctrl_col_{auto_coloris}_{version}')

        # Quantités, Cartons et Échantillonnage
        st.markdown('<div class="section-header">📦 Quantités et Échantillonnage</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            qte_of = st.number_input('Cde mere', min_value=0, step=1, value=auto_qte_of, key=f'ctrl_qteof_{auto_qte_of}_{version}')
        with c2:
            qte_presentee = st.number_input('Qté présentée *', min_value=0, step=1, key='ctrl_qtepres_widget', on_change=actualiser_echantillon)
        with c3:
            cartons_presentes = st.text_input('📦 Cartons présentés', placeholder='Ex: 12-13-34', key='ctrl_cartons_pres_widget')
        with c4:
            num_palette = st.text_input('N° Palette', key='ctrl_palette_widget')

        liste_cartons = [c.strip() for c in re.split(r'[-,;\s]+', cartons_presentes) if c.strip()]
        c_ctrl_qte, c_ctrl_cartons = st.columns(2)

        with c_ctrl_qte:
            qte_controlee = st.number_input('Qté contrôlée *', min_value=0, step=1, key='ctrl_qtectrl_widget')

        with c_ctrl_cartons:
            if liste_cartons:
                cartons_controles_list = st.multiselect('🔎 N° cartons contrôlés', options=liste_cartons, help='Sélectionnez les cartons contrôlés', key=f'ctrl_cartons_ctrl_select_{version}')
                cartons_controles = ' - '.join(cartons_controles_list)
            else:
                cartons_controles = st.text_input('🔎 N° cartons contrôlés', placeholder="Renseignez d'abord 'Cartons présentés'", key=f'ctrl_cartons_ctrl_input_{version}')

        st.session_state['carton_controle_val'] = cartons_controles

        pct_controle = ((int(qte_controlee) / int(qte_presentee) * 100) if qte_presentee > 0 else 0.0)
        pct_ctrl_class = ('danger' if pct_controle < 10 else ('warning' if pct_controle < 50 else 'value'))

        st.markdown(f'<div class="calc-box"><div class="label">📊 % Contrôlé = Qté contrôlée / Qté présentée (Instantané)</div><div class="value {pct_ctrl_class}">{pct_controle:.2f} %</div></div>', unsafe_allow_html=True)

        if of_val:
            try:
                qte_target = int(qte_of) if (qte_of and int(qte_of) > 0) else 0
                cumul_bdd = db.get_cumul_controled_db(of_val, qte_target)
                qte_actuelle = int(qte_presentee) if qte_presentee else 0
                total_cumul = cumul_bdd + qte_actuelle

                if qte_target > 0:
                    pct_cumul_val = (float(total_cumul) / float(qte_target)) * 100.0
                    details = f'{total_cumul} / {qte_target} pcs'
                    decompte = f'BDD ({cumul_bdd}) + Saisie ({qte_actuelle})'
                    cumul_class = 'danger' if pct_cumul_val < 5 else 'value'

                    st.markdown(
                        f"""
                        <div class="calc-box" style="margin-top: 10px; border-left: 5px solid #2d6a9f;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div class="label">📈 % Contrôlé Cumulé — <small>({details})</small></div>
                                <div style="font-size: 0.85em; color: #2d6a9f; background: #eef5fc; padding: 3px 8px; border-radius: 4px; font-weight: 500;">➕ {decompte}</div>
                            </div>
                            <div class="value {cumul_class}" style="margin-top: 5px;">{pct_cumul_val:.2f} %</div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
            except Exception as e:
                st.error(f'❌ Erreur lors du calcul automatique : {e}')

    # Dossiers locaux
    PHOTO_DIR = r'\\nvserveur\Dossiers Services\QUALITE\Contrôle\Photos defauts'
    PIECES_JOINTE_DIR = r'\\nvserveur\Dossiers Services\QUALITE\Contrôle\PIèces Jointes'
    os.makedirs(PHOTO_DIR, exist_ok=True)
    os.makedirs(PIECES_JOINTE_DIR, exist_ok=True)

    # ── ONGLET 2 : Compteurs de Défauts & Photo ──
    MAX_PHOTOS_NC = 10

    # Initialisation (à placer avant le bloc, une seule fois)
    if not isinstance(st.session_state.get('photos_nc'), dict):
        st.session_state['photos_nc'] = {}
    if 'cam_nc_idx' not in st.session_state:
        st.session_state['cam_nc_idx'] = 0

    # ── ONGLET 2 : Compteurs de Défauts & Photo  ──
    with tab_defauts:
            st.markdown('<div class="section-header">🛠️ Saisie Tactile des Défauts</div>', unsafe_allow_html=True)

            limite_maj = st.session_state.get('limite_maj_max', 0)
            limite_min = st.session_state.get('limite_min_max', 0)

            col_maj, col_min, col_sec = st.columns(3)

            # ── DÉFAUTS MAJEURS ──
            with col_maj:
                st.write(f'**Défauts Majeurs** *(Max toléré : {limite_maj})*')
                sub_c1, sub_c2 = st.columns(2)
                sub_c1.button('➕ Ajouter Majeur', key=f'add_maj_{version}', on_click=biz.inc_majeur)
                sub_c2.button('➖ Retirer Majeur', key=f'rem_maj_{version}', on_click=biz.dec_majeur)

                defaut_majeur = st.number_input('Valeur enregistrée', min_value=0, step=1, key='maj_counter')
                if defaut_majeur > limite_maj:
                    st.error(f'⚠️ Seuil dépassé ! ({defaut_majeur} > {limite_maj} max)')

            # ── DÉFAUTS MINEURS ──
            with col_min:
                st.write(f'**Défauts Mineurs** *(Max toléré : {limite_min})*')
                sub_c1, sub_c2 = st.columns(2)
                sub_c1.button('➕ Ajouter Mineur', key=f'add_min_{version}', on_click=biz.inc_mineur)
                sub_c2.button('➖ Retirer Mineur', key=f'rem_min_{version}', on_click=biz.dec_mineur)

                defaut_mineur = st.number_input('Valeur enregistrée', min_value=0, step=1, key='min_counter')
                if defaut_mineur > limite_min and limite_min > 0:
                    st.warning(f'⚠️ Seuil dépassé ! ({defaut_mineur} > {limite_min} max)')

            # ── DÉFAUTS SÉCURITAIRES ──
            with col_sec:
                st.write('**Défauts Sécuritaires** *(Max : 0)*')
                sub_c1, sub_c2 = st.columns(2)
                sub_c1.button('➕ Ajouter Sécu', key=f'add_sec_{version}', on_click=biz.inc_secu)
                sub_c2.button('➖ Retirer Sécu', key=f'rem_sec_{version}', on_click=biz.dec_secu)

                defaut_securitaire = st.number_input('Valeur enregistrée', min_value=0, step=1, key='sec_counter')
                if defaut_securitaire > 0:
                    st.error('🚨 Défaut critique/sécuritaire présent !')

            st.markdown('---')
            total_defaut = defaut_majeur + defaut_mineur + defaut_securitaire
            st.session_state['widget_total_defauts'] = total_defaut

            st.markdown(
                f'<div class="calc-box"><div class="label">🚨 Total Défauts Saisis</div><div class="value">{total_defaut}</div></div>',
                unsafe_allow_html=True)
            st.markdown('---')

            col_nc_left, col_photo_right = st.columns([1, 1], gap='medium')

            # ── NC 1 : description (sélection multiple) + une photo par non-conformité ──
            with col_nc_left:
                st.markdown('##### 📝 Non-Conformité 1 (NC 1)')
                raw_data_nc1 = db.fetch_db_typologie_defauts() or []
                liste_defauts_raw1 = [
                    str(item[0]).strip() if isinstance(item, (tuple, list)) else str(item).strip()
                    for item in raw_data_nc1 if item
                ]
                AUTRE_DEFAUT = '➕ Autre (saisie libre)'
                options_tab2 = [AUTRE_DEFAUT] + liste_defauts_raw1

                defauts_choisis = st.multiselect(
                    'Sélection du ou des défauts NC 1',
                    options=options_tab2,
                    placeholder='Choisissez un ou plusieurs défauts',
                    key=f'nc1_multi_{version}',
                )

                liste_desc_nc1 = []  # textes enregistrés dans la description
                libelles_nc = {}  # clé -> libellé : UNE photo possible par clé

                for d in defauts_choisis:
                    if d != AUTRE_DEFAUT:
                        liste_desc_nc1.append(d)
                        libelles_nc[d] = d

                if AUTRE_DEFAUT in defauts_choisis:
                    texte_libre = st.text_area('📝 Préciser le défaut (Saisie libre) *', height=100,
                                               key=f'nc1_area_custom_{version}').strip()
                    if texte_libre:
                        liste_desc_nc1.append(texte_libre)
                        libelles_nc[AUTRE_DEFAUT] = texte_libre

                st.session_state['nc1_libelles'] = libelles_nc  # lu par le bouton Enregistrer

                description_nc1 = ' ; '.join(liste_desc_nc1)

                remarques_nc1 = st.text_area('💬 Remarques & Observations (Optionnel)', height=120,
                                             key=f'nc1_remarques_input_{version}')
                if remarques_nc1.strip() and description_nc1:
                    description_nc1 += f' | Remarques: {remarques_nc1.strip()}'

                st.session_state['description_nc1_val'] = description_nc1

            with col_photo_right:
                st.markdown('##### 📸 Photo de chaque non-conformité')

                photos = st.session_state['photos_nc']
                for cle in [c for c in photos if c not in libelles_nc]:
                    del photos[cle]  # pas de photo sans non-conformité

                reprise = st.session_state.get('nc1_reprise')
                if reprise not in libelles_nc:
                    reprise = st.session_state['nc1_reprise'] = None

                if not libelles_nc:
                    st.info("👉 Choisissez d'abord une non-conformité : une photo pourra être prise pour chacune.")
                else:
                    sans_photo = [c for c in libelles_nc if c not in photos]
                    st.caption(f'📷 {len(photos)}/{len(libelles_nc)} non-conformité(s) photographiée(s)')

                    cle_cible = None
                    if reprise:
                        cle_cible = reprise
                        st.warning(f'🔄 Reprise de « {libelles_nc[reprise]} » : l\'ancienne photo est conservée '
                                   'jusqu\'à la nouvelle prise.')
                        st.button('✖ Annuler la reprise', key=f'annuler_reprise_{version}', on_click=annuler_reprise)
                    elif not sans_photo:
                        st.success('✅ Chaque non-conformité a sa photo.')
                    elif len(sans_photo) == 1:
                        cle_cible = sans_photo[0]
                    else:
                        cle_select = f'nc1_cible_{version}'
                        if st.session_state.get(cle_select) not in sans_photo:
                            st.session_state.pop(cle_select, None)
                        cle_cible = st.selectbox('Défaut à photographier', options=sans_photo,
                                                 format_func=lambda c: libelles_nc[c], key=cle_select)

                    if cle_cible is not None:
                        st.markdown(f'**Photo pour :** {libelles_nc[cle_cible]}')

                        # ── Caméra arrière par défaut (décocher pour la caméra avant)
                        use_cam_arriere = st.toggle('📷 Utiliser la caméra arrière', value=True,
                                                    key=f'toggle_cam_{version}')
                        appliquer_mode_camera('environment' if use_cam_arriere else 'user')

                        photo_nc_file = st.camera_input(
                            f'Photo : {libelles_nc[cle_cible]}',
                            key=f"camera_nc1_{version}_{st.session_state['cam_nc_idx']}"
                        )
                        if photo_nc_file is not None:
                            photos[cle_cible] = photo_nc_file.getvalue()  # 1 photo = 1 non-conformité
                            st.session_state['nc1_reprise'] = None
                            st.session_state['cam_nc_idx'] += 1  # nouveau widget -> vide
                            st.rerun()

                    # Miniatures, dans l'ordre des non-conformités
                    prises = [c for c in libelles_nc if c in photos]
                    if prises:
                        cols = st.columns(3)
                        for i, cle in enumerate(prises):
                            with cols[i % 3]:
                                legende = libelles_nc[cle] + (' (sera remplacée)' if cle == reprise else '')
                                st.image(photos[cle], caption=legende, width="stretch")
                                st.button('🔄 Reprendre', key=f'reprise_photo_{version}_{i}',
                                          on_click=demarrer_reprise, args=(cle,))

            st.markdown('---')
            qte_controlee = st.session_state.get('ctrl_qtectrl_widget', 0)
            pct_defaut = ((int(total_defaut) / int(qte_controlee) * 100) if qte_controlee > 0 else 0.0)
            pct_def_class = ('danger' if pct_defaut >= 5 else ('warning' if pct_defaut >= 2 else 'value'))

            st.markdown(
                f'<div class="calc-box"><div class="label">📊 % Défaut = Total défaut / Qté contrôlée (Instantané)</div>'
                f'<div class="value {pct_def_class}">{pct_defaut:.2f} %</div></div>',
                unsafe_allow_html=True)

            st.button('🔄 Réinitialiser tous les compteurs à 0', key=f'btn_reset_cnt_{version}',
                      on_click=biz.reset_compteurs)

    # ── ONGLET 3 : Décision & Résultats du Tri ──
    with tab_traitement:
        st.markdown('<div class="section-header">⚖️ Conclusion & Décision</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)

        with c1:
            st.info("💡 La **Description NC 1** et la **Photo** sont renseignées dans l'onglet Compteurs de Défauts.")

        with c2:
            # ── 🎯 LECTURE DIRECTE DU SESSION STATE EN TEMPS RÉEL ──
            cnt_maj = st.session_state.get('maj_counter', 0)
            cnt_min = st.session_state.get('min_counter', 0)
            cnt_sec = st.session_state.get('sec_counter', 0)

            lim_maj = st.session_state.get('limite_maj_max', 0)
            lim_min = st.session_state.get('limite_min_max', 0)

            # ── ÉVALUATION DES DÉPASSEMENTS ──
            dep_maj = cnt_maj > lim_maj
            dep_min = cnt_min > lim_min and lim_min > 0
            dep_sec = cnt_sec > 0

            # Décision Refusé si au moins un des 3 compteurs dépasse sa limite
            if dep_maj or dep_min or dep_sec:
                decision_initiale = 'Refusé'
                badge_color = '#dc2626'
                badge_icon = '❌'

                causes = []
                if dep_maj: causes.append(f"Majeurs ({cnt_maj} > {lim_maj})")
                if dep_min: causes.append(f"Mineurs ({cnt_min} > {lim_min})")
                if dep_sec: causes.append(f"Sécuritaires ({cnt_sec})")
                txt_causes = "Motif : " + " | ".join(causes)
            else:
                decision_initiale = 'Accepté'
                badge_color = '#16a34a'
                badge_icon = '✅'
                txt_causes = "Lot conforme aux limites AQL"

            decision_finale = decision_initiale

            st.markdown(
                f"""
                        <div style="background-color: #f8fafc; border: 2px solid {badge_color}; border-radius: 8px; padding: 12px; text-align: center; margin-bottom: 10px;">
                            <span style="font-size: 0.85em; color: #475569; font-weight: bold;">⚖️ DÉCISION AUTOMATIQUE AQL</span><br/>
                            <span style="font-size: 1.4em; color: {badge_color}; font-weight: bold;">{badge_icon} {decision_initiale}</span><br/>
                            <small style="color: {badge_color}; font-weight: bold;">{txt_causes}</small>
                        </div>
                        """,
                unsafe_allow_html=True,
            )

            if decision_initiale == 'Refusé':
                st.warning('⚠️ Le lot a été automatiquement calculé comme **Refusé**.')
                appliquer_derogation = st.checkbox('🙋 Appliquer une dérogation ?', key=f'chk_derogation_{version}')
                if appliquer_derogation:
                    decision_finale = st.selectbox(
                        '📌 Nouvelle décision suite à dérogation :',
                        ['Accepté sous dérogation', 'Dérogation client', 'Refusé'],
                        key=f'derogation_select_{version}'
                    )
        st.markdown('<div class="section-header">🔄 Résultats & Coûts du tri</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            quantite_triee = st.number_input('Quantité triée', min_value=0, step=1, value=0, key='tri_qte_widget')
        with c2:
            total_defaut_tri = st.number_input('Total défauts au tri', min_value=0, step=1, value=0, key='tri_tot_widget')
        with c3:
            nb_defauts_tri = st.number_input('Nb défauts au tri', min_value=0, step=1, value=0, key='tri_nb_widget')
        with c4:
            numero_qc = st.text_input('N° QC', key='tri_qc_widget')

        st.markdown('##### 📝 Description Non-Conformité 2 (Tri)')
        raw_data_nc2 = db.fetch_db_typologie_defauts() or []
        liste_defauts_raw2 = [
            str(item[0]).strip() if isinstance(item, (tuple, list)) else str(item).strip()
            for item in raw_data_nc2 if item
        ]
        AUTRE_DEFAUT_2 = '➕ Autre (saisie libre)'
        options_tab3 = [AUTRE_DEFAUT_2] + liste_defauts_raw2

        defauts_choisis_nc2 = st.multiselect(
            '📝 Description NC 2 (Tri) : un ou plusieurs défauts',
            options=options_tab3,
            placeholder='Choisissez un ou plusieurs défauts',
            key=f'nc2_multi_{version}',
        )

        liste_desc_nc2 = [d for d in defauts_choisis_nc2 if d != AUTRE_DEFAUT_2]

        if AUTRE_DEFAUT_2 in defauts_choisis_nc2:
            texte_libre_nc2 = st.text_area('📝 Préciser la description NC 2 (Saisie libre)', height=90,
                                           key=f'nc2_area_custom_{version}').strip()
            if texte_libre_nc2:
                liste_desc_nc2.append(texte_libre_nc2)

        description_nc2_val = ' ; '.join(liste_desc_nc2)

        st.session_state['description_nc2_val'] = description_nc2_val

        pct_defaut_tri = ((float(total_defaut_tri) / float(quantite_triee) * 100.0) if quantite_triee > 0 else 0.0)
        pct_tri_class = ('danger' if pct_defaut_tri >= 5 else ('warning' if pct_defaut_tri >= 2 else 'value'))

        st.markdown(f'<div class="calc-box"><div class="label">📊 % Défaut au tri = Total défauts tri / Quantité triée (Automatique)</div><div class="value {pct_tri_class}">{pct_defaut_tri:.2f} %</div></div>', unsafe_allow_html=True)

        st.markdown('<div class="section-header">💰 Évaluation financière</div>', unsafe_allow_html=True)
        cc1, cc2 = st.columns(2)
        with cc1:
            temps_tri = st.number_input('Temps de tri (mn)', min_value=0.0, step=0.5, format='%.1f', value=0.0, key='time_widget')
        with cc2:
            cout_mn = st.number_input('Coût / mn ($)', min_value=0.0, step=0.01, format='%.2f', value=0.0, key='cost_widget')

        cout_tri_auto = round(float(temps_tri * cout_mn), 2)
        st.markdown(f'<div class="calc-box" style="margin-top: 10px; margin-bottom: 25px;"><div class="label">💰 Coût total du Tri Calculé (Temps × Coût/mn)</div><div class="value" style="color: #2d6a9f;">{cout_tri_auto:.2f} $</div></div>', unsafe_allow_html=True)

    # ── ONGLET 4 : Tableau de Mesure ──
    with tab_sur_mesure:
        st.markdown('<div class="section-header">📏 Grille de Contrôle Sur-Mesure</div>', unsafe_allow_html=True)

        ref_val = auto_reference if 'auto_reference' in locals() else ''
        coloris_base = auto_coloris if 'auto_coloris' in locals() else ''
        of_base = auto_of if 'auto_of' in locals() else ''

        of_val = st.session_state.get(f'ctrl_of_{of_base}_{version}', of_base)
        ref_val = st.session_state.get(f'ctrl_ref_manual_widget_{ref_val}_{version}', ref_val)
        chaine_val = st.session_state.get('ctrl_chaine_widget', '')
        date_val = st.session_state.get('ctrl_date_widget', date.today())
        coloris_val = st.session_state.get(f'ctrl_col_{coloris_base}_{version}', coloris_base)
        ctrl_val = st.session_state.get('controleur_final', '')
        ctrl_final_nom = str(ctrl_val).strip() if ctrl_val and str(ctrl_val).strip() else 'Non renseigné'
        qte_val = st.session_state.get('ctrl_qtectrl_widget', 0)

        if ref_val:
            date_str = date_val.strftime('%d/%m/%Y') if hasattr(date_val, 'strftime') else str(date_val)
            st.markdown(
                f"""
                <div style="background-color: #f8fafc; padding: 12px 16px; border-radius: 8px; border: 1px solid #cbd5e1; margin-bottom: 15px;">
                    <small style="color: #475569; font-weight: bold;">📌 RAPPEL DES INFORMATIONS DU CONTRÔLE (ONGLET 1)</small><br>
                    <b>OF :</b> {of_val} | <b>Modèle :</b> {ref_val} | <b>Chaîne :</b> {chaine_val} | <b>Date :</b> {date_str} <br>
                    <b>Qté Contrôlée :</b> {qte_val} | <b>Coloris :</b> {coloris_val} | <b>Contrôleur :</b> {ctrl_final_nom}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ── 🔗 Résolution du modèle ──
            modele_base = choisir_modele_base(ref_val, version, db.engine)

            df_raw = pd.DataFrame()
            if modele_base:
                conn = db.get_connection()
                query = """
                    SELECT point_de_mesure, tolerance, taille, valeur_cible
                    FROM mesures_modele
                    WHERE LOWER(TRIM(nom_modele)) = LOWER(TRIM(?))
                    ORDER BY id ASC
                """
                df_raw = pd.read_sql(query, conn, params=[str(modele_base).strip()])
                if df_raw.empty:
                    st.warning(f"⚠️ Le modèle « {modele_base} » existe mais ne contient aucune mesure.")
                elif str(modele_base).strip().upper() != str(ref_val).strip().upper():
                    st.caption(f'🔗 Mesures chargées depuis le modèle « {modele_base} »')

            if not df_raw.empty:
                # ── 📐 Un seul tableau : tailles par blocs de 4, blocs empilés ──
                tailles = trier_tailles(df_raw['taille'])
                nonce = st.session_state.get('grille_nonce', 0)    # change après un enregistrement
                df_init, blocs, nb_slots = construire_grille(df_raw, tailles)

                cle_base = f'{ref_val}_{modele_base}_{nonce}_{version}'
                cle_etat = f'grille_etat_{cle_base}'

                if cle_etat in st.session_state:          # conserve la saisie entre deux rafraîchissements
                    df_grille = pd.DataFrame(st.session_state[cle_etat])
                else:
                    df_grille = df_init

                st.caption(
                    f"📐 Tailles : {', '.join(tailles)} — saisissez les mesures dans les colonnes "
                    f"P1 à P{4} de chaque taille. Les tailles suivantes sont affichées plus bas, dans le même tableau."
                )

                grid_response = AgGrid(
                    df_grille,
                    gridOptions=options_grille_empilee(nb_slots),
                    allow_unsafe_jscode=True,
                    theme='streamlit',
                    height=hauteur_grille(len(df_grille)),
                    fit_columns_on_grid_load=True,
                    key=f'grid_mesures_{cle_base}',
                )

                df_edite = pd.DataFrame(grid_response['data'])
                st.session_state[cle_etat] = df_edite.to_dict(orient='records')

                # Seules les tailles où une pièce a été saisie sont retenues pour l'enregistrement
                mesures_par_taille = grille_vers_records(df_edite, tailles, blocs)
                nb_hors_tol = compter_hors_tolerance(mesures_par_taille)

                if nb_hors_tol > 0:
                    st.error(f'🚨 **{nb_hors_tol} mesure(s)** hors tolérance détectée(s) au total !')
                elif mesures_par_taille:
                    st.success(f'✅ Toutes les mesures renseignées ({len(mesures_par_taille)} taille(s)) sont dans les tolérances.')
                else:
                    st.info('ℹ️ Aucune mesure saisie pour le moment.')

                # ── 🔴 Contre-contrôle des mesures hors tolérance (5 cases par point) ──
                hors_tol_liste = extraire_hors_tolerance(mesures_par_taille, tailles)
                if hors_tol_liste:
                    st.markdown('---')
                    st.markdown('##### 🔴 Contre-contrôle : points hors tolérance à mesurer à nouveau')
                    st.caption(
                        'Chaque ligne est un point hors tolérance (taille en rouge). Mesurez-le à nouveau '
                        'dans les 5 cases : vert = conforme, rouge = encore hors tolérance.'
                    )

                    cle_saisies = f'recontrole_saisies_{cle_base}'
                    saisies_rc = st.session_state.setdefault(cle_saisies, {})
                    df_rc = construire_grille_recontrole(hors_tol_liste, saisies_rc)
                    signature = abs(hash(tuple((h['taille'], h['point'], tuple(h['hors'])) for h in hors_tol_liste)))

                    grid_rc = AgGrid(
                        df_rc,
                        gridOptions=options_grille_recontrole(),
                        allow_unsafe_jscode=True,
                        theme='streamlit',
                        height=hauteur_recontrole(len(df_rc)),
                        fit_columns_on_grid_load=True,
                        key=f'grid_recontrole_{cle_base}_{signature}',
                    )
                    df_rc_edite = pd.DataFrame(grid_rc['data'])
                    saisies_rc.update(lire_saisies(df_rc_edite))

                    nb_mesures_rc, nb_ok_rc, nb_nc_rc = bilan(df_rc_edite)
                    if nb_mesures_rc == 0:
                        st.info(f'ℹ️ {len(df_rc)} point(s) à contrôler à nouveau.')
                    elif nb_nc_rc:
                        st.error(f'🚨 {nb_nc_rc} point(s) toujours hors tolérance après contre-contrôle '
                                 f'({nb_ok_rc} conforme(s) sur {len(df_rc)}).')
                    else:
                        st.success(f'✅ {nb_ok_rc} point(s) conforme(s) sur {len(df_rc)} après contre-contrôle.')

                    if st.button('💾 Enregistrer le contre-contrôle', key=f'btn_save_recontrole_{cle_base}'):
                        try:
                            nb_lignes_rc = enregistrer_recontrole(
                                db.engine,
                                {'num_of': of_val, 'reference': ref_val, 'modele_mesures': modele_base,
                                 'controleur': ctrl_final_nom, 'date_controle': date_val},
                                df_rc_edite,
                            )
                            if nb_lignes_rc:
                                st.success(f'✅ {nb_lignes_rc} point(s) enregistré(s) dans le contre-contrôle.')
                            else:
                                st.warning('⚠️ Aucune mesure saisie dans le contre-contrôle.')
                        except Exception as e:
                            st.error(f'❌ Erreur lors de l\'enregistrement du contre-contrôle : {e}')

                st.markdown('---')
                st.markdown('##### ⚖️ Décision Globale des Mesures')
                col_dec, col_info = st.columns([2, 3])

                with col_dec:
                    decision_mesure = st.radio('Statut du contrôle sur mesure :', options=['Conforme', 'Non Conforme'],
                                               index=0, horizontal=True,
                                               key=f'radio_decision_mesure_{ref_val}_{version}')

                with col_info:
                    badge_color = '#16a34a' if decision_mesure == 'Conforme' else '#dc2626'
                    st.markdown(
                        f"""
                        <div style="background-color: #f8fafc; border: 1px solid {badge_color}; border-radius: 6px; padding: 10px 12px; text-align: center;">
                            <span style="font-size: 0.85em; color: #475569;">STATUT MESURES :</span><br> 
                            <b style="color: {badge_color}; font-size: 1.1em;">{decision_mesure.upper()}</b>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.markdown('---')
                if st.button("💾 Enregistrer toutes les mesures", key=f"btn_save_mesures_{ref_val}_{version}"):
                    try:
                        if not mesures_par_taille:
                            st.warning("⚠️ Aucune mesure renseignée à enregistrer.")
                        else:
                            for t_key, t_data in mesures_par_taille.items():
                                mesures_data = {
                                    "num_of": of_val,
                                    "chaine": chaine_val,
                                    "date_controle": date_val,
                                    "reference": ref_val,
                                    "qte_controlee": qte_val,
                                    "coloris": coloris_val,
                                    "taille": t_key,
                                    "controleur": ctrl_final_nom,
                                    "statut_mesure": decision_mesure,
                                    "details_mesures": t_data,
                                }
                                db.insert_mesures_record(mesures_data)

                            st.success(
                                f"✅ Mesures de {len(mesures_par_taille)} taille(s) enregistrées dans 'controle_sur_mesure' !")
                            st.session_state['grille_nonce'] = nonce + 1    # remet le tableau à vide
                            st.rerun()

                    except Exception as e:
                        st.error(f"❌ Erreur lors de la sauvegarde : {e}")

    # ── ONGLET 5 : Pièces jointes ──
    with tab_pj:
        st.subheader("📎 Pièces jointes et Documents associés")
        fichiers_joints = st.file_uploader(
            "Téléverser des fichiers (Images, PDF)",
            type=["png", "jpg", "jpeg", "pdf"],
            accept_multiple_files=True,
            key=f"up_pieces_jointes_widget_{version}",
        )

        if fichiers_joints:
            st.markdown("---")
            st.markdown("##### 👁️ Aperçu des pièces jointes :")
            for file in fichiers_joints:
                with st.expander(f"📄 {file.name} ({file.size // 1024} KB)"):
                    if file.type.startswith("image/"):
                        st.image(file, use_container_width=True)
                    elif file.type == "application/pdf":
                        try:
                            bytes_data = file.getvalue()
                            base64_pdf = base64.b64encode(bytes_data).decode("utf-8")
                            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500" type="application/pdf"></iframe>'
                            st.markdown(pdf_display, unsafe_allow_html=True)
                        except Exception as err_pdf:
                            st.warning(f"Impossible d'afficher l'aperçu PDF : {err_pdf}")

    # ── ONGLET 6 : Numéro facture ──
    with tab_facture:
        st.subheader("🧾 Facturation & Imputation")
        col_fac1, col_fac2 = st.columns(2)
        with col_fac1:
            num_facture = st.text_input("N° de Facture", placeholder="EX: FAC-2026-0012", key=f"input_num_facture_widget_{version}")
        with col_fac2:
            motif_facture = st.text_area("Remarques / Motif de facturation", key=f"txt_fac_obs_widget_{version}")

    # ── 🟢 BOUTON ENREGISTRER GLOBAL (HORS DES ONGLETS) ──
    st.divider()

    if st.button('💾 Enregistrer le contrôle', key='save_btn_global', type='primary', use_container_width=True):
        # 1. Récupération hybride des champs
        controleur_val = str(
            st.session_state.get('controleur_final', controleur if 'controleur' in locals() else '')).strip()
        chaine_val = str(st.session_state.get('ctrl_chaine_widget', chaine if 'chaine' in locals() else '')).strip()

        key_of_dyn = f'ctrl_of_{auto_of}_{version}' if 'auto_of' in locals() else None
        of_champ_val = str(st.session_state.get(key_of_dyn, of_val if 'of_val' in locals() else '') if key_of_dyn else (
            of_val if 'of_val' in locals() else '')).strip()

        key_ref_dyn = f'ctrl_ref_manual_widget_{auto_reference}_{version}' if 'auto_reference' in locals() else None
        reference_val = str(
            st.session_state.get(key_ref_dyn, reference if 'reference' in locals() else '') if key_ref_dyn else (
                reference if 'reference' in locals() else '')).strip()

        num_facture_val = str(st.session_state.get(f'input_num_facture_widget_{version}', '')).strip()
        motif_facture_val = str(st.session_state.get(f'txt_fac_obs_widget_{version}', '')).strip()
        fichiers_pj = st.session_state.get(f'up_pieces_jointes_widget_{version}', [])

        # 2. Validation
        invalid_values = ['', 'None', '-- Sélectionner une chaîne --', '-- Choisir une chaîne --', 'Sélectionner...']

        erreurs = []
        if controleur_val in invalid_values:
            erreurs.append('**Contrôleur final**')
        if of_champ_val in invalid_values:
            erreurs.append('**OF**')
        if chaine_val in invalid_values:
            erreurs.append('**Chaîne**')

        if erreurs:
            st.error(f"⚠️ Veuillez remplir les champs obligatoires suivants avant d'enregistrer : {', '.join(erreurs)}")
        else:
            clean_of = "".join(c for c in of_champ_val if c.isalnum() or c in ('-', '_'))
            clean_ref = "".join(c for c in reference_val if c.isalnum() or c in ('-', '_'))
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # 3. Traitement des Photos NC (liste)
            photos_nc = st.session_state.get('photos_nc', [])
            photos_traitees = []  # liste de dicts {nom, chemin, bytes}

            for idx, raw in enumerate(photos_nc, start=1):
                nom_photo = f'{clean_of}_{clean_ref}_{timestamp}_{idx}.jpg'
                chemin_photo = os.path.join(PHOTO_DIR, nom_photo)
                try:
                    img = Image.open(io.BytesIO(raw)).convert('RGB')
                    img.thumbnail((1280, 1280))
                    img.save(chemin_photo, format='JPEG', quality=85)

                    # Octets compressés (plus légers pour la BDD)
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG', quality=85)

                    photos_traitees.append({
                        'nom': nom_photo,
                        'chemin': chemin_photo,
                        'bytes': buf.getvalue(),
                    })
                except Exception as e:
                    st.error(f'❌ Erreur sauvegarde photo {idx} : {e}')

            # Compatibilité avec la colonne existante (1ère photo uniquement)
            photo_bytes = photos_traitees[0]['bytes'] if photos_traitees else None
            nom_photo_genere = photos_traitees[0]['nom'] if photos_traitees else None

            # 4. Dictionnaire pour la BDD principale
            data_to_save = {
                'date_controle': st.session_state.get('ctrl_date_widget', date.today()),
                'chaine': chaine_val,
                'client': st.session_state.get(
                    f'ctrl_client_{auto_client}_{version}' if 'auto_client' in locals() else '',
                    client if 'client' in locals() else ''),
                'controleur_final': controleur_val,
                'of': of_champ_val,
                'article': st.session_state.get(
                    f'ctrl_art_{auto_article}_{version}' if 'auto_article' in locals() else '',
                    article if 'article' in locals() else ''),
                'reference': reference_val,
                'norme': st.session_state.get(f'ctrl_norme_{auto_norme}_{version}' if 'auto_norme' in locals() else '',
                                              norme if 'norme' in locals() else ''),
                'coloris': st.session_state.get(
                    f'ctrl_col_{auto_coloris}_{version}' if 'auto_coloris' in locals() else '',
                    coloris if 'coloris' in locals() else ''),
                'qte_of': st.session_state.get(
                    f'ctrl_qteof_{auto_qte_of}_{version}' if 'auto_qte_of' in locals() else '',
                    qte_of if 'qte_of' in locals() else 0),
                'qte_presentee': st.session_state.get('ctrl_qtepres_widget',
                                                      qte_presentee if 'qte_presentee' in locals() else 0),
                'cartons_presentes': str(st.session_state.get('ctrl_cartons_pres_widget', '')),
                'carton_controle': str(st.session_state.get('carton_controle_val', '')),
                'numero_palette': st.session_state.get('ctrl_palette_widget',
                                                       num_palette if 'num_palette' in locals() else ''),
                'qte_controlee': st.session_state.get('ctrl_qtectrl_widget',
                                                      qte_controlee if 'qte_controlee' in locals() else 0),
                'pourcentage_controle': pct_controle if 'pct_controle' in locals() else 0.0,
                'total_defaut': st.session_state.get('ctrl_tot_def', total_defaut if 'total_defaut' in locals() else 0),
                'pourcentage_defaut': st.session_state.get('ctrl_pct_def',
                                                           pct_defaut if 'pct_defaut' in locals() else 0.0),
                'defaut_majeur': st.session_state.get('maj_counter', 0),
                'defaut_mineur': st.session_state.get('min_counter', 0),
                'defaut_securitaire': st.session_state.get('sec_counter', 0),
                'description_nc': st.session_state.get('description_nc1_val', ''),
                'description_nc1': st.session_state.get('description_nc2_val', ''),
                'decision': decision_finale if 'decision_finale' in locals() else 'Accepté',
                'quantite_triee': st.session_state.get('tri_qte_widget', 0),
                'total_defaut_tri': st.session_state.get('tri_tot_widget', 0),
                'nb_defauts_tri': st.session_state.get('tri_nb_widget', 0),
                'pourcentage_defaut_tri': pct_defaut_tri if 'pct_defaut_tri' in locals() else 0.0,
                'numero_qc': st.session_state.get('tri_qc_widget', ''),
                'temps_tri_mn': st.session_state.get('time_widget', 0.0),
                'cout_mn': st.session_state.get('cost_widget', 0.0),
                'cout_tri': cout_tri_auto if 'cout_tri_auto' in locals() else 0.0,
                'nom_photo': nom_photo_genere,  # 1ère photo
                'numero_facture': num_facture_val,
                'motif_facture': motif_facture_val,
                'photo_nc': photo_bytes,  # 1ère photo (octets)
            }

            try:
                # Insertion dans la BDD principale
                db.insert_record(data_to_save)

                nb_pj_ok = 0

                # A. Toutes les photos NC
                for p in photos_traitees:
                    if hasattr(db, 'insert_photo_record'):
                        db.insert_photo_record({
                            'of_val': of_champ_val,
                            'reference': reference_val,
                            'nom_fichier': p['nom'],
                            'chemin_fichier': p['chemin'],
                            'photo_bytes': p['bytes'],
                        })

                    if hasattr(db, 'insert_piece_jointe_record'):
                        db.insert_piece_jointe_record({
                            'of_val': of_champ_val,
                            'reference': reference_val,
                            'nom_fichier': p['nom'],
                            'chemin_fichier': p['chemin'],
                            'fichier_data': p['bytes'],
                            'type_mime': 'image/jpeg'
                        })

                # B. Documents joints
                if fichiers_pj:
                    for f in fichiers_pj:
                        nom_orig, ext = os.path.splitext(f.name)
                        nom_pj_clean = "".join(c for c in nom_orig if c.isalnum() or c in ('-', '_'))
                        nouveau_nom_pj = f"{clean_of}_{clean_ref}_{timestamp}_{nom_pj_clean}{ext}"
                        chemin_pj = os.path.join(PIECES_JOINTE_DIR, nouveau_nom_pj)

                        f_bytes = f.getvalue()
                        with open(chemin_pj, "wb") as out_f:
                            out_f.write(f_bytes)

                        if hasattr(db, 'insert_piece_jointe_record'):
                            db.insert_piece_jointe_record({
                                'of_val': of_champ_val,
                                'reference': reference_val,
                                'nom_fichier': nouveau_nom_pj,
                                'chemin_fichier': chemin_pj,
                                'fichier_data': f_bytes,
                                'type_mime': f.type or 'application/octet-stream'
                            })
                            nb_pj_ok += 1

                msg_photos = f" | 📷 {len(photos_traitees)} photo(s)" if photos_traitees else ""
                msg_pj = f" | 📎 {nb_pj_ok} pièce(s) jointe(s)" if nb_pj_ok > 0 else ""
                st.success(f'✅ Contrôle enregistré avec succès en base de données !{msg_photos}{msg_pj}')
                time.sleep(1.5)

                # Reset global et rechargement
                reinitialiser_formulaire()
                st.rerun()

            except Exception as e:
                st.error(f"❌ Erreur lors de l'enregistrement BDD : {e}")

