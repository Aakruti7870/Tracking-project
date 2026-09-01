package com.trackmyrmc.triplocation

import android.content.Intent
import android.os.Build
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

class TripLocationModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("TripLocation")

    Function("isAvailable") {
      true
    }

    AsyncFunction("startTracking") { tripId: String, backendUrl: String, token: String ->
      val context = requireNotNull(appContext.reactContext) { "React context is unavailable" }
      TripLocationState.save(context, tripId, backendUrl, token)

      val intent = Intent(context, TripLocationService::class.java).apply {
        action = TripLocationService.ACTION_START
      }

      if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        context.startForegroundService(intent)
      } else {
        context.startService(intent)
      }
      true
    }

    AsyncFunction("stopTracking") {
      val context = requireNotNull(appContext.reactContext) { "React context is unavailable" }
      TripLocationState.clear(context)
      context.stopService(Intent(context, TripLocationService::class.java))
      true
    }
  }
}
