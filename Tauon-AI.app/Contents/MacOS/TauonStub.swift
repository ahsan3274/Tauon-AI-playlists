import Cocoa

@main
class AppDelegate: NSObject, NSApplicationDelegate {
    var process: Process?
    var keepAlive: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let bundleURL = Bundle.main.bundleURL
        let appRoot = bundleURL.deletingLastPathComponent()
                                  .deletingLastPathComponent()
                                  .deletingLastPathComponent()

        let shell = Process()
        shell.executableURL = URL(fileURLWithPath: "/bin/bash")
        shell.currentDirectoryURL = appRoot
        shell.arguments = ["-c", "./venv/bin/python src/tauon"]

        shell.terminationHandler = { [weak self] proc in
            self?.keepAlive?.invalidate()
            NSApplication.shared.terminate(Int32(proc.terminationStatus))
        }

        do {
            try shell.run()
            self.process = shell
        } catch {
            NSApplication.shared.terminate(1)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return false
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        process?.terminate()
        return .terminateNow
    }
}
