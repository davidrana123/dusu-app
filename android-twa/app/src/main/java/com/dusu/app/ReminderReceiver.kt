package com.dusu.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Fires every 4 hours (from AlarmManager) → shows the reminder notification. */
class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        Notifications.show(context)
    }
}
