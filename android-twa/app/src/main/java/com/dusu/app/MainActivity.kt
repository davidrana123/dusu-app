package com.dusu.app

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.Button
import androidx.core.content.ContextCompat
import com.google.androidbrowserhelper.trusted.LauncherActivity as TwaLauncherActivity

/**
 * Entry activity. Its only jobs:
 *   1) If the phone is OFFLINE, show a "turn on the internet" screen (don't open a blank
 *      Chrome error). Retry re-checks.
 *   2) If ONLINE, launch the Trusted Web Activity (DuSu running inside the app on Chrome's
 *      engine — so Web Speech mic/voice works).
 * It also (re)schedules the 4-hourly practice reminder each time it runs.
 */
class MainActivity : android.app.Activity() {

    private lateinit var splashView: View
    private lateinit var offlineView: View
    private var launched = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        splashView = findViewById(R.id.splashView)
        offlineView = findViewById(R.id.offlineView)
        findViewById<Button>(R.id.retryBtn).setOnClickListener { decide() }

        // Local 4-hourly reminders (no server).
        Notifications.createChannel(this)
        Notifications.scheduleEvery4Hours(this)
        requestNotifPermission()

        // Brief splash, then route by connectivity.
        Handler(Looper.getMainLooper()).postDelayed({
            splashView.visibility = View.GONE
            decide()
        }, 1200)
    }

    override fun onResume() {
        super.onResume()
        // Coming back from the TWA → the session is over; close this shim so the user
        // lands on the launcher, not a blank screen (and no relaunch loop).
        if (launched) { finish(); return }
        // Still on the offline screen: re-check in case the user just enabled data.
        if (splashView.visibility != View.VISIBLE) decide()
    }

    private fun decide() {
        if (isOnline()) {
            offlineView.visibility = View.GONE
            launchDuSu()
        } else {
            offlineView.visibility = View.VISIBLE
        }
    }

    private fun launchDuSu() {
        if (launched) return
        launched = true
        startActivity(Intent(this, TwaLauncherActivity::class.java))
        // Keep MainActivity in the back stack so returning re-checks connectivity;
        // do NOT finish() here (finishing would drop the TWA's parent task on some OEMs).
    }

    private fun isOnline(): Boolean {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val net = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(net) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    private fun requestNotifPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 101)
            }
        }
    }
}
