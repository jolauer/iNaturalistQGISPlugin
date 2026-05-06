import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from .dialog import INaturalistDialog


class INaturalistPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.action = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        self.action = QAction(
            QIcon(icon_path),
            'iNaturalist Explorer',
            self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToWebMenu('iNaturalist Explorer', self.action)

    def unload(self):
        self.iface.removePluginWebMenu('iNaturalist Explorer', self.action)
        self.iface.removeToolBarIcon(self.action)
        del self.action

    def run(self):
        if self.dialog is None:
            self.dialog = INaturalistDialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
