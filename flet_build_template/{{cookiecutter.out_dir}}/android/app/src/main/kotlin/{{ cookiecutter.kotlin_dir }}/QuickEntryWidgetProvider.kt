package {{ cookiecutter.org_name_2 }}.{{ cookiecutter.package_name }}

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews

class QuickEntryWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray
    ) {
        appWidgetIds.forEach { appWidgetId ->
            val views = RemoteViews(context.packageName, R.layout.quick_entry_widget)
            views.setOnClickPendingIntent(
                R.id.widget_income,
                quickEntryIntent(context, appWidgetId * 2, "ingreso")
            )
            views.setOnClickPendingIntent(
                R.id.widget_expense,
                quickEntryIntent(context, appWidgetId * 2 + 1, "gasto")
            )
            appWidgetManager.updateAppWidget(appWidgetId, views)
        }
    }

    private fun quickEntryIntent(context: Context, requestCode: Int, type: String): PendingIntent {
        val intent = Intent(context, QuickEntryActivity::class.java).apply {
            putExtra(QuickEntryActivity.EXTRA_TYPE, type)
        }
        return PendingIntent.getActivity(
            context,
            requestCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }
}
