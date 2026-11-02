package {{ cookiecutter.org_name_2 }}.{{ cookiecutter.package_name }}

import io.flutter.embedding.android.FlutterActivity
import android.os.Handler
import android.os.Looper

class MainActivity: FlutterActivity() {
    private val refreshHandler = Handler(Looper.getMainLooper())
    private val refreshAfterStartup = Runnable {
        FinanceSummaryWidgetProvider.requestRefresh(this)
    }

    override fun onResume() {
        super.onResume()
        FinanceSummaryWidgetProvider.requestRefresh(this)
        // Flet abre SQLite durante el arranque. Reintenta cuando Python ya
        // tuvo tiempo de inicializar la base y registrar su ruta.
        refreshHandler.removeCallbacks(refreshAfterStartup)
        refreshHandler.postDelayed(refreshAfterStartup, 5_000L)
    }

    override fun onPause() {
        // Al volver al escritorio, SQLite ya contiene los cambios guardados
        // por Flet y el widget puede mostrar el resumen actualizado.
        FinanceSummaryWidgetProvider.requestRefresh(this)
        refreshHandler.removeCallbacks(refreshAfterStartup)
        super.onPause()
    }

    override fun onDestroy() {
        refreshHandler.removeCallbacks(refreshAfterStartup)
        super.onDestroy()
    }
}
