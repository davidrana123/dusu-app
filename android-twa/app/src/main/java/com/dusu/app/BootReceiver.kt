package com.dusu.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Alarms are cleared on reboot — re-arm the 4-hour reminder after BOOT_COMPLETED. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            Notifications.createChannel(context)
            Notifications.scheduleEvery4Hours(context)
        }
    }
}
