plugins {
    id("com.android.application") version "9.5.1" // Kotlin support is built in since AGP 9
}

android {
    namespace = "com.local.streaming4free"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.local.streaming4free"
        minSdk = 23
        targetSdk = 34 // same as WATCHED and CINEFUSE TV
        versionCode = 1
        versionName = "1.0"
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
            // same key as the two other apps (the computer's Android debug key): sideloaded, never published to a store
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    lint {
        abortOnError = false
    }
}

dependencies {
    val media3 = "1.11.1"
    implementation("androidx.leanback:leanback:1.2.0")
    implementation("androidx.media3:media3-exoplayer:$media3")
    implementation("androidx.media3:media3-exoplayer-hls:$media3")
    implementation("androidx.media3:media3-exoplayer-dash:$media3")
    implementation("androidx.media3:media3-ui:$media3")
    implementation("io.coil-kt:coil:2.7.0")
    testImplementation("junit:junit:4.13.2")
}
