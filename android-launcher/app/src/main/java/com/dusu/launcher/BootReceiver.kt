package com.dusu.launcher

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Re-schedule the daily reminder after a device reboot (alarms are cleared on boot). */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            Notifications.createChannel(context)
            Notifications.scheduleDaily(context)
        }
    }
}
