# DuSu — Android app (TWA)

Runs the live DuSu web app **inside the app**, full-screen, on the device's own
Chrome engine (Trusted Web Activity). Because it *is* Chrome under the hood, the
Web Speech API (mic STT + TTS) works exactly like it does in the browser — unlike a
plain WebView, which breaks speech recognition.

This is a **separate module** from `../android-launcher` (which only kicked the user
out to external Chrome). Different package name (`com.dusu.app` vs `com.dusu.launcher`)
so both can be installed side-by-side.

- **Loads:** `https://dusu-app-1.onrender.com/`
- **Package:** `com.dusu.app`
- **Min Android:** 5.0 (API 21)

---

## 1. Build

Needs JDK 17 + Android SDK (same setup that builds `android-launcher`).

```bash
cd android-twa

# Quick test build (debug — self-signed, installable immediately):
./gradlew assembleDebug
# → app/build/outputs/apk/debug/app-debug.apk

# Release build (needs a keystore — see step 2):
./gradlew assembleRelease
# → app/build/outputs/apk/release/app-release.apk
```

Install on a phone (USB debugging on):

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The debug APK opens the site inside a **Custom Tab bar** until the asset-links
verification (step 3) matches the APK's signature. Speech already works; the top bar
just isn't hidden yet.

---

## 2. Release keystore (one time)

```bash
keytool -genkey -v -keystore dusu-release.jks -keyalg RSA -keysize 2048 \
  -validity 10000 -alias dusu
```

Create `android-twa/keystore.properties` (git-ignored):

```properties
storeFile=dusu-release.jks
storePassword=YOUR_STORE_PASSWORD
keyAlias=dusu
keyPassword=YOUR_KEY_PASSWORD
```

`assembleRelease` then signs automatically.

---

## 3. Full-screen (drop the address bar) — Digital Asset Links

Chrome hides its UI only when the site and the app vouch for each other.

**a. Get the APK's signing SHA-256:**

```bash
# debug key:
keytool -list -v -keystore ~/.android/debug.keystore -alias androiddebugkey \
  -storepass android -keypass android | grep SHA256
# release key:
keytool -list -v -keystore dusu-release.jks -alias dusu | grep SHA256
```

Copy the `SHA256:` value (e.g. `AB:CD:...:EF`).

**b. Tell the server about it** — set an env var on Render (backend service):

```
ANDROID_CERT_SHA256 = AB:CD:...:EF
```

(Comma-separate multiple, e.g. your upload key **and** the Play App Signing key.)

The backend already serves the matching statement at
`https://dusu-app-1.onrender.com/.well-known/assetlinks.json` from that env var.
Verify after deploy:

```bash
curl -s https://dusu-app-1.onrender.com/.well-known/assetlinks.json
```

The app side is already declared (`app/src/main/res/values/strings.xml` →
`asset_statements`).

**c. Reinstall the app.** On next launch Chrome verifies both directions and runs
DuSu edge-to-edge with no address bar.

---

## 4. Custom domain later

If you move off `onrender.com`, update in three places:
1. `app/src/main/res/values/strings.xml` — `launchUrl`, `hostName`, `asset_statements` site.
2. Render env — keep `ANDROID_CERT_SHA256` (same cert), point the domain's DNS.
3. The new domain must serve `/.well-known/assetlinks.json` (the backend route does).

---

## 5. Play Store (optional)

Play needs an **AAB**, not an APK:

```bash
./gradlew bundleRelease   # → app/build/outputs/bundle/release/app-release.aab
```

With Play App Signing, add **both** the upload-key SHA-256 and the Play-issued
app-signing SHA-256 to `ANDROID_CERT_SHA256`.
