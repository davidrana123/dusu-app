import java.util.Properties

plugins {
    id("com.android.application")
}

// Optional release signing: create android-twa/keystore.properties (git-ignored) with
//   storeFile=..  storePassword=..  keyAlias=..  keyPassword=..
// If absent, `assembleRelease` still runs but the APK is unsigned (use debug for testing).
val keystorePropsFile = rootProject.file("keystore.properties")
val keystoreProps = Properties().apply { if (keystorePropsFile.exists()) load(keystorePropsFile.inputStream()) }

android {
    namespace = "com.dusu.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.dusu.app"     // distinct from com.dusu.launcher — installs side-by-side
        minSdk = 21                        // TWA runs on the device's Chrome engine
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    if (keystorePropsFile.exists()) {
        signingConfigs {
            create("release") {
                storeFile = file(keystoreProps["storeFile"] as String)
                storePassword = keystoreProps["storePassword"] as String
                keyAlias = keystoreProps["keyAlias"] as String
                keyPassword = keystoreProps["keyPassword"] as String
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (keystorePropsFile.exists()) signingConfig = signingConfigs.getByName("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    // Trusted Web Activity support: ships the LauncherActivity that renders the site
    // full-screen on the device's Chrome engine (so Web Speech STT/TTS keep working).
    // Pinned to 2.5.0 — newer 2.7.x pulls androidx.browser 1.10 / core 1.17 which
    // demand AGP 8.9.1 + compileSdk 36. 2.5.0 (browser 1.4, core 1.7) builds cleanly
    // on AGP 8.5.2 / SDK 34 and has all the TWA features we use.
    implementation("com.google.androidbrowserhelper:androidbrowserhelper:2.5.0")
}
