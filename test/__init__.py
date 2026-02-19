# Import qgis libs so that we set the correct sip api version.
# Skip silently when QGIS is not available (e.g., in lightweight CI/test runs).
try:
    import qgis  # pylint: disable=W0611  # NOQA
except ModuleNotFoundError:
    pass
