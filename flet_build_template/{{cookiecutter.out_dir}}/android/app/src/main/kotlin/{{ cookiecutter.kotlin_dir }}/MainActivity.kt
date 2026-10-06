package {{ cookiecutter.org_name_2 }}.{{ cookiecutter.package_name }}

import io.flutter.embedding.android.FlutterActivity

class MainActivity: FlutterActivity() {
    override fun onResume() {
        super.onResume()
        FinanceSummaryWidgetProvider.requestRefresh(this)
    }
}
