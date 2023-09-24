from PyQt5.QtWidgets import (QApplication, QMainWindow, QStyle, QFileDialog, QMessageBox, QAction,
                            QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QComboBox, QWidget,
                            QFrame, QCheckBox)
from PyQt5.QtCore import (QThreadPool)
from custom_widgets import (UpdateDialog, ParamDialog, VisualizeClusterWidget, Viewer, ToolWidget,
                            InspectionWidget)
from PyQt5 import Qt
import sys
import os
import json
sys.path.insert(0, ".")
from backend import SessionFeature

class MainWindow(QMainWindow):


    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setWindowTitle("Cell Clustering Tool")
        self.setMinimumSize(600, 400)
        
        self.windows = {}

        # Data stuff
        self.sessions = {}
        self.sessions['saline'] = {}
        self.sessions['cocaine'] = {}
        self.path_list = {}

        # Event defaults:
        self.event_defaults = {"ALP": {"window": 20, "delay": 0},
                               "IALP": {"window": 20, "delay": 0},
                               "RNFS": {"window": 20, "delay": 0},
                               "ALP_Timeout": {"window": 20, "delay": 0}}

        # Menu Bar
        pixmapi_folder = QStyle.StandardPixmap.SP_DirIcon
        button_folder = QAction(self.style().standardIcon(pixmapi_folder), "&Load Data", self)
        button_folder.setStatusTip("Select a Folder to load in data")
        button_folder.triggered.connect(self.onMyToolBarButtonClick)
        pixmapi_save = QStyle.StandardPixmap.SP_DialogSaveButton
        button_save = QAction(self.style().standardIcon(pixmapi_save), "&Save", self)
        button_save.setStatusTip("Save current state")
        button_save.triggered.connect(self.save)
        pixmapi_load = QStyle.StandardPixmap.SP_FileDialogStart
        button_load = QAction(self.style().standardIcon(pixmapi_load), "&Load Saved State", self)
        button_load.setStatusTip("Load previously saved state")
        button_load.triggered.connect(self.load_saved_state)
        pixmapi_update = QStyle.StandardPixmap.SP_BrowserReload
        button_update = QAction(self.style().standardIcon(pixmapi_update), "&Update Default Parameters", self)
        button_update.setStatusTip("Update the default parameters of the events")
        button_update.triggered.connect(self.updateDefaults)
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        file_menu.addAction(button_folder)
        file_menu.addAction(button_save)
        file_menu.addAction(button_load)
        file_menu.addAction(button_update)

        # Tool Widgets        
        self.current_selection = None
        self.w_tools = ToolWidget(self.event_defaults)
        self.w_tools.setEnabled(False)

        # Layouts
        layout_central = QHBoxLayout()
        layout_cluster = QVBoxLayout()
        self.cluster_viz = VisualizeClusterWidget()

        layout_cluster.addWidget(self.cluster_viz)
        layout_central.addLayout(layout_cluster)
        layout_central.addWidget(self.w_tools)

        widget = QWidget()
        widget.setLayout(layout_central)
        self.setCentralWidget(widget)

        self.show()

    def activateParams(self, viewer: Viewer):
        if self.current_selection is None:
            self.current_selection = viewer
            self.current_selection.changeToRed()
            self.w_tools.setEnabled(True)
            self.updateParams()
        elif self.current_selection == viewer:
            if viewer.selected == True:
                viewer.changeToWhite()
                self.w_tools.setEnabled(False)
            else:
                viewer.selected = True
                viewer.changeToRed()
                self.w_tools.setEnabled(True)
                self.updateParams()
        else:
            self.current_selection.changeToWhite()

            self.current_selection = viewer
            self.current_selection.changeToRed()
            self.w_tools.setEnabled(True)
            self.updateParams()

    def updateParams(self):
        group, x, y, mouseID = self.current_selection.returnInfo()
        session = self.sessions[group][mouseID][f"{x}:{y}"]
        result = self.path_list[session.dpath]
        result["no_of_clusters"] = session.no_of_clusters

        self.w_tools.update(result, session.data["unit_ids"])

    def updateDefaults(self):
        pdg = UpdateDialog(self.event_defaults)
        if pdg.exec():
            result = pdg.get_result()
        else:
            return
        self.event_defaults = result
        self.w_tools.update_defaults(self.event_defaults)

    def updateCluster(self, result):
        no_of_clusters = result.pop("no_of_clusters")
        outliers = result.pop("outliers")
        self.setWindowTitle("Loading...")
        group, x, y, mouseID = self.current_selection.returnInfo()
        session = self.sessions[group][mouseID][f"{x}:{y}"]
        session.set_outliers(outliers)
        old_result = self.path_list[session.dpath]
        session.load_events(result.keys())
        for event in result:
            delay, window = result[event]["delay"], result[event]["window"]
            session.events[event].set_delay_and_duration(delay, window)
            session.events[event].set_values()        
        result["group"] = old_result["group"]
        result["outliers"] = session.outliers_list
        session.set_vector()
        session.set_no_of_clusters(no_of_clusters)
        session.compute_clustering()
        self.path_list[session.dpath] = result

        # Visualisation stuff
        mouseID, x, y, group, cl_result = session.get_vis_info()
        self.current_selection.updateVisualization(cl_result)
        self.setWindowTitle("Cell Clustering Tool")

        # Check if there is an active subwindow and update it
        name = f"{session.mouseID} {session.day} {session.session}"
        if name in self.windows:
            self.windows[name].refresh()

        
    def startInspection(self, current_selection=None):
        current_selection = self.current_selection if current_selection is None else current_selection
        group, x, y, mouseID = current_selection.returnInfo()
        session = self.sessions[group][mouseID][f"{x}:{y}"]

        name = f"{session.mouseID} {session.day} {session.session}"

        if name not in self.windows:
            wid = InspectionWidget(session, self)
            wid.setWindowTitle(name)
            self.windows[name] = wid
            wid.show()
    
    def deleteSelection(self):
        group, x, y, mouseID = self.current_selection.returnInfo()
        self.cluster_viz.grids[group].removeVisualization(mouseID, x, y)
        path = self.sessions[group][mouseID][f"{x}:{y}"].dpath
        # Remove it from all references
        del self.path_list[path]
        del self.sessions[group][mouseID][f"{x}:{y}"]
        if not self.sessions[group][mouseID]:
            del self.sessions[group][mouseID]


    def removeWindow(self, name):
        self.windows.pop(name)

    def printError(self, s):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("I have a question!")
        if isinstance(s, tuple):
            text = f"For path {s[1]} the following error occurred:\n {s[0]}"
        else:
            text = s
        dlg.setText(text)
        dlg.setIcon(QMessageBox.Icon.Critical)
        dlg.exec()


    def addData(self):
        #self.data.append(data)
        print("finished")


    def onMyToolBarButtonClick(self, s):
        fname = QFileDialog.getExistingDirectory(
            self,
            "Open Folder",
        )
        if fname != '' and fname not in self.path_list:
            pdg = ParamDialog(self.event_defaults)
            if pdg.exec():
                result = pdg.get_result()
            else:
                return
            self.load_session(fname, result)
            

    def load_saved_state(self):
        fname = QFileDialog.getOpenFileName(
            self,
            "Open File",
        )
        fname = fname[0]
        if fname[-4:] == "json":
            if os.path.getsize(fname) != 0:
                self.setWindowTitle("Loading...")
                with open(fname, 'r') as f:
                    self.path_list = json.load(f)

                if "defaults" in self.path_list:
                    self.event_defaults = self.path_list.pop("defaults")
                    self.w_tools.update_defaults(self.event_defaults)

                for path in self.path_list.keys():
                    results = self.path_list[path]
                    self.load_session(path, results)

                self.setWindowTitle("Cell Clustering Tool")      
        

    def load_session(self, fname, result):
        self.setWindowTitle("Loading...")

        events = list(result.keys())
        events.remove("group")
        
        if "outliers" in result:
            events.remove("outliers")
        no_of_clusters = None
        if "no_of_clusters" in events:
            no_of_clusters = result["no_of_clusters"]
            events.remove("no_of_clusters")
        session = SessionFeature(fname, events)
        if no_of_clusters is not None:
            session.no_of_clusters = no_of_clusters
        for event in events:
            delay, window = result[event]["delay"], result[event]["window"]
            session.events[event].set_delay_and_duration(delay, window)
            session.events[event].set_values()

        session.set_group(result["group"])
        if "outliers" in result:
            session.set_outliers(result["outliers"])
        session.set_vector()
        session.compute_clustering()

        self.path_list[fname] = result
        

        # Visualisation stuff
        mouseID, x, y, group, cl_result = session.get_vis_info()
        if session.mouseID not in self.sessions[group]:
            self.sessions[group][f"{session.mouseID}"] = {}
            self.cluster_viz.grids[group].addGrid(mouseID)
        self.sessions[group][f"{session.mouseID}"][f"{x}:{y}"] = session
        # Generate the Grid
        self.cluster_viz.grids[group].addVisualization(group, mouseID, cl_result, x, y)
        self.setWindowTitle("Cell Clustering Tool")

    
    def save(self):
        default_dir = os.getcwd()
        default_filename = os.path.join(default_dir, "paths.json")
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save State", default_filename, "JSON Files (*.json)"
        )
        if filename:
            if self.path_list:
                extended_json = self.path_list.copy()
                extended_json["defaults"] = self.event_defaults
                with open(filename, 'w') as f:
                    json.dump(extended_json, f)

app = QApplication([])
window = MainWindow()
app.exec()