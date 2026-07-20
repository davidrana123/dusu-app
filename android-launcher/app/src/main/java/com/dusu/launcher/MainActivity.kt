package com.dusu.launcher

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

/**
 * DuSu launcher — a tiny app whose only job is to open the DuSu web app in the
 * user's real browser (Chrome). No WebView, so the browser's full Web Speech
 * API works exactly like normal. It just: checks internet → offers a Start
 * button → opens the URL in Chrome (or the default browser).
 */
class MainActivity : AppCompatActivity() {

    private val dusuUrl: String by lazy { getString(R.string.dusu_url) }

    private lateinit var welcomeView: View
    private lateinit var offlineView: View
    private lateinit var splashView: View

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        splashView = findViewById(R.id.splashView)
        welcomeView = findViewById(R.id.welcomeView)
        offlineView = findViewById(R.id.offlineView)

        findViewById<Button>(R.id.startBtn).setOnClickListener { openDuSu() }
        findViewById<Button>(R.id.retryBtn).setOnClickListener { refresh() }

        // Brief splash (~1.6s), then show the right screen based on connectivity.
        Handler(Looper.getMainLooper()).postDelayed({
            splashView.visibility = View.GONE
            refresh()
        }, 1600)
    }

    // Re-check connectivity whenever the user returns to the app (e.g. from Chrome).
    override fun onResume() {
        super.onResume()
        if (splashView.visibility != View.VISIBLE) refresh()
    }

    private fun refresh() {
        if (isOnline()) {
            welcomeView.visibility = View.VISIBLE
            offlineView.visibility = View.GONE
        } else {
            welcomeView.visibility = View.GONE
            offlineView.visibility = View.VISIBLE
        }
    }

    private fun isOnline(): Boolean {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val net = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(net) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    private fun openDuSu() {
        if (!isOnline()) { refresh(); return }
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(dusuUrl))
        // Prefer Chrome (best Web Speech support); fall back to the default browser.
        try {
            intent.setPackage("com.android.chrome")
            startActivity(intent)
        } catch (e: ActivityNotFoundException) {
            intent.setPackage(null)
            try {
                startActivity(intent)
            } catch (e2: ActivityNotFoundException) {
                Toast.makeText(this, getString(R.string.no_browser), Toast.LENGTH_LONG).show()
            }
        }
    }
}
