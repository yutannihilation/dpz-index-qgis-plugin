# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load NiceTile class from file NiceTile.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .nice_tile import NiceTile
    return NiceTile(iface)
