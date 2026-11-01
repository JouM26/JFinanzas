package {{ cookiecutter.org_name_2 }}.{{ cookiecutter.package_name }}

import io.flutter.embedding.android.FlutterActivity

class MainActivity: FlutterActivity() {
    override fun onResume() {
        super.onResume()
        FinanceSummaryWidgetProvider.requestRefresh(this)
    }

    override fun onPause() {
        // Al volver al escritorio, SQLite ya contiene los cambios guardados
        // por Flet y el widget puede mostrar el resumen actualizado.
        FinanceSummaryWidgetProvider.requestRefresh(this)
        super.onPause()
    }
}
