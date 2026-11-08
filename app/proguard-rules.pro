# ProGuard rules for DashboardLMStudio
# Keep model classes used in Retrofit/Gson
-keep class com.example.dashboardlmstudio.** { *; }
-keepclassmembers class com.example.dashboardlmstudio.** { *; }

# Gson specific rules
-keepattributes Signature,InnerClasses,EnclosingMethod
-keep class com.google.gson.** { *; }
-dontwarn com.google.gson.**

# OkHttp/Okio
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }
-keep class okio.** { *; }

# MPAndroidChart
-keep class com.github.mikephil.charting.** { *; }
-dontwarn com.github.mikephil.charting.**

# Retrofit
-keep class retrofit2.** { *; }
-dontwarn retrofit2.**

# Coroutines
-keep class kotlinx.coroutines.** { *; }
-dontwarn kotlinx.coroutines.**

# AndroidX
-keep class androidx.** { *; }
-dontwarn androidx.**

# Keep all public classes and methods in the main package
-keep public class com.example.dashboardlmstudio.** {
    public protected *;
}

# Remove logging calls in release builds
-assumenosideeffects class android.util.Log {
    public static *** d(...);
    public static *** v(...);
    public static *** i(...);
}
