"""
Main dialog for the iNaturalist QGIS Plugin.
"""
import os
from qgis.PyQt.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QComboBox,
    QDateEdit, QCheckBox, QSpinBox, QProgressBar, QTextEdit,
    QFormLayout, QMessageBox, QCompleter, QSizePolicy, QFrame,
    QDoubleSpinBox, QRadioButton, QButtonGroup
)
from qgis.PyQt.QtCore import Qt, QDate, QStringListModel
from qgis.PyQt.QtGui import QFont, QColor, QPalette

from qgis.core import QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject

from .api import INaturalistAPI
from .layer_builder import build_layer
from .workers import FetchWorker, TaxaSearchWorker


ICONIC_TAXA = [
    ("Alle Gruppen", ""),
    ("Pflanzen (Plantae)", "47126"),
    ("Tiere (Animalia)", "1"),
    ("Pilze (Fungi)", "47170"),
    ("Vögel (Aves)", "3"),
    ("Säugetiere (Mammalia)", "40151"),
    ("Reptilien (Reptilia)", "26036"),
    ("Amphibien (Amphibia)", "20978"),
    ("Insekten (Insecta)", "47158"),
    ("Spinnen (Arachnida)", "47119"),
    ("Fische (Actinopterygii)", "47178"),
    ("Weichtiere (Mollusca)", "47115"),
]

QUALITY_GRADES = [
    ("Alle", ""),
    ("Forschungsqualität", "research"),
    ("Benötigt ID", "needs_id"),
    ("Gelegentlich", "casual"),
]


class INaturalistDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.api = INaturalistAPI()
        self.fetch_worker = None
        self.taxa_worker = None
        self.selected_taxon_id = None

        self.setWindowTitle("iNaturalist Explorer")
        self.setMinimumWidth(520)
        self.setMinimumHeight(640)
        self._build_ui()

    # ─────────────────────────── UI CONSTRUCTION ───────────────────────────

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)

        # Header
        header = QLabel("🌿 iNaturalist Explorer")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        header.setFont(font)
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("color: #2e7d32; padding: 6px;")
        main_layout.addWidget(header)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tabs.addTab(self._build_login_tab(), "🔑 Login")
        self.tabs.addTab(self._build_query_tab(), "🔍 Abfrage")
        self.tabs.addTab(self._build_filter_tab(), "🎛️ Filter")
        self.tabs.addTab(self._build_results_tab(), "📋 Ergebnisse")

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Bereit.")
        self.status_label.setStyleSheet("color: #555; font-size: 11px;")
        main_layout.addWidget(self.status_label)

        # Action buttons
        btn_layout = QHBoxLayout()
        self.load_btn = QPushButton("▶ Beobachtungen laden")
        self.load_btn.setStyleSheet(
            "QPushButton { background-color: #2e7d32; color: white; font-weight: bold; "
            "padding: 8px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #388e3c; }"
            "QPushButton:disabled { background-color: #aaa; }"
        )
        self.load_btn.clicked.connect(self._on_load)
        self.cancel_btn = QPushButton("■ Abbrechen")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

    # ── Login Tab ──

    def _build_login_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        info = QLabel(
            "Für erweiterte Abfragen melden Sie sich an.\n"
            "Sie benötigen eine OAuth App unter:\n"
            "https://www.inaturalist.org/oauth/applications"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; background: #f9f9f9; padding: 8px; border-radius: 4px;")
        layout.addWidget(info)

        form = QFormLayout()
        self.le_username = QLineEdit()
        self.le_username.setPlaceholderText("iNaturalist Benutzername")
        self.le_password = QLineEdit()
        self.le_password.setEchoMode(QLineEdit.Password)
        self.le_password.setPlaceholderText("Passwort")
        self.le_app_id = QLineEdit()
        self.le_app_id.setPlaceholderText("OAuth App ID")
        self.le_app_secret = QLineEdit()
        self.le_app_secret.setEchoMode(QLineEdit.Password)
        self.le_app_secret.setPlaceholderText("OAuth App Secret")

        form.addRow("Benutzername:", self.le_username)
        form.addRow("Passwort:", self.le_password)
        form.addRow("App ID:", self.le_app_id)
        form.addRow("App Secret:", self.le_app_secret)
        layout.addLayout(form)

        self.login_btn = QPushButton("Anmelden")
        self.login_btn.setStyleSheet(
            "QPushButton { background-color: #1565c0; color: white; padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1976d2; }"
        )
        self.login_btn.clicked.connect(self._on_login)
        layout.addWidget(self.login_btn)

        self.login_status = QLabel("Nicht angemeldet (anonyme Abfragen möglich)")
        self.login_status.setStyleSheet("color: #888; font-style: italic;")
        self.login_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.login_status)

        anon_note = QLabel(
            "ℹ️  Ohne Login sind anonyme Abfragen möglich,\n"
            "aber Rate-Limits gelten und private Beobachtungen\n"
            "werden nicht angezeigt."
        )
        anon_note.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(anon_note)
        layout.addStretch()
        return w

    # ── Query Tab ──

    def _build_query_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # Extent source
        extent_group = QGroupBox("Räumlicher Bereich")
        eg_layout = QVBoxLayout(extent_group)

        self.rb_canvas = QRadioButton("Canvas-Ausdehnung verwenden")
        self.rb_bbox = QRadioButton("Manuelle Bounding Box")
        self.rb_canvas.setChecked(True)
        self.extent_grp = QButtonGroup()
        self.extent_grp.addButton(self.rb_canvas)
        self.extent_grp.addButton(self.rb_bbox)
        eg_layout.addWidget(self.rb_canvas)

        self.btn_from_canvas = QPushButton("📐 Aktuelle Canvas-Ausdehnung übernehmen")
        self.btn_from_canvas.clicked.connect(self._get_canvas_extent)
        eg_layout.addWidget(self.btn_from_canvas)

        eg_layout.addWidget(self.rb_bbox)

        bbox_layout = QFormLayout()
        self.sb_north = QDoubleSpinBox(); self.sb_north.setRange(-90, 90); self.sb_north.setDecimals(6)
        self.sb_south = QDoubleSpinBox(); self.sb_south.setRange(-90, 90); self.sb_south.setDecimals(6)
        self.sb_east = QDoubleSpinBox(); self.sb_east.setRange(-180, 180); self.sb_east.setDecimals(6)
        self.sb_west = QDoubleSpinBox(); self.sb_west.setRange(-180, 180); self.sb_west.setDecimals(6)

        # Default: Germany
        self.sb_north.setValue(55.0); self.sb_south.setValue(47.3)
        self.sb_east.setValue(15.0); self.sb_west.setValue(5.9)

        bbox_layout.addRow("Nord (max lat):", self.sb_north)
        bbox_layout.addRow("Süd (min lat):", self.sb_south)
        bbox_layout.addRow("Ost (max lon):", self.sb_east)
        bbox_layout.addRow("West (min lon):", self.sb_west)
        eg_layout.addLayout(bbox_layout)
        layout.addWidget(extent_group)

        # Layer options
        layer_group = QGroupBox("Layer-Optionen")
        lg_layout = QFormLayout(layer_group)
        self.le_layer_name = QLineEdit("iNaturalist Beobachtungen")
        self.sb_max_results = QSpinBox()
        self.sb_max_results.setRange(1, 10000)
        self.sb_max_results.setValue(1000)
        self.sb_max_results.setSuffix(" Beobachtungen")
        lg_layout.addRow("Layer-Name:", self.le_layer_name)
        lg_layout.addRow("Max. Ergebnisse:", self.sb_max_results)
        layout.addWidget(layer_group)
        layout.addStretch()
        return w

    # ── Filter Tab ──

    def _build_filter_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # Taxon filter
        taxon_group = QGroupBox("Taxon / Artgruppe")
        tg_layout = QVBoxLayout(taxon_group)

        grp_layout = QFormLayout()
        self.cb_iconic_taxon = QComboBox()
        for label, val in ICONIC_TAXA:
            self.cb_iconic_taxon.addItem(label, val)
        grp_layout.addRow("Gruppe:", self.cb_iconic_taxon)
        tg_layout.addLayout(grp_layout)

        species_layout = QHBoxLayout()
        self.le_taxon_search = QLineEdit()
        self.le_taxon_search.setPlaceholderText("Artname suchen (z.B. Quercus, Falco...)")
        self.btn_taxon_search = QPushButton("🔎")
        self.btn_taxon_search.setFixedWidth(32)
        self.btn_taxon_search.clicked.connect(self._search_taxa)
        self.le_taxon_search.returnPressed.connect(self._search_taxa)
        species_layout.addWidget(self.le_taxon_search)
        species_layout.addWidget(self.btn_taxon_search)
        tg_layout.addLayout(species_layout)

        self.cb_taxon_results = QComboBox()
        self.cb_taxon_results.addItem("-- Artsuche oben durchführen --", None)
        self.cb_taxon_results.currentIndexChanged.connect(self._on_taxon_selected)
        tg_layout.addWidget(self.cb_taxon_results)
        layout.addWidget(taxon_group)

        # User filter
        user_group = QGroupBox("Benutzer")
        ug_layout = QFormLayout(user_group)
        self.le_user = QLineEdit()
        self.le_user.setPlaceholderText("iNaturalist Benutzername")
        self.le_ident_user = QLineEdit()
        self.le_ident_user.setPlaceholderText("Benutzer der Bestimmung gemacht hat")
        ug_layout.addRow("Beobachter:", self.le_user)
        ug_layout.addRow("Bestimmer:", self.le_ident_user)
        layout.addWidget(user_group)

        # Date filter
        date_group = QGroupBox("Zeitraum")
        dg_layout = QFormLayout(date_group)
        self.de_date_from = QDateEdit()
        self.de_date_from.setCalendarPopup(True)
        self.de_date_from.setDisplayFormat("dd.MM.yyyy")
        self.de_date_from.setDate(QDate.currentDate().addYears(-1))
        self.cb_date_from_enabled = QCheckBox("Von:")
        self.cb_date_from_enabled.setChecked(False)

        self.de_date_to = QDateEdit()
        self.de_date_to.setCalendarPopup(True)
        self.de_date_to.setDisplayFormat("dd.MM.yyyy")
        self.de_date_to.setDate(QDate.currentDate())
        self.cb_date_to_enabled = QCheckBox("Bis:")
        self.cb_date_to_enabled.setChecked(False)

        from_row = QHBoxLayout()
        from_row.addWidget(self.cb_date_from_enabled)
        from_row.addWidget(self.de_date_from)
        to_row = QHBoxLayout()
        to_row.addWidget(self.cb_date_to_enabled)
        to_row.addWidget(self.de_date_to)

        dg_layout.addRow(from_row)
        dg_layout.addRow(to_row)
        layout.addWidget(date_group)

        # Quality / other filters
        qual_group = QGroupBox("Qualität & weitere Filter")
        qg_layout = QFormLayout(qual_group)

        self.cb_quality = QComboBox()
        for label, val in QUALITY_GRADES:
            self.cb_quality.addItem(label, val)
        self.cb_quality.setCurrentIndex(1)  # research quality default

        self.cb_captive = QComboBox()
        self.cb_captive.addItem("Alle (wild + kultiviert)", "")
        self.cb_captive.addItem("Nur wild", "false")
        self.cb_captive.addItem("Nur kultiviert/gefangen", "true")
        self.cb_captive.setCurrentIndex(1)  # only wild default

        self.cb_has_photos = QCheckBox("Nur mit Fotos")
        self.cb_has_photos.setChecked(True)
        self.cb_has_sounds = QCheckBox("Nur mit Tonaufnahmen")

        qg_layout.addRow("Qualitätsstufe:", self.cb_quality)
        qg_layout.addRow("Kultiviert:", self.cb_captive)
        qg_layout.addRow(self.cb_has_photos)
        qg_layout.addRow(self.cb_has_sounds)
        layout.addWidget(qual_group)
        layout.addStretch()
        return w

    # ── Results Tab ──

    def _build_results_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText(
            "Nach dem Laden werden hier Informationen zu den Ergebnissen angezeigt."
        )
        layout.addWidget(self.results_text)

        self.btn_clear_results = QPushButton("🗑 Ergebnisse löschen")
        self.btn_clear_results.clicked.connect(self.results_text.clear)
        layout.addWidget(self.btn_clear_results)
        return w

    # ─────────────────────────── ACTIONS ───────────────────────────────────

    def _on_login(self):
        username = self.le_username.text().strip()
        password = self.le_password.text().strip()
        app_id = self.le_app_id.text().strip()
        app_secret = self.le_app_secret.text().strip()

        if not all([username, password, app_id, app_secret]):
            QMessageBox.warning(self, "Fehlende Angaben", "Bitte alle Login-Felder ausfüllen.")
            return

        self.login_btn.setEnabled(False)
        self.login_status.setText("Anmeldung läuft...")
        self._set_status("Anmeldung bei iNaturalist...")

        success, msg = self.api.login(username, password, app_id, app_secret)

        self.login_btn.setEnabled(True)
        if success:
            self.login_status.setText(f"✅ Angemeldet als: {self.api.username}")
            self.login_status.setStyleSheet("color: #2e7d32; font-weight: bold;")
            self._set_status("Login erfolgreich.")
        else:
            self.login_status.setText(f"❌ Fehler: {msg}")
            self.login_status.setStyleSheet("color: #c62828;")
            self._set_status(f"Login fehlgeschlagen: {msg}")

    def _get_canvas_extent(self):
        canvas = self.iface.mapCanvas()
        extent = canvas.extent()
        src_crs = canvas.mapSettings().destinationCrs()
        dst_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(src_crs, dst_crs, QgsProject.instance())
        ext_wgs84 = transform.transformBoundingBox(extent)

        self.sb_north.setValue(round(ext_wgs84.yMaximum(), 6))
        self.sb_south.setValue(round(ext_wgs84.yMinimum(), 6))
        self.sb_east.setValue(round(ext_wgs84.xMaximum(), 6))
        self.sb_west.setValue(round(ext_wgs84.xMinimum(), 6))
        self.rb_bbox.setChecked(True)
        self._set_status("Canvas-Ausdehnung übernommen.")

    def _search_taxa(self):
        query = self.le_taxon_search.text().strip()
        if not query:
            return
        self._set_status(f"Suche nach Taxon: {query}...")
        self.btn_taxon_search.setEnabled(False)

        self.taxa_worker = TaxaSearchWorker(self.api, query)
        self.taxa_worker.finished.connect(self._on_taxa_results)
        self.taxa_worker.error.connect(self._on_taxa_error)
        self.taxa_worker.start()

    def _on_taxa_results(self, results):
        self.btn_taxon_search.setEnabled(True)
        self.cb_taxon_results.clear()
        if not results:
            self.cb_taxon_results.addItem("Keine Treffer gefunden", None)
            self._set_status("Keine Taxon-Treffer.")
            return
        self.cb_taxon_results.addItem("-- Bitte wählen --", None)
        for t in results:
            name = t.get("name", "?")
            common = t.get("preferred_common_name", "")
            rank = t.get("rank", "")
            label = f"{name} ({common}) [{rank}]" if common else f"{name} [{rank}]"
            self.cb_taxon_results.addItem(label, t.get("id"))
        self._set_status(f"{len(results)} Taxa gefunden.")

    def _on_taxa_error(self, msg):
        self.btn_taxon_search.setEnabled(True)
        self._set_status(f"Taxon-Suche Fehler: {msg}")

    def _on_taxon_selected(self, idx):
        self.selected_taxon_id = self.cb_taxon_results.itemData(idx)

    def _build_params(self):
        params = {}

        # BBox
        if self.rb_canvas.isChecked():
            self._get_canvas_extent()

        params["nelat"] = self.sb_north.value()
        params["nelng"] = self.sb_east.value()
        params["swlat"] = self.sb_south.value()
        params["swlng"] = self.sb_west.value()

        # Iconic taxon
        iconic_val = self.cb_iconic_taxon.currentData()
        if iconic_val:
            params["iconic_taxa[]"] = iconic_val

        # Specific taxon
        if self.selected_taxon_id:
            params["taxon_id"] = self.selected_taxon_id

        # User filters
        user = self.le_user.text().strip()
        if user:
            params["user_login"] = user
        ident_user = self.le_ident_user.text().strip()
        if ident_user:
            params["ident_user_login"] = ident_user

        # Date filters
        if self.cb_date_from_enabled.isChecked():
            params["d1"] = self.de_date_from.date().toString("yyyy-MM-dd")
        if self.cb_date_to_enabled.isChecked():
            params["d2"] = self.de_date_to.date().toString("yyyy-MM-dd")

        # Quality
        quality_val = self.cb_quality.currentData()
        if quality_val:
            params["quality_grade"] = quality_val

        # Captive
        captive_val = self.cb_captive.currentData()
        if captive_val:
            params["captive"] = captive_val

        # Media
        if self.cb_has_photos.isChecked():
            params["photos"] = "true"
        if self.cb_has_sounds.isChecked():
            params["sounds"] = "true"

        return params

    def _on_load(self):
        params = self._build_params()
        max_results = self.sb_max_results.value()

        self._set_status("Lade Beobachtungen von iNaturalist...")
        self.load_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        self.tabs.setCurrentIndex(3)  # Switch to results tab

        self.fetch_worker = FetchWorker(self.api, params)
        self.fetch_worker.progress.connect(self._on_progress)
        self.fetch_worker.finished.connect(lambda obs, total: self._on_fetch_done(obs, total, max_results))
        self.fetch_worker.error.connect(self._on_fetch_error)
        self.fetch_worker.start()

    def _on_progress(self, loaded, total):
        if total > 0:
            pct = int(min(loaded / total * 100, 100))
            self.progress_bar.setValue(pct)
        self._set_status(f"Lade... {loaded} / {total} Beobachtungen")

    def _on_fetch_done(self, observations, total, max_results):
        self.cancel_btn.setEnabled(False)
        self.load_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        # Truncate to max_results
        if len(observations) > max_results:
            observations = observations[:max_results]

        if not observations:
            self._set_status("Keine Beobachtungen im gewählten Bereich / Filter.")
            self.results_text.setPlainText("Keine Beobachtungen gefunden.")
            return

        layer_name = self.le_layer_name.text().strip() or "iNaturalist Beobachtungen"
        layer, count = build_layer(observations, layer_name)

        # Summary
        from collections import Counter
        taxa_counts = Counter(
            (o.get("taxon") or {}).get("iconic_taxon_name", "unknown")
            for o in observations
        )
        taxa_summary = "\n".join(
            f"  • {k}: {v}" for k, v in taxa_counts.most_common()
        )

        user_counts = Counter(
            (o.get("user") or {}).get("login", "?")
            for o in observations
        )
        top_users = "\n".join(
            f"  • {k}: {v}" for k, v in user_counts.most_common(10)
        )

        summary = (
            f"✅ Erfolgreich geladen!\n\n"
            f"Gesamt gefunden: {total:,}\n"
            f"Geladen: {count:,} Beobachtungen\n"
            f"Layer: '{layer_name}'\n\n"
            f"── Artgruppen ──\n{taxa_summary}\n\n"
            f"── Top-Beobachter (max. 10) ──\n{top_users}\n"
        )
        self.results_text.setPlainText(summary)
        self._set_status(f"{count} Beobachtungen geladen → Layer '{layer_name}' erstellt.")

    def _on_fetch_error(self, msg):
        self.load_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self._set_status(f"Fehler: {msg}")
        QMessageBox.critical(self, "API Fehler", f"Fehler beim Laden:\n{msg}")

    def _on_cancel(self):
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.terminate()
            self.fetch_worker.wait()
        self.load_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self._set_status("Abgebrochen.")

    def _set_status(self, msg):
        self.status_label.setText(msg)
