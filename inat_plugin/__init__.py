def classFactory(iface):
    from .plugin import INaturalistPlugin
    return INaturalistPlugin(iface)
