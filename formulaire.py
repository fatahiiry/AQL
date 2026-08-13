from datetime import date
import re
import time
import io
import os
import database as db
from database import get_connection
import pandas as pd
from PIL import Image
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
import streamlit as st
import business as biz
from datetime import datetime

def actualiser_echantillon():
  qte_pres = st.session_state.get('ctrl_qtepres_widget', 0)

  # 1. On dépaquète dans maj_tolere et min_tolere
  qte_ctrl, maj_tolere, min_tolere = db.get_norme_values(qte_pres)

  # 2. On met à jour les clés dans st.session_state avec les bonnes variables
  st.session_state['ctrl_qtectrl_widget'] = qte_ctrl
  st.session_state['limite_maj_max'] = maj_tolere
  st.session_state['limite_min_max'] = min_tolere
  st.session_state['widget_maj'] = maj_tolere
  st.session_state['widget_min'] = min_tolere


def render_formulaire():
  tab_ident, tab_defauts, tab_traitement, tab_sur_mesure = st.tabs([
      '📋 1. Identification & Volumes',
      '⚠️ 2. Compteurs de Défauts',
      '🔄 3. Décision & Résultats du Tri',
      '📏 4. Tableau de Mesure',
  ])
  #  ONGLET 1 : Identification & Volumes
  with tab_ident:
    st.markdown(
        '<div class="section-header">🔍 Recherche et sélection de'
        " l'OF</div>",
        unsafe_allow_html=True,
    )
    of_search_input = st.text_input(
        "Saisissez le N° d'OF à rechercher...",
        value='',
        placeholder='Ex: 958...',
    )

    suggestions = db.search_of_suggestions(of_search_input)
    selected_row = None

    if suggestions:
      chosen_of = st.selectbox(
          "Résultat(s) trouvé(s) - Choisissez l'OF exact :",
          options=suggestions,
          key='of_exact_select',
      )
      records_df = db.get_of_records(chosen_of)

      if not records_df.empty:
        if len(records_df) > 1:
          options_labels = [
              f"Ligne {i + 1} : Article: {r['article']} | Coloris: {r['coloris']}"
              f" | Qté Réf (Excel cde_mere): {r['cde_mere']}"
              for i, r in records_df.iterrows()
          ]
          chosen_index = st.selectbox(
              '⚠️ Plusieurs déclinaisons trouvées pour cet OF. Sélectionnez la'
              ' bonne ligne :',
              options=range(len(options_labels)),
              format_func=lambda x: options_labels[x],
              key='declinaison_select',
          )
          selected_row = records_df.iloc[chosen_index]
        else:
          selected_row = records_df.iloc[0]
    else:
      if len(of_search_input) >= 1:
        st.warning('⚠️ Aucun OF correspondant trouvé dans la table.')
      else:
        st.info(
            '💡 Saisissez le numéro d\'OF pour activer la recherche'
            ' automatique.'
        )

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

    st.markdown(
        '<div class="section-header">📋 Formulaire d\'identification du'
        ' lot</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
      date_controle = st.date_input(
          '📅 Date *', value=date.today(), key='ctrl_date_widget'
      )
      liste_chaines_db = db.fetch_db_chaines()
      chaine = st.selectbox(
          'Chaîne *', options=liste_chaines_db, key='ctrl_chaine_widget'
      )
      client = st.text_input(
          'Client *', value=auto_client, key=f'ctrl_client_{auto_client}'
      )
    with c2:
      controleur = st.text_input('Contrôleur final *', key='controleur_final')
      of_val = st.text_input(
          'OF *',
          value=auto_of,
          disabled=(selected_row is not None),
          key=f'ctrl_of_{auto_of}',
      )
      article = st.text_input(
          'Article *', value=auto_article, key=f'ctrl_art_{auto_article}'
      )
    with c3:
      reference = st.text_input(
          'Référence',
          value=auto_reference,
          key=f'ctrl_ref_manual_widget_{auto_reference}',
      )
      norme = st.text_input(
          'Norme', value=auto_norme, key=f'ctrl_norme_{auto_norme}'
      )
      coloris = st.text_input(
          'Coloris', value=auto_coloris, key=f'ctrl_col_{auto_coloris}'
      )

    # 📌 Quantités, Cartons et Échantillonnage
    st.markdown(
        '<div class="section-header">📦 Quantités et Échantillonnage</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    with c1:
      qte_of = st.number_input(
          'Cde mere',
          min_value=0,
          step=1,
          value=auto_qte_of,
          key=f'ctrl_qteof_{auto_qte_of}',
      )

    with c2:
      # 📌 CHAMP "Qté présentée" (déclenche le callback au changement)
      qte_presentee = st.number_input(
          'Qté présentée *',
          min_value=0,
          step=1,
          key='ctrl_qtepres_widget',
          on_change=actualiser_echantillon,
      )

    with c3:
      # 📌 CHAMP "Cartons présentés" (Format texte ex: 12-13-34)
      cartons_presentes = st.text_input(
          '📦 Cartons présentés',
          placeholder='Ex: 12-13-34',
          key='ctrl_cartons_pres_widget',
      )

    with c4:
      num_palette = st.text_input('N° Palette', key='ctrl_palette_widget')

    # Extraction propre des numéros de cartons saisis (séparateurs acceptés : -, ,, space)
    liste_cartons = [
        c.strip() for c in re.split(r'[-,;\s]+', cartons_presentes) if c.strip()
    ]

    c_ctrl_qte, c_ctrl_cartons = st.columns(2)

    with c_ctrl_qte:
      # 📌 CHAMP "Qté contrôlée" (mis à jour par le callback)
      qte_controlee = st.number_input(
          'Qté contrôlée *',
          min_value=0,
          step=1,
          key='ctrl_qtectrl_widget',
      )

    with c_ctrl_cartons:
      # 📌 NOUVEAU CHAMP : "N° cartons contrôlés"
      if liste_cartons:
        cartons_controles_list = st.multiselect(
            '🔎 N° cartons contrôlés',
            options=liste_cartons,
            help='Sélectionnez les cartons contrôlés parmi ceux présentés',
            key='ctrl_cartons_ctrl_select',
        )
        cartons_controles = ' - '.join(cartons_controles_list)
      else:
        cartons_controles = st.text_input(
            '🔎 N° cartons contrôlés',
            placeholder="Renseignez d'abord 'Cartons présentés'",
            key='ctrl_cartons_ctrl_input',
        )

    # Enregistrement de la valeur finale dans le session_state pour la BDD
    st.session_state['carton_controle_val'] = cartons_controles

    pct_controle = (
        (int(qte_controlee) / int(qte_presentee) * 100)
        if qte_presentee > 0
        else 0.0
    )
    pct_ctrl_class = (
        'danger'
        if pct_controle < 10
        else ('warning' if pct_controle < 50 else 'value')
    )

    st.markdown(
        f"""
            <div class="calc-box">
                <div class="label">📊 % Contrôlé = Qté contrôlée / Qté présentée (Instantané)</div>
                <div class="value {pct_ctrl_class}">{pct_controle:.2f} %</div>
            </div>""",
        unsafe_allow_html=True,
    )

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
                            <div style="font-size: 0.85em; color: #2d6a9f; background: #eef5fc; padding: 3px 8px; border-radius: 4px; font-weight: 500;">
                                ➕ {decompte}
                            </div>
                        </div>
                        <div class="value {cumul_class}" style="margin-top: 5px;">{pct_cumul_val:.2f} %</div>
                    </div>""",
              unsafe_allow_html=True,
          )
      except Exception as e:
        st.error(f'❌ Erreur lors du calcul automatique : {e}')

  # Chemin du dossier d'enregistrement local des photos
  PHOTO_DIR = r'C:\Users\developpeur1\Desktop\A suppr\CONTROLE\photos'
  os.makedirs(PHOTO_DIR, exist_ok=True)

  #  ONGLET 2 : Compteurs de Défauts & Photo
  with tab_defauts:
      st.markdown(
          '<div class="section-header">🛠️ Saisie Tactile des Défauts</div>',
          unsafe_allow_html=True,
      )

      limite_maj = st.session_state.get('limite_maj_max', 0)
      limite_min = st.session_state.get('limite_min_max', 0)

      col_maj, col_min, col_sec = st.columns(3)

      # DÉFAUTS MAJEURS
      with col_maj:
          st.write(f'**Défauts Majeurs** *(Max toléré : {limite_maj})*')
          sub_c1, sub_c2 = st.columns(2)
          sub_c1.button('➕ Ajouter Majeur', key='add_maj', on_click=biz.inc_majeur)
          sub_c2.button('➖ Retirer Majeur', key='rem_maj', on_click=biz.dec_majeur)

          defaut_majeur = st.number_input(
              'Valeur enregistrée', min_value=0, step=1, key='widget_maj'
          )
          if defaut_majeur > limite_maj and limite_maj > 0:
              st.error(f'⚠️ Seuil dépassé ! ({defaut_majeur} > {limite_maj} max)')

      # DÉFAUTS MINEURS
      with col_min:
          st.write(f'**Défauts Mineurs** *(Max toléré : {limite_min})*')
          sub_c1, sub_c2 = st.columns(2)
          sub_c1.button('➕ Ajouter Mineur', key='add_min', on_click=biz.inc_mineur)
          sub_c2.button('➖ Retirer Mineur', key='rem_min', on_click=biz.dec_mineur)

          defaut_mineur = st.number_input(
              'Valeur enregistrée', min_value=0, step=1, key='widget_min'
          )
          if defaut_mineur > limite_min and limite_min > 0:
              st.warning(f'⚠️ Seuil dépassé ! ({defaut_mineur} > {limite_min} max)')

      # DÉFAUTS SÉCURITAIRES
      with col_sec:
          st.write('**Défauts Sécuritaires** *(Max : 0)*')
          sub_c1, sub_c2 = st.columns(2)
          sub_c1.button('➕ Ajouter Sécu', key='add_sec', on_click=biz.inc_secu)
          sub_c2.button('➖ Retirer Sécu', key='rem_sec', on_click=biz.dec_secu)

          defaut_securitaire = st.number_input(
              'Valeur enregistrée',
              min_value=0,
              step=1,
              key='widget_sec',
          )
          if defaut_securitaire > 0:
              st.error('🚨 Défaut critique/sécuritaire présent !')

      st.markdown('---')
      total_defaut = defaut_majeur + defaut_mineur + defaut_securitaire
      st.session_state['widget_total_defauts'] = total_defaut

      st.markdown(
          f"""
        <div class="calc-box">
            <div class="label">🚨 Total Défauts Saisis</div>
            <div class="value">{total_defaut}</div>
        </div>""",
          unsafe_allow_html=True,
      )

      st.markdown('---')

      # ── Disposition en 2 Colonnes Rééquilibrée ──
      col_nc_left, col_photo_right = st.columns([1, 1], gap='medium')

      with col_nc_left:
          st.markdown('##### 📝 Non-Conformité 1 (NC 1)')

          raw_data_nc1 = db.fetch_db_typologie_defauts() or []
          liste_defauts_raw1 = [
              str(item[0]).strip()
              if isinstance(item, (tuple, list))
              else str(item).strip()
              for item in raw_data_nc1
              if item
          ]

          options_tab2 = [
                             '-- Sélectionner un défaut --',
                             '➕ Autre (saisie libre)',
                         ] + liste_defauts_raw1

          defaut_choisi_nc1 = st.selectbox(
              'Sélection du défaut NC 1',
              options=options_tab2,
              index=0,
              placeholder='🔎 Tapez une lettre pour rechercher un défaut...',
              help="Tapez directement le nom d'un défaut pour filtrer la liste.",
              key='nc1_select',
          )

          # Précisions ou Saisie libre
          if defaut_choisi_nc1 == '➕ Autre (saisie libre)':
              description_nc1 = st.text_area(
                  '📝 Préciser le défaut (Saisie libre) *',
                  height=180,
                  placeholder=(
                      'Détaillez précisément les non-conformités observées...'
                  ),
                  key='nc1_area_custom',
              ).strip()
          else:
              description_nc1 = (
                  str(defaut_choisi_nc1).strip()
                  if defaut_choisi_nc1 != '-- Sélectionner un défaut --'
                  else ''
              )

              remarques_nc1 = st.text_area(
                  '💬 Remarques & Observations (Optionnel)',
                  height=180,
                  placeholder=(
                      'Précisions sur la localisation du défaut, la gravité, etc.'
                  ),
                  key='nc1_remarques_input',
              )
              if remarques_nc1.strip() and description_nc1:
                  description_nc1 += f' | Remarques: {remarques_nc1.strip()}'

          st.session_state['description_nc1_val'] = description_nc1

      with col_photo_right:
          st.markdown('##### 📸 Photo de la NC 1 (Optionnel)')

          photo_nc_file = st.camera_input(
              'Prendre une photo du défaut', key='camera_nc1_input'
          )

          if photo_nc_file is not None:
              st.session_state['photo_nc_bytes'] = photo_nc_file.getvalue()
              st.success('📷 Photo conservée !')

      st.markdown('---')

      qte_controlee = st.session_state.get('ctrl_qtectrl_widget', 0)
      pct_defaut = (
          (int(total_defaut) / int(qte_controlee) * 100)
          if qte_controlee > 0
          else 0.0
      )
      pct_def_class = (
          'danger'
          if pct_defaut >= 5
          else ('warning' if pct_defaut >= 2 else 'value')
      )

      st.markdown(
          f"""
        <div class="calc-box">
            <div class="label">📊 % Défaut = Total défaut / Qté contrôlée (Instantané)</div>
            <div class="value {pct_def_class}">{pct_defaut:.2f} %</div>
        </div>""",
          unsafe_allow_html=True,
      )

      st.button(
          '🔄 Réinitialiser tous les compteurs à 0', on_click=biz.reset_compteurs
      )

  # ==============================================================================
  #  ONGLET 3 : Décision & Résultats du Tri
  # ==============================================================================
  with tab_traitement:
      st.markdown(
          '<div class="section-header">⚖️ Conclusion & Décision</div>',
          unsafe_allow_html=True,
      )
      c1, c2 = st.columns(2)

      with c1:
          st.info(
              "💡 La **Description NC 1** et la **Photo** sont renseignées dans"
              " l'onglet Compteurs de Défauts."
          )

      with c2:
          depassement_majeur = (limite_maj > 0) and (defaut_majeur > limite_maj)
          depassement_mineur = (limite_min > 0) and (defaut_mineur > limite_min)
          presence_securitaire = defaut_securitaire > 0

          if depassement_majeur or depassement_mineur or presence_securitaire:
              decision_initiale = 'Refusé'
              badge_color = '#dc2626'
              badge_icon = '❌'
          else:
              decision_initiale = 'Accepté'
              badge_color = '#16a34a'
              badge_icon = '✅'

          decision_finale = decision_initiale

          st.markdown(
              f"""
            <div style="background-color: #f8fafc; border: 2px solid {badge_color}; border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 10px;">
                <span style="font-size: 0.85em; color: #475569; font-weight: bold;">⚖️ DÉCISION AUTOMATIQUE AQL</span><br/>
                <span style="font-size: 1.3em; color: {badge_color}; font-weight: bold;">{badge_icon} {decision_initiale}</span>
            </div>
            """,
              unsafe_allow_html=True,
          )
          if decision_initiale == 'Refusé':
              st.warning('⚠️ Le lot a été automatiquement calculé comme **Refusé**.')

              appliquer_derogation = st.checkbox(
                  '🙋 Appliquer une dérogation ?', key='chk_derogation'
              )

              if appliquer_derogation:
                  decision_finale = st.selectbox(
                      '📌 Nouvelle décision suite à dérogation :',
                      [
                          'Accepté sous dérogation',
                          'Dérogation client',
                          'Refusé',
                      ],
                      key='derogation_select',
                  )

      st.markdown(
          '<div class="section-header">🔄 Résultats & Coûts du tri</div>',
          unsafe_allow_html=True,
      )
      c1, c2, c3, c4 = st.columns(4)
      with c1:
          quantite_triee = st.number_input(
              'Quantité triée', min_value=0, step=1, value=0, key='tri_qte_widget'
          )
      with c2:
          total_defaut_tri = st.number_input(
              'Total défauts au tri', min_value=0, step=1, value=0, key='tri_tot_widget'
          )
      with c3:
          nb_defauts_tri = st.number_input(
              'Nb défauts au tri', min_value=0, step=1, value=0, key='tri_nb_widget'
          )
      with c4:
          numero_qc = st.text_input('N° QC', key='tri_qc_widget')

      # ── Récupération et sélection directe NC 2 ──
      st.markdown('##### 📝 Description Non-Conformité 2 (Tri)')

      raw_data_nc2 = db.fetch_db_typologie_defauts() or []
      liste_defauts_raw2 = [
          str(item[0]).strip()
          if isinstance(item, (tuple, list))
          else str(item).strip()
          for item in raw_data_nc2
          if item
      ]

      options_tab3 = [
                         '-- Sélectionner un défaut --',
                         '➕ Autre (saisie libre)',
                     ] + liste_defauts_raw2

      defaut_choisi_nc2 = st.selectbox(
          '📝 Description NC 2 (Tri)',
          options=options_tab3,
          index=0,
          placeholder='🔎 Tapez une lettre pour rechercher le second défaut...',
          help="Tapez directement le nom d'un défaut pour filtrer la liste.",
          key='nc2_select',
      )

      description_nc2_val = ''
      if defaut_choisi_nc2 == '➕ Autre (saisie libre)':
          description_nc2_val = st.text_area(
              '📝 Préciser la description NC 2 (Saisie libre)',
              height=90,
              placeholder='Deuxième description liée aux opérations de tri...',
              key='nc2_area_custom',
          ).strip()
      elif (
              defaut_choisi_nc2
              and str(defaut_choisi_nc2) != '-- Sélectionner un défaut --'
      ):
          description_nc2_val = str(defaut_choisi_nc2).strip()

      st.session_state['description_nc2_val'] = description_nc2_val

      pct_defaut_tri = (
          (float(total_defaut_tri) / float(quantite_triee) * 100.0)
          if quantite_triee > 0
          else 0.0
      )
      pct_tri_class = (
          'danger'
          if pct_defaut_tri >= 5
          else ('warning' if pct_defaut_tri >= 2 else 'value')
      )

      st.markdown(
          f"""
        <div class="calc-box">
            <div class="label">📊 % Défaut au tri = Total défauts tri / Quantité triée (Automatique)</div>
            <div class="value {pct_tri_class}">{pct_defaut_tri:.2f} %</div>
        </div>""",
          unsafe_allow_html=True,
      )

      st.markdown(
          '<div class="section-header">💰 Évaluation financière</div>',
          unsafe_allow_html=True,
      )
      cc1, cc2 = st.columns(2)
      with cc1:
          temps_tri = st.number_input(
              'Temps de tri (mn)',
              min_value=0.0,
              step=0.5,
              format='%.1f',
              value=0.0,
              key='time_widget',
          )
      with cc2:
          cout_mn = st.number_input(
              'Coût / mn ($)',
              min_value=0.0,
              step=0.01,
              format='%.2f',
              value=0.0,
              key='cost_widget',
          )

      cout_tri_auto = round(float(temps_tri * cout_mn), 2)

      st.markdown(
          f"""
        <div class="calc-box" style="margin-top: 10px; margin-bottom: 25px;">
            <div class="label">💰 Coût total du Tri Calculé (Temps × Coût/mn)</div>
            <div class="value" style="color: #2d6a9f;">{cout_tri_auto:.2f} $</div>
        </div>""",
          unsafe_allow_html=True,
      )

      st.divider()

      if st.button('💾 Enregistrer le contrôle', key='save_btn'):
          # ── 1. Validation des champs obligatoires ──
          controleur_val = str(controleur).strip() if controleur else ''
          of_champ_val = str(of_val).strip() if of_val else ''
          chaine_val = str(chaine).strip() if chaine else ''

          invalid_values = [
              '',
              'None',
              '-- Sélectionner une chaîne --',
              '-- Choisir une chaîne --',
              'Sélectionner...',
          ]

          erreurs = []
          if controleur_val in invalid_values:
              erreurs.append('**Contrôleur final**')
          if of_champ_val in invalid_values:
              erreurs.append('**OF**')
          if chaine_val in invalid_values:
              erreurs.append('**Chaîne**')

          if erreurs:
              st.error(
                  '⚠️ Veuillez remplir les champs obligatoires suivants avant'
                  f" d'enregistrer : {', '.join(erreurs)}"
              )
          else:
              # ── 2. Sauvegarde de la photo sur disque local ──
              photo_bytes = st.session_state.get('photo_nc_bytes', None)
              nom_photo_genere = None
              chemin_complet_photo = None

              if photo_bytes is not None:
                  clean_of = "".join(
                      c for c in str(of_champ_val) if c.isalnum() or c in ('-', '_')
                  )
                  clean_ref = "".join(
                      c for c in str(reference) if c.isalnum() or c in ('-', '_')
                  )
                  timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

                  nom_photo_genere = f'{clean_of}_{clean_ref}_{timestamp}.jpg'
                  chemin_complet_photo = os.path.join(PHOTO_DIR, nom_photo_genere)

                  try:
                      img = Image.open(io.BytesIO(photo_bytes))
                      img.thumbnail((1280, 1280))
                      img.save(chemin_complet_photo, format='JPEG', quality=85)
                  except Exception as e:
                      st.error(
                          f"❌ Erreur lors de la sauvegarde de l'image sur disque : {e}"
                      )

              # ── 3. Données pour la table principale ──
              desc_nc1_finale = st.session_state.get(
                  'description_nc1_val',
                  description_nc1 if 'description_nc1' in locals() else '',
              )

              data_to_save = {
                  'date_controle': date_controle,
                  'chaine': chaine_val,
                  'client': client,
                  'controleur_final': controleur_val,
                  'of': of_champ_val,
                  'article': article,
                  'reference': reference,
                  'norme': norme,
                  'coloris': coloris,
                  'qte_of': qte_of,
                  'qte_presentee': qte_presentee,
                  'cartons_presentes': st.session_state.get(
                      'ctrl_cartons_pres_widget', ''
                  ),
                  'carton_controle': st.session_state.get('carton_controle_val', ''),
                  'numero_palette': num_palette,
                  'qte_controlee': qte_controlee,
                  'pourcentage_controle': pct_controle,
                  'total_defaut': total_defaut,
                  'pourcentage_defaut': pct_defaut,
                  'defaut_majeur': defaut_majeur,
                  'defaut_mineur': defaut_mineur,
                  'defaut_securitaire': defaut_securitaire,
                  'description_nc': desc_nc1_finale,
                  'description_nc1': description_nc2_val,
                  'decision': decision_finale,
                  'quantite_triee': quantite_triee,
                  'total_defaut_tri': total_defaut_tri,
                  'nb_defauts_tri': nb_defauts_tri,
                  'pourcentage_defaut_tri': pct_defaut_tri,
                  'numero_qc': numero_qc,
                  'temps_tri_mn': temps_tri,
                  'cout_mn': cout_mn,
                  'cout_tri': cout_tri_auto,
                  'nom_photo': nom_photo_genere,
              }

              # ── 4. Données pour la table dédiée QualiteDB.dbo.controle_photos ──
              data_photo_to_save = {
                  'of_val': of_champ_val,
                  'reference': reference,
                  'nom_fichier': nom_photo_genere,
                  'chemin_fichier': chemin_complet_photo,
                  'photo_bytes': photo_bytes,
              }

              try:
                  # Enregistrement table principale
                  db.insert_record(data_to_save)

                  # Enregistrement table dédiée photos
                  if hasattr(db, 'insert_photo_record') and nom_photo_genere:
                      db.insert_photo_record(data_photo_to_save)

                  st.session_state.pop('photo_nc_bytes', None)

                  msg_photo = (
                      f' | 📸 Photo sauvegardée : `{nom_photo_genere}`'
                      if nom_photo_genere
                      else ''
                  )
                  st.success(f'✅ Contrôle enregistré avec succès !{msg_photo}')
                  time.sleep(1)
                  st.rerun()

              except Exception as e:
                  st.error(f"❌ Erreur lors de l'enregistrement BDD : {e}")

  #  ONGLET 4 : Tableau de Mesure
  with tab_sur_mesure:
        st.markdown(
            '<div class="section-header">📏 Grille de Contrôle Sur-Mesure</div>',
            unsafe_allow_html=True,
        )

        # ── 1. Récupération EXACTE des clés de l'Onglet 1 ──────────────────────
        ref_val = auto_reference if 'auto_reference' in locals() else ''
        coloris_base = auto_coloris if 'auto_coloris' in locals() else ''
        of_base = auto_of if 'auto_of' in locals() else ''

        of_val = st.session_state.get(f'ctrl_of_{of_base}', of_base)
        ref_val = st.session_state.get(f'ctrl_ref_manual_widget_{ref_val}', ref_val)
        chaine_val = st.session_state.get('ctrl_chaine_widget', '')
        date_val = st.session_state.get('ctrl_date_widget', date.today())
        coloris_val = st.session_state.get(f'ctrl_col_{coloris_base}', coloris_base)
        ctrl_val = st.session_state.get('controleur_final', '')
        ctrl_final_nom = (
            str(ctrl_val).strip()
            if ctrl_val and str(ctrl_val).strip()
            else 'Non renseigné'
        )
        qte_val = st.session_state.get('ctrl_qtectrl_widget', 0)

        if ref_val:
            date_str = (
                date_val.strftime('%d/%m/%Y')
                if hasattr(date_val, 'strftime')
                else str(date_val)
            )

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

            conn = db.get_connection()
            query = """
                   SELECT point_de_mesure, tolerance, taille, valeur_cible
                   FROM mesures_modele
                   WHERE LOWER(TRIM(nom_modele)) = LOWER(TRIM(?))
                   ORDER BY id ASC
               """
            df_raw = pd.read_sql(query, conn, params=[str(ref_val).strip()])

            if not df_raw.empty:
                tailles_dispo = sorted(df_raw['taille'].astype(str).unique().tolist())

                if 'sauvegarde_mesures' not in st.session_state:
                    st.session_state['sauvegarde_mesures'] = {}

                taille_choisie = st.selectbox(
                    '🎯 Choisissez la Taille à contrôler :',
                    options=tailles_dispo,
                    key=f'select_taille_{ref_val}',
                )

                # Préparation du DataFrame de base
                if taille_choisie in st.session_state['sauvegarde_mesures']:
                    df_saisie = pd.DataFrame(
                        st.session_state['sauvegarde_mesures'][taille_choisie]
                    )
                else:
                    df_taille = df_raw[
                        df_raw['taille'].astype(str) == str(taille_choisie)
                        ].copy()
                    df_saisie = pd.DataFrame({
                        'POINTS DE MESURE': df_taille['point_de_mesure'],
                        'TOL (+/-)': df_taille['tolerance'],
                        'CIBLE (cm)': df_taille['valeur_cible'],
                        'Pièce 1': [''] * len(df_taille),
                        'Pièce 2': [''] * len(df_taille),
                        'Pièce 3': [''] * len(df_taille),
                        'Pièce 4': [''] * len(df_taille),
                    })

                # ── 📌 INSCRIPTION DE LA RÈGLE JS DE COLORATION DANS AGGRID ───────
                cell_style_jscode = JsCode("""
                  function(params) {
                      if (params.value !== null && params.value !== undefined && params.value !== "") {
                          let val = parseFloat(String(params.value).replace(',', '.'));
                          let cible = parseFloat(params.data['CIBLE (cm)']);
                          let tol = parseFloat(params.data['TOL (+/-)']);

                          if (!isNaN(val) && !isNaN(cible) && !isNaN(tol)) {
                              if (val < (cible - tol) || val > (cible + tol)) {
                                  return {
                                      'color': '#dc2626',
                                      'backgroundColor': '#fee2e2',
                                      'fontWeight': 'bold'
                                  };
                              }
                          }
                      }
                      return null;
                  };
                  """)

                gb = GridOptionsBuilder.from_dataframe(df_saisie)
                gb.configure_columns(
                    ['POINTS DE MESURE', 'TOL (+/-)', 'CIBLE (cm)'],
                    editable=False,
                )
                gb.configure_columns(
                    ['Pièce 1', 'Pièce 2', 'Pièce 3', 'Pièce 4'],
                    editable=True,
                    cellStyle=cell_style_jscode,
                )

                grid_options = gb.build()

                # ── 📌 TABLEAU UNIQUE D'ÉDITION AVEC COLORATION DIRECTE ───────────
                grid_response = AgGrid(
                    df_saisie,
                    gridOptions=grid_options,
                    allow_unsafe_jscode=True,
                    theme='streamlit',
                    height=350,
                    fit_columns_on_grid_load=True,
                    key=f'grid_{ref_val}_{taille_choisie}',
                )

                # Récupération immédiate des données éditées par l'utilisateur
                df_actuel = pd.DataFrame(grid_response['data'])
                st.session_state['sauvegarde_mesures'][taille_choisie] = (
                    df_actuel.to_dict(orient='records')
                )

                # Détection et comptage des anomalies
                nb_hors_tol = 0
                cols_p = ['Pièce 1', 'Pièce 2', 'Pièce 3', 'Pièce 4']
                for col in cols_p:
                    for _, r in df_actuel.iterrows():
                        v_str = str(r[col]).replace(',', '.').strip()
                        if v_str not in ['', 'nan', 'None']:
                            try:
                                v = float(v_str)
                                c = float(r['CIBLE (cm)'])
                                t = float(r['TOL (+/-)'])
                                if v < (c - t) or v > (c + t):
                                    nb_hors_tol += 1
                            except (ValueError, TypeError):
                                pass

                if nb_hors_tol > 0:
                    st.error(
                        f'🚨 **{nb_hors_tol} mesure(s)** hors tolérance détectée(s)'
                        ' (cellule(s) rouge(s) ci-dessus) !'
                    )
                else:
                    st.success(
                        '✅ Toutes les mesures renseignées sont dans les tolérances'
                        ' autorisées.'
                    )

                st.markdown('---')

                # ── 3. Décision Exclusive (Radio) & Bouton d'enregistrement ───────
                # ── 3. Décision Exclusive (Radio) & Bouton d'enregistrement ───────
                st.markdown('##### ⚖️ Décision Globale des Mesures')
                col_dec, col_info = st.columns([2, 3])

                with col_dec:
                    decision_mesure = st.radio(
                        'Statut du contrôle sur mesure :',
                        options=['Conforme', 'Non Conforme'],
                        index=0,  # 'Conforme' sélectionné par défaut
                        horizontal=True,
                        key=f'radio_decision_mesure_{ref_val}',
                    )

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

                # Enregistrement
                if st.button('💾 Enregistrer les mesures', key=f'btn_save_mesures_{ref_val}'):
                    try:
                        mesures_data = {
                            'num_of': of_val,
                            'reference': ref_val,
                            'taille': taille_choisie,
                            'chaine': chaine_val,
                            'controleur': ctrl_final_nom,
                            'date_controle': date_val,
                            'statut_mesure': decision_mesure,
                            'details_mesures': st.session_state['sauvegarde_mesures'].get(taille_choisie, []),
                        }
                        # Appel de la fonction d'insertion en BDD
                        if hasattr(db, 'insert_mesures_record'):
                            db.insert_mesures_record(mesures_data)
                        else:
                            st.session_state[f'mesures_saved_{of_val}'] = mesures_data

                        st.success(f"✅ Mesures enregistrées avec le statut : '{decision_mesure}' !")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erreur lors de l'enregistrement des mesures : {e}")