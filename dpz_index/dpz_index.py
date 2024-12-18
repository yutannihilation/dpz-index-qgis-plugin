import math
from typing import Callable

from PyQt5.QtCore import QVariant
from PyQt5.QtWidgets import QWidget
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis._core import (
    QgsProject,
    QgsVectorLayer,
    QgsField,
    QgsGraduatedSymbolRenderer,
    QgsClassificationEqualInterval,
    QgsColorBrewerColorRamp,
)
from qgis.gui import QgisInterface

# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the dialog
from .dpz_index_dialog import DpzIndexDialog
import os.path

# constants
DPZ_INDEX_ATTR = "DPZ index"
LINEWIDTH = 1.0
COLOR_RESOLUTION = 20


class DpzIndex:
    """QGIS Plugin Implementation."""

    def __init__(self, iface: QgisInterface):
        """Constructor."""

        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        locale_path = os.path.join(
            self.plugin_dir, "i18n", "DpzIndex_{}.qm".format(locale)
        )

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr("&DPZ index")

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

        self.dlg = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message: str) -> str:
        """Get the translation for a string using Qt translation API."""
        return QCoreApplication.translate("DpzIndex", message)

    def add_action(
        self,
        icon_path: str,
        text: str,
        callback: Callable,
        enabled_flag: bool = True,
        add_to_menu: bool = True,
        add_to_toolbar: bool = True,
        status_tip: str | None = None,
        whats_this: str | None = None,
        parent: QWidget | None = None,
    ) -> QAction:
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ":/plugins/dpz_index/icon.png"
        self.add_action(
            icon_path,
            text=self.tr("DPZ index"),
            callback=self.run,
            parent=self.iface.mainWindow(),
        )

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr("&DPZ index"), action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start:
            self.first_start = False
            self.dlg = DpzIndexDialog()
            self.dlg.button_box.accepted.connect(self.add_layer)

        self.dlg.vector_layers.clear()
        for l in list_vector_layers():
            self.dlg.vector_layers.addItem(l.name())

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            pass

    def add_layer(self):
        """Add a new layer containing the calculated result"""
        chosen = self.dlg.vector_layers.currentItem().text()

        src_layer = None
        for l in list_vector_layers():
            if l.name() == chosen:
                src_layer = l
                break
        if not src_layer:
            # should not happen
            raise RuntimeError("chosen item doesn't exist")

        new_layer = create_dpz_layer(src_layer, COLOR_RESOLUTION, LINEWIDTH)
        QgsProject.instance().addMapLayer(new_layer)
        new_layer.triggerRepaint()

        self.dlg.close()


def list_vector_layers():
    """Get a list of vector layers"""
    layers = QgsProject.instance().mapLayers()
    return [l for l in layers.values() if type(l) is QgsVectorLayer]


def create_dpz_layer(
    src_layer: QgsVectorLayer, color_resolution: int, linewidth: float
) -> QgsVectorLayer:
    new_layer = QgsVectorLayer("LineString", src_layer.name() + " (copy)", "memory")

    new_layer.setCrs(src_layer.crs())

    new_layer.dataProvider().addAttributes(src_layer.dataProvider().fields())

    # adding feature requires editing mode
    new_layer.startEditing()
    new_layer.addFeatures(src_layer.getFeatures())
    new_layer.addAttribute(QgsField(DPZ_INDEX_ATTR, QVariant.Type.Double))
    new_layer.commitChanges()

    new_layer.startEditing()
    for f in new_layer.getFeatures():
        points = f.geometry().asPolyline()
        angle = (points[-1] - points[0]).angle() / math.pi * 180
        f[DPZ_INDEX_ATTR] = abs(angle % 90 - 45)
        new_layer.updateFeature(f)
    new_layer.commitChanges()

    renderer = QgsGraduatedSymbolRenderer(DPZ_INDEX_ATTR)
    renderer.setClassificationMethod(QgsClassificationEqualInterval())
    ramp = QgsColorBrewerColorRamp()
    renderer.setSourceColorRamp(ramp)
    renderer.updateClasses(new_layer, color_resolution)
    renderer.setSymbolSizes(linewidth, linewidth)

    new_layer.setRenderer(renderer)

    return new_layer
