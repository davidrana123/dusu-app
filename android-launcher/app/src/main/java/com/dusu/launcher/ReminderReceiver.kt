package com.dusu.launcher

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Fires daily (from the AlarmManager) → shows the reminder notification. */
class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        Notifications.show(context)
    }
}
