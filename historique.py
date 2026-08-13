# historique.py

import pandas as pd
import streamlit as st

import database as db  # Assurez-vous d'avoir l'accès BDD


def render_historique():
    st.markdown(
        '<div class="section-header">📊 Historique des contrôles</div>',
        unsafe_allow_html=True,
    )

    try:
        # Chargement des enregistrements (via db.load_records)
        df_raw = db.load_records(limit=300)

        if df_raw is None or df_raw.empty:
            st.info("Aucun enregistrement trouvé dans la table controle_qualite.")
        else:
            st.markdown("##### 🔍 Filtres de recherche")
            f1, f2, f3, f4 = st.columns([2, 2, 2, 1])

            with f1:
                search_of = st.text_input(
                    "Filtrer par N° d'OF", value="", key="hist_filter_of"
                )
            with f2:
                distinct_decisions = ["Tous"] + list(
                    df_raw["decision"].dropna().unique()
                ) if "decision" in df_raw.columns else ["Tous"]
                search_decision = st.selectbox(
                    "Filtrer par Décision",
                    distinct_decisions,
                    key="hist_filter_dec",
                )
            with f3:
                distinct_chaines = ["Toutes"] + list(
                    df_raw["chaine"].dropna().unique()
                ) if "chaine" in df_raw.columns else ["Toutes"]
                search_chaine = st.selectbox(
                    "Filtrer par Chaîne",
                    distinct_chaines,
                    key="hist_filter_ch",
                )
            with f4:
                nb_lignes = st.selectbox(
                    "Lignes Max", [20, 50, 100, 200], index=1, key="hist_limit"
                )

            df_filtered = df_raw.copy()
            if search_of and "of" in df_filtered.columns:
                df_filtered = df_filtered[
                    df_filtered["of"]
                    .astype(str)
                    .str.contains(search_of, case=False, na=False)
                ]
            if search_decision != "Tous" and "decision" in df_filtered.columns:
                df_filtered = df_filtered[
                    df_filtered["decision"] == search_decision
                ]
            if search_chaine != "Toutes" and "chaine" in df_filtered.columns:
                df_filtered = df_filtered[
                    df_filtered["chaine"] == search_chaine
                ]

            df_filtered = df_filtered.head(nb_lignes)

            st.write("")
            st.markdown(
                "💡 *Cliquez sur une ligne pour afficher les détails et descriptions de non-conformité associées.*"
            )

            def color_refused(row):
                if row.get("decision") == "Refusé":
                    return ["background-color: rgba(220, 38, 38, 0.15)"] * len(
                        row
                    )
                return [""] * len(row)

            styled_df = df_filtered.style.apply(color_refused, axis=1)

            event = st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True,
                column_order=[
                    "date_controle",
                    "chaine",
                    "client",
                    "of",
                    "article",
                    "qte_presentee",
                    "qte_controlee",
                    "total_defaut",
                    "defaut_majeur",
                    "defaut_mineur",
                    "defaut_securitaire",
                    "description_nc",
                    "description_nc1",
                    "pourcentage_defaut",
                    "decision",
                    "cout_tri",
                ],
                column_config={
                    "date_controle": st.column_config.DateColumn(
                        "📅 Date", format="DD/MM/YYYY"
                    ),
                    "of": st.column_config.TextColumn("N° OF"),
                    "qte_presentee": st.column_config.NumberColumn(
                        "Qté Prés.", format="%d"
                    ),
                    "qte_controlee": st.column_config.NumberColumn(
                        "Qté Ctrl.", format="%d"
                    ),
                    "total_defaut": st.column_config.NumberColumn(
                        "Total Déf.", format="%d"
                    ),
                    "defaut_majeur": st.column_config.NumberColumn(
                        "Déf. Majeurs", format="%d"
                    ),
                    "defaut_mineur": st.column_config.NumberColumn(
                        "Déf. Mineurs", format="%d"
                    ),
                    "defaut_securitaire": st.column_config.NumberColumn(
                        "Déf. Sécu.", format="%d"
                    ),
                    "description_nc": st.column_config.TextColumn(
                        "📝 Desc. NC 1"
                    ),
                    "description_nc1": st.column_config.TextColumn(
                        "📝 Desc. NC 2"
                    ),
                    "pourcentage_defaut": st.column_config.NumberColumn(
                        "% Défaut", format="%.2f %%"
                    ),
                    "decision": st.column_config.TextColumn("⚖️ Décision"),
                    "cout_tri": st.column_config.NumberColumn(
                        "💰 Coût Tri", format="%.2f $"
                    ),
                },
                selection_mode="single-row",
                on_select="rerun",
            )

            # ── DÉTAILS DU CONTRÔLE SÉLECTIONNÉ ──
            if event and event.get("selection", {}).get("rows"):
                selected_row_idx = event["selection"]["rows"][0]
                row_data = df_filtered.iloc[selected_row_idx]

                st.markdown("---")
                st.markdown(
                    f'<div class="section-header">🔎 Détails du contrôle du {row_data.get("date_controle", "N/A")} — OF #{row_data.get("of", "N/A")}</div>',
                    unsafe_allow_html=True,
                )

                d1, d2, d3 = st.columns(3)
                with d1:
                    st.write(
                        f"**Contrôleur :** {row_data.get('controleur_final', '-')}"
                    )
                    st.write(
                        f"**Référence :** {row_data.get('reference', '-')}"
                    )
                    st.write(f"**Norme :** {row_data.get('norme', '-')}")
                with d2:
                    st.write(f"**Coloris :** {row_data.get('coloris', '-')}")
                    st.write(
                        f"**Défauts Majeurs :** {row_data.get('defaut_majeur', 0)}"
                    )
                    st.write(
                        f"**Défauts Mineurs :** {row_data.get('defaut_mineur', 0)}"
                    )
                with d3:
                    st.write(
                        f"**Défauts Sécuritaires :** {row_data.get('defaut_securitaire', 0)}"
                    )
                    st.write(f"**N° QC :** {row_data.get('numero_qc', '-')}")
                    st.write(
                        f"**Temps de tri :** {row_data.get('temps_tri_mn', 0)} mn"
                    )

                c_nc1, c_nc2 = st.columns(2)
                with c_nc1:
                    st.text_area(
                        "📝 Description Non-Conformité 1",
                        value=str(
                            row_data.get("description_nc")
                            or "Aucune description"
                        ),
                        disabled=True,
                        key="view_nc1",
                    )
                with c_nc2:
                    st.text_area(
                        "📝 Description Non-Conformité 2",
                        value=str(
                            row_data.get("description_nc1")
                            or "Aucune description"
                        ),
                        disabled=True,
                        key="view_nc2",
                    )

                # ── 📏 MESURES SUR-MESURE ASSOCIÉES ──
                selected_of = str(row_data.get("of", "")).strip()

                if selected_of:
                    try:
                        conn = db.get_connection()
                        query_sm = """
                            SELECT taille, point_de_mesure, tolerance, valeur_cible,
                                   piece_1, piece_2, piece_3, piece_4, controleur, decision
                            FROM controle_sur_mesure
                            WHERE LOWER(TRIM(of_num)) = LOWER(TRIM(?))
                            ORDER BY created_at DESC
                        """
                        df_sm = pd.read_sql(query_sm, conn, params=[selected_of])

                        st.markdown("##### 📏 Contrôle Sur-Mesure Associé")

                        if not df_sm.empty:
                            dec_sm = df_sm.iloc[0]["decision"]
                            ctrl_sm = df_sm.iloc[0]["controleur"]
                            badge_bg = (
                                "#16a34a"
                                if dec_sm == "Conforme"
                                else (
                                    "#dc2626"
                                    if dec_sm == "Non Conforme"
                                    else "#2d6a9f"
                                )
                            )

                            st.markdown(
                                f"""
                                <div style="background-color: #f8fafc; padding: 10px 14px; border-radius: 6px; border-left: 5px solid {badge_bg}; margin-bottom: 10px;">
                                    📌 <b>Contrôleur Sur-Mesure :</b> {ctrl_sm} | 
                                    ⚖️ <b>Décision Sur-Mesure :</b> <span style="color: {badge_bg}; font-weight: bold;">{dec_sm}</span>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            df_sm_display = df_sm[
                                [
                                    "taille",
                                    "point_de_mesure",
                                    "tolerance",
                                    "valeur_cible",
                                    "piece_1",
                                    "piece_2",
                                    "piece_3",
                                    "piece_4",
                                ]
                            ].rename(
                                columns={
                                    "taille": "Taille",
                                    "point_de_mesure": "Point de mesure",
                                    "tolerance": "TOL (+/-)",
                                    "valeur_cible": "Cible (cm)",
                                    "piece_1": "Pièce 1",
                                    "piece_2": "Pièce 2",
                                    "piece_3": "Pièce 3",
                                    "piece_4": "Pièce 4",
                                }
                            )

                            st.dataframe(
                                df_sm_display,
                                use_container_width=True,
                                hide_index=True,
                            )
                        else:
                            st.info(
                                f"ℹ️ Aucun enregistrement sur-mesure trouvé pour l'OF #{selected_of}."
                            )

                    except Exception as err_sm:
                        st.warning(
                            f"⚠️ Impossible de charger les mesures sur-mesure : {err_sm}"
                        )

    except Exception as e:
        st.error(f"❌ Erreur lors du chargement de l'historique : {e}")