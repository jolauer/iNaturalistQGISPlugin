"""
Background worker thread for iNaturalist API requests.
"""
from qgis.PyQt.QtCore import QThread, pyqtSignal


class FetchWorker(QThread):
    progress = pyqtSignal(int, int)  # loaded, total
    finished = pyqtSignal(list, int)  # observations, total
    error = pyqtSignal(str)

    def __init__(self, api, params, parent=None):
        super().__init__(parent)
        self.api = api
        self.params = params

    def run(self):
        try:
            observations, total = self.api.get_observations(
                self.params,
                progress_callback=lambda loaded, tot: self.progress.emit(loaded, tot)
            )
            self.finished.emit(observations, total)
        except Exception as e:
            self.error.emit(str(e))


class TaxaSearchWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, api, query, parent=None):
        super().__init__(parent)
        self.api = api
        self.query = query

    def run(self):
        try:
            results = self.api.get_taxa(self.query)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))
