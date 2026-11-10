package com.example.lmstudio.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ServerStats(
    val cpuUsage: Double = 0.0,
    val memoryUsedMB: Long = 0,
    val memoryTotalMB: Long = 0,
    val gpuUsage: Double? = null,
    val gpuMemoryUsedMB: Long? = null,
    val gpuMemoryTotalMB: Long? = null,
    val temperatureCelsius: Float? = null,
    val fanSpeedPercent: Int? = null,
    val uptimeSeconds: Long = 0,
    val timestamp: Long = System.currentTimeMillis()
)

@Serializable
data class TokenMetrics(
    val tokensPerSecond: Double = 0.0,
    val totalTokensGenerated: Long = 0,
    val totalTokensReceived: Long = 0,
    val avgLatencyMs: Double = 0.0,
    val requestsLastMinute: Int = 0,
    val requestsLastHour: Int = 0,
    val timestamp: Long = System.currentTimeMillis()
)

@Serializable
data class ErrorLog(
    val id: String = java.util.UUID.randomUUID().toString(),
    val message: String,
    val timestamp: Long = System.currentTimeMillis(),
    val severity: Severity = Severity.ERROR,
    val source: String = "LM Studio API"
) {
    enum class Severity { INFO, WARNING, ERROR, CRITICAL }
}

@Serializable
data class ModelInfo(
    val id: String,
    @SerialName("object") val objectType: String = "model",
    @SerialName("owned_by") val ownedBy: String? = null,
    val created: Long = 0
)
