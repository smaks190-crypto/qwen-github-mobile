package expo.modules.termuxbridge

import android.app.Service
import android.content.Intent
import android.os.IBinder

/** Explicit, non-exported callback endpoint for Termux's one-shot PendingIntent. */
class TermuxResultService : Service() {
  override fun onBind(intent: Intent?): IBinder? = null

  override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
    val id = intent?.getIntExtra("execution_id", -1) ?: -1
    val bundle = intent?.getBundleExtra("result")
    if (id >= 0) {
      val exitCode = bundle?.getInt("exitCode", -1) ?: -1
      val stderr = bundle?.getString("stderr") ?: ""
      val stdout = bundle?.getString("stdout") ?: ""
      val error = bundle?.getString("errmsg")
      TermuxCommands.onResult(id, exitCode, stdout, stderr, error)
    }
    stopSelf(startId)
    return START_NOT_STICKY
  }
}
