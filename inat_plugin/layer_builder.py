"""
Converts iNaturalist observations to a QGIS vector layer.
"""
from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature, QgsGeometry,
    QgsPointXY, QgsProject, QgsCoordinateReferenceSystem,
    QgsSymbol, QgsSingleSymbolRenderer, QgsMarkerSymbol,
    QgsCategorizedSymbolRenderer, QgsRendererCategory
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor


ICONIC_TAXA_COLORS = {
    "Plantae": "#4CAF50",
    "Animalia": "#FF9800",
    "Fungi": "#9C27B0",
    "Insecta": "#FFEB3B",
    "Aves": "#2196F3",
    "Mammalia": "#795548",
    "Reptilia": "#8BC34A",
    "Amphibia": "#00BCD4",
    "Actinopterygii": "#03A9F4",
    "Arachnida": "#F44336",
    "Mollusca": "#FF5722",
    "unknown": "#9E9E9E",
}


def build_layer(observations, layer_name="iNaturalist Beobachtungen"):
    """
    Create a QgsVectorLayer from a list of iNaturalist observation dicts.
    """
    layer = QgsVectorLayer("Point?crs=EPSG:4326", layer_name, "memory")
    provider = layer.dataProvider()

    fields = [
        QgsField("id", QVariant.Int),
        QgsField("observed_on", QVariant.String),
        QgsField("created_at", QVariant.String),
        QgsField("user", QVariant.String),
        QgsField("user_id", QVariant.Int),
        QgsField("taxon_id", QVariant.Int),
        QgsField("taxon_name", QVariant.String),
        QgsField("common_name", QVariant.String),
        QgsField("iconic_taxon", QVariant.String),
        QgsField("taxon_rank", QVariant.String),
        QgsField("quality_grade", QVariant.String),
        QgsField("num_id_agreements", QVariant.Int),
        QgsField("place_guess", QVariant.String),
        QgsField("description", QVariant.String),
        QgsField("url", QVariant.String),
        QgsField("image_url", QVariant.String),
        QgsField("captive", QVariant.Bool),
    ]
    provider.addAttributes(fields)
    layer.updateFields()

    features = []
    for obs in observations:
        loc = obs.get("location")
        if not loc:
            continue
        try:
            lat, lon = map(float, loc.split(","))
        except Exception:
            continue

        taxon = obs.get("taxon") or {}
        user = obs.get("user") or {}
        photos = obs.get("photos") or []

        feat = QgsFeature()
        feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
        feat.setAttributes([
            obs.get("id"),
            obs.get("observed_on", ""),
            (obs.get("created_at") or "")[:10],
            user.get("login", ""),
            user.get("id"),
            taxon.get("id"),
            taxon.get("name", ""),
            (taxon.get("preferred_common_name") or ""),
            taxon.get("iconic_taxon_name", "unknown"),
            taxon.get("rank", ""),
            obs.get("quality_grade", ""),
            obs.get("num_identification_agreements", 0),
            obs.get("place_guess", ""),
            (obs.get("description") or "")[:500],
            f"https://www.inaturalist.org/observations/{obs.get('id')}",
            photos[0].get("url", "").replace("square", "medium") if photos else "",
            obs.get("captive", False),
        ])
        features.append(feat)

    provider.addFeatures(features)
    layer.updateExtents()
    _apply_categorized_style(layer)
    QgsProject.instance().addMapLayer(layer)
    return layer, len(features)


def _apply_categorized_style(layer):
    """Apply colored symbols by iconic taxon."""
    categories = []
    for taxon_name, color_hex in ICONIC_TAXA_COLORS.items():
        symbol = QgsMarkerSymbol.createSimple({
            "name": "circle",
            "color": color_hex,
            "size": "3",
            "outline_color": "#333333",
            "outline_width": "0.2"
        })
        label = taxon_name if taxon_name != "unknown" else "Unbekannt"
        cat = QgsRendererCategory(taxon_name, symbol, label)
        categories.append(cat)

    renderer = QgsCategorizedSymbolRenderer("iconic_taxon", categories)
    layer.setRenderer(renderer)
    layer.triggerRepaint()
