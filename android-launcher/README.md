# DuSu Launcher (Android)

A tiny launcher app. It does NOT contain the learning system — it just:

1. Shows a splash → checks internet.
2. **Offline** → "No Internet Connection" + Retry.
3. **Online** → "Start DuSu" button → opens the DuSu web app in the phone's
   **real browser (Chrome)**, where the full Web Speech API (voice) works normally.

No WebView (so voice input never breaks). APK is ~2–3 MB.

## Build in Android Studio (easiest)
1. **Open** the `android-launcher` folder in Android Studio → let Gradle sync.
2. Plug in your phone (USB debugging) → **Run ▶** to install & test, or
3. **Build → Build Bundle(s)/APK(s) → Build APK(s)** → find `app-debug.apk` in
   `android-launcher/app/build/outputs/apk/debug/`.

## Build from command line
```
cd android-launcher
./gradlew assembleDebug        # gradlew is created by Android Studio on first sync
```

## Build in the cloud (no local setup)
Pushing to GitHub triggers `.github/workflows/build-apk.yml`, which builds a
debug APK and uploads it as an artifact (Actions run → Artifacts → download).

## Config
- The URL it opens is in `app/src/main/res/values/strings.xml` → `dusu_url`
  (currently `https://dusu-app-1.onrender.com`; change to your domain later).
- App id: `com.dusu.launcher`. minSdk 26 (Android 8.0+), targetSdk 34.

## Install the APK on a phone
Copy `app-debug.apk` to the phone → tap it → allow "install from unknown
sources" → installed. (Debug-signed; fine for sideloading / sharing with friends.)
