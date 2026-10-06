# historique.py

import io
import os
import warnings

from PIL import Image
import pandas as pd
import streamlit as st
import database as db  # Accès à la base de données SQL Server


def clean_image_bytes(raw_data):
    """Convertit les types binaires SQL Server (memoryview, bytearray, bytes, hex)

    en un format utilisable par st.image().
    """
    if raw_data is None:
        return None
    try:
        if isinstance(raw_data, memoryview):
            raw_data = raw_data.tobytes()
        elif isinstance(raw_data, bytearray):
            raw_data = bytes(raw_data)
        elif isinstance(raw_data, str) and (
            raw_data.startswith("0x") or raw_data.startswith("\\x")
        ):
            raw_data = bytes.fromhex(raw_data[2:])

        # Validation de l'image via PIL
        img = Image.open(io.BytesIO(raw_data))
        img.verify()
        return raw_data
    except Exception:
        return None


def _clean(value):
    """Même nettoyage que lors de l'enregistrement (nom de fichier)."""
    return "".join(c for c in str(value or "") if c.isalnum() or c in ("-", "_"))


def _is_image(nom, mime):
    nom = (nom or "").lower()
    return str(mime or "").startswith("image/") or nom.endswith(
        (".jpg", ".jpeg", ".png")
    )


def collect_photos(selected_of, reference, df_ph, df_pj, fallback_bytes=None):
    """Regroupe TOUTES les photos du contrôle sélectionné.

    Sources : table des photos + images présentes dans les pièces jointes
    + colonne photo_nc de la table principale (en dernier recours).
    Les doublons (même nom de fichier) sont supprimés, et seules les photos
    de la même référence que le contrôle sont conservées.
    """
    prefix = f"{_clean(selected_of)}_{_clean(reference)}_"
    photos, seen = [], set()

    def add(nom, chemin, raw):
        nom = str(nom or "")
        if nom and not nom.startswith(prefix):
            return  # photo d'un autre contrôle du même OF
        if nom and nom in seen:
            return
        if nom:
            seen.add(nom)
        photos.append({"nom": nom or "photo", "chemin": chemin, "bytes": raw})

    if df_ph is not None and not df_ph.empty:
        for _, r in df_ph.iterrows():
            add(r.get("nom_fichier"), r.get("chemin_fichier"), r.get("photo_bytes"))

    if df_pj is not None and not df_pj.empty:
        for _, r in df_pj.iterrows():
            if _is_image(r.get("nom_fichier"), r.get("type_mime")):
                add(r.get("nom_fichier"), r.get("chemin_fichier"), r.get("fichier_data"))

    # Ancien enregistrement : une seule photo dans controle_qualite.photo_nc
    if not photos and fallback_bytes is not None:
        photos.append({"nom": "photo_nc", "chemin": None, "bytes": fallback_bytes})

    photos.sort(key=lambda p: p["nom"])
    return photos


def render_historique():
    st.markdown(
        '<div class="section-header">📊 Historique des contrôles</div>',
        unsafe_allow_html=True,
    )

    try:
        # Chargement des enregistrements depuis la base de données
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
                distinct_decisions = (
                    ["Tous"] + list(df_raw["decision"].dropna().unique())
                    if "decision" in df_raw.columns
                    else ["Tous"]
                )
                search_decision = st.selectbox(
                    "Filtrer par Décision",
                    distinct_decisions,
                    key="hist_filter_dec",
                )
            with f3:
                distinct_chaines = (
                    ["Toutes"] + list(df_raw["chaine"].dropna().unique())
                    if "chaine" in df_raw.columns
                    else ["Toutes"]
                )
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
                "💡 *Cliquez sur une ligne pour afficher les détails, photos, pièces jointes et mesures.*"
            )

            def color_refused(row):
                if row.get("decision") == "Refusé":
                    return ["background-color: rgba(220, 38, 38, 0.15)"] * len(
                        row
                    )
                return [""] * len(row)

            styled_df = df_filtered.style.apply(color_refused, axis=1)

            # Ordre des colonnes
            column_order_list = [
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
                "numero_facture",
                "num_facture",
                "cout_tri",
            ]

            valid_column_order = [
                c for c in column_order_list if c in df_filtered.columns
            ]

            event = st.dataframe(
                styled_df,
                width="stretch",
                hide_index=True,
                column_order=valid_column_order,
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
                    "numero_facture": st.column_config.TextColumn(
                        "🧾 N° Facture"
                    ),
                    "num_facture": st.column_config.TextColumn(
                        "🧾 N° Facture"
                    ),
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

                facture_a_afficher = (
                    row_data.get("numero_facture")
                    or row_data.get("num_facture")
                    or "-"
                )

                d1, d2, d3, d4 = st.columns(4)
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
                with d4:
                    st.write(f"**🧾 N° Facture :** `{facture_a_afficher}`")
                    st.write(
                        f"**💰 Coût de Tri :** {row_data.get('cout_tri', 0):.2f} $"
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

                # ── 📸 SECTION PHOTOS ET PIÈCES JOINTES ──
                st.markdown("##### 📸 Photos NC & 📎 Pièces Jointes")

                selected_of = str(row_data.get("of", "")).strip()
                selected_ref = str(row_data.get("reference", "") or "").strip()
                col_photos, col_docs = st.columns(2)

                # Chargement des deux sources (une seule fois)
                df_ph, df_pj = None, None
                err_load = None
                if selected_of:
                    try:
                        df_ph = db.get_photos_by_of(selected_of)
                    except Exception as err:
                        err_load = f"photos : {err}"
                    try:
                        df_pj = db.get_pieces_jointes_by_of(selected_of)
                    except Exception as err:
                        err_load = f"documents : {err}"

                photos = collect_photos(
                    selected_of,
                    selected_ref,
                    df_ph,
                    df_pj,
                    fallback_bytes=clean_image_bytes(row_data.get("photo_nc")),
                )
                photo_names = {p["nom"] for p in photos}

                # 1. Photos de non-conformité (toutes, en grille)
                with col_photos:
                    st.markdown(f"**Photos de Non-Conformité ({len(photos)})**")
                    if photos:
                        grid = st.columns(2)
                        for i, p in enumerate(photos):
                            with grid[i % 2]:
                                shown = False
                                if p["chemin"] and os.path.exists(str(p["chemin"])):
                                    st.image(
                                        p["chemin"],
                                        caption=f"Photo #{i + 1}",
                                        width="stretch",
                                    )
                                    shown = True
                                else:
                                    img_ok = clean_image_bytes(p["bytes"])
                                    if img_ok:
                                        st.image(
                                            img_ok,
                                            caption=f"Photo #{i + 1}",
                                            width="stretch",
                                        )
                                        shown = True
                                if not shown:
                                    st.warning(
                                        f"⚠️ Photo #{i + 1} introuvable ({p['nom']})"
                                    )
                    elif selected_of:
                        st.caption("Aucune photo associée à ce contrôle.")

                # 2. Pièces jointes (hors photos déjà affichées)
                with col_docs:
                    st.markdown("**Documents & Pièces Jointes**")
                    if selected_of:
                        nb_docs = 0
                        if df_pj is not None and not df_pj.empty:
                            for idx, row_pj in df_pj.iterrows():
                                nom_f = row_pj["nom_fichier"]
                                if nom_f in photo_names:
                                    continue  # déjà affichée dans les photos
                                nb_docs += 1
                                chemin_f = row_pj["chemin_fichier"]
                                bytes_f = row_pj.get("fichier_data")
                                mime_t = (
                                    row_pj.get("type_mime")
                                    or "application/octet-stream"
                                )

                                with st.expander(f"📄 {nom_f}"):
                                    if chemin_f and os.path.exists(chemin_f):
                                        with open(chemin_f, "rb") as file_disk:
                                            st.download_button(
                                                label=f"📥 Télécharger {nom_f}",
                                                data=file_disk.read(),
                                                file_name=nom_f,
                                                mime=mime_t,
                                                key=f"dl_disk_{idx}_{selected_of}_{selected_row_idx}",
                                            )
                                    elif bytes_f:
                                        st.download_button(
                                            label=f"📥 Télécharger {nom_f}",
                                            data=bytes_f,
                                            file_name=nom_f,
                                            mime=mime_t,
                                            key=f"dl_db_{idx}_{selected_of}_{selected_row_idx}",
                                        )
                                    else:
                                        st.caption(
                                            f"⚠️ Fichier introuvable sur le disque : `{chemin_f}`"
                                        )
                        if nb_docs == 0:
                            st.caption("Aucun document joint pour cet OF.")

                if err_load:
                    st.caption(f"Erreur chargement {err_load}")

                # ── 📏 MESURES SUR-MESURE ASSOCIÉES ──
                if selected_of:
                    try:
                        conn = db.get_connection()
                        query_sm = """
                            SELECT taille, point_de_mesure, tolerance, valeur_cible,
                                   piece_1, piece_2, piece_3, piece_4, controleur, decision
                            FROM controle_sur_mesure
                            WHERE LOWER(TRIM([of_num])) = LOWER(TRIM(?))
                            ORDER BY created_at DESC
                        """

                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            df_sm = pd.read_sql(
                                query_sm, conn, params=[selected_of]
                            )
                        conn.close()

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
                                width="stretch",
                                hide_index=True,
                            )
                        else:
                            st.info(
                                f"ℹ️ Aucun enregistrement sur-mesure trouvé pour l'OF {selected_of}."
                            )

                    except Exception as err_sm:
                        st.warning(
                            f"⚠️ Impossible de charger les mesures sur-mesure : {err_sm}"
                        )

    except Exception as e:
        st.error(f"❌ Erreur lors du chargement de l'historique : {e}")