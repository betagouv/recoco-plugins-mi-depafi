import pluggy

hookimpl = pluggy.HookimplMarker("recoco")


class MiDepafiPlugin:
    urls_module = "plugin_mi_depafi.urls"

    @hookimpl
    def project_tab_entries(self):
        return ("plugin_mi_depafi:realisation-list", "Réalisations")
