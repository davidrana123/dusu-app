package com.dusu.app

import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

/** Local, no-server practice reminder — fires every 4 hours with a rotating message. */
object Notifications {

    const val CHANNEL_ID = "dusu_reminders"
    const val NOTIF_ID = 1001
    private const val FOUR_HOURS_MS = 4L * 60L * 60L * 1000L

    fun createChannel(ctx: Context) {
        val mgr = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val ch = NotificationChannel(
            CHANNEL_ID,
            ctx.getString(R.string.notif_channel_name),
            NotificationManager.IMPORTANCE_DEFAULT
        ).apply { description = "Nudges to practise English with DuSu" }
        mgr.createNotificationChannel(ch)
    }

    /** Inexact (battery-friendly) repeating alarm every 4 hours, first fire in 4 hours. */
    fun scheduleEvery4Hours(ctx: Context) {
        val am = ctx.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val pi = PendingIntent.getBroadcast(
            ctx, 0, Intent(ctx, ReminderReceiver::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val first = System.currentTimeMillis() + FOUR_HOURS_MS
        am.setInexactRepeating(AlarmManager.RTC_WAKEUP, first, FOUR_HOURS_MS, pi)
    }

    /** Build + show the current reminder (message rotates by 4-hour slot). */
    fun show(ctx: Context) {
        val msgs = ctx.resources.getStringArray(R.array.notif_messages)
        val slot = (System.currentTimeMillis() / FOUR_HOURS_MS).toInt()
        val parts = msgs[Math.floorMod(slot, msgs.size)].split("||")
        val title = parts.getOrElse(0) { "DuSu" }
        val body = parts.getOrElse(1) { "Time to practise English." }

        val open = PendingIntent.getActivity(
            ctx, 0, Intent(ctx, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notif = NotificationCompat.Builder(ctx, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(open)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()

        try {
            NotificationManagerCompat.from(ctx).notify(NOTIF_ID, notif)
        } catch (e: SecurityException) {
            // POST_NOTIFICATIONS not granted (Android 13+) — ignore silently.
        }
    }
}
