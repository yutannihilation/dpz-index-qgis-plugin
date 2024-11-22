# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load DpzIndex class.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .dpz_index import DpzIndex
    return DpzIndex(iface)
