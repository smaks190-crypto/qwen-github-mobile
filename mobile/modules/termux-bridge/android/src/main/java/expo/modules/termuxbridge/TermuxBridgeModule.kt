package expo.modules.termuxbridge

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import android.os.Build
import expo.modules.kotlin.Promise
import expo.modules.core.permissions.Permissions
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger

/** The app never runs a web server: Termux executes a single background command and returns stdout. */
class TermuxBridgeModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("TermuxBridge")

    AsyncFunction("run") { payload: String, promise: Promise ->
      val context = appContext.reactContext
      if (context == null) {
        promise.reject("NO_CONTEXT", "Android context is not available", null)
      } else {
        TermuxCommands.run(context, payload, promise)
      }
    }

    AsyncFunction("cancel") { jobId: String, promise: Promise ->
      val context = appContext.reactContext
      if (context == null) {
        promise.reject("NO_CONTEXT", "Android context is not available", null)
      } else {
        // Cancels the Termux subprocess via an independent short-lived command.
        TermuxCommands.run(context, "{\"action\":\"cancel\",\"job_id\":\"${jobId.replace("\"", "")}\"}", promise)
      }
    }

    // The user must consent to Termux's custom dangerous permission at runtime.
    Function("hasTermuxPermission") {
      val context = appContext.reactContext
      context != null && context.checkSelfPermission("com.termux.permission.RUN_COMMAND") == PackageManager.PERMISSION_GRANTED
    }

    AsyncFunction("requestTermuxPermission") { promise: Promise ->
      Permissions.askForPermissionsWithPermissionsManager(
        appContext.permissions, promise, "com.termux.permission.RUN_COMMAND"
      )
    }

    Function("openAppPermissionSettings") {
      appContext.reactContext?.let { context ->
        val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
          Uri.parse("package:${context.packageName}"))
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
      }
    }

    Function("isTermuxInstalled") {
      val context = appContext.reactContext
      if (context == null) false else try {
        context.packageManager.getPackageInfo("com.termux", 0)
        true
      } catch (_: PackageManager.NameNotFoundException) {
        false
      }
    }
  }
}

internal object TermuxCommands {
  private val nextId = AtomicInteger(2000)
  private val pending = ConcurrentHashMap<Int, Promise>()
  private const val HOME = "/data/data/com.termux/files/home"
  private const val PYTHON = "/data/data/com.termux/files/usr/bin/python"
  private const val RUNNER = "$HOME/.local/bin/qwen-github-agent.py"

  fun run(context: Context, payload: String, promise: Promise) {
    if (payload.length > 100_000) {
      promise.reject("BAD_INPUT", "Command payload is too large", null)
      return
    }
    if (context.checkSelfPermission("com.termux.permission.RUN_COMMAND") != PackageManager.PERMISSION_GRANTED) {
      promise.reject("TERMUX_PERMISSION", "Разреши «Run commands in Termux environment» в разрешениях приложения Android.", null)
      return
    }
    val id = nextId.incrementAndGet()
    val result = Intent(context, TermuxResultService::class.java).putExtra("execution_id", id)
    val flags = PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_UPDATE_CURRENT or
      (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
    try {
      val callback = PendingIntent.getService(context, id, result, flags)
      val command = Intent("com.termux.RUN_COMMAND")
      command.setClassName("com.termux", "com.termux.app.RunCommandService")
      command.putExtra("com.termux.RUN_COMMAND_PATH", PYTHON)
      command.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", arrayOf(RUNNER))
      command.putExtra("com.termux.RUN_COMMAND_WORKDIR", HOME)
      command.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true)
      command.putExtra("com.termux.RUN_COMMAND_STDIN", payload)
      command.putExtra("com.termux.RUN_COMMAND_PENDING_INTENT", callback)
      pending[id] = promise
      val component = context.startService(command)
      if (component == null) {
        pending.remove(id)
        callback.cancel()
        promise.reject("TERMUX_MISSING", "Termux не найден. Установи Termux и выполни первоначальную настройку.", null)
      }
    } catch (error: Exception) {
      pending.remove(id)
      promise.reject("TERMUX_LAUNCH", "Не удалось запустить Termux: ${error.javaClass.simpleName}", error)
    }
  }

  fun onResult(id: Int, exitCode: Int, stdout: String, stderr: String, error: String?) {
    val promise = pending.remove(id) ?: return
    if (error != null || exitCode != 0) {
      // stderr may contain CLI diagnostics. Limit it and never pass it to regular chat as a success.
      promise.reject("TERMUX_FAILED", (error ?: stderr).take(750).ifEmpty { "Команда завершилась с кодом $exitCode" }, null)
    } else {
      promise.resolve(stdout.take(90000))
    }
  }
}
