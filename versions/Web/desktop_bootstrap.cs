using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("VideoSubtitleExtraction")]
[assembly: AssemblyProduct("VideoSubtitleExtraction")]
[assembly: AssemblyVersion("1.0.0.0")]

class Program {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    static extern IntPtr CreateJobObject(IntPtr attributes, string name);
    [DllImport("kernel32.dll")]
    static extern bool SetInformationJobObject(IntPtr job, int type, IntPtr info, uint length);
    [DllImport("kernel32.dll")]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr handle);
    [StructLayout(LayoutKind.Sequential)]
    struct BasicLimits {
        public long ProcessTime, JobTime;
        public uint Flags;
        public UIntPtr MinWorkingSet, MaxWorkingSet;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint Priority, Scheduling;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct IoCounters { public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes; }
    [StructLayout(LayoutKind.Sequential)]
    struct ExtendedLimits {
        public BasicLimits Basic;
        public IoCounters Io;
        public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
    }
    static IntPtr CreateLifetimeJob() {
        IntPtr job = CreateJobObject(IntPtr.Zero, null);
        ExtendedLimits limits = new ExtendedLimits();
        limits.Basic.Flags = 0x2000; // Kill only this application's process tree on exit.
        int size = Marshal.SizeOf(limits);
        IntPtr pointer = Marshal.AllocHGlobal(size);
        try {
            Marshal.StructureToPtr(limits, pointer, false);
            if (job == IntPtr.Zero || !SetInformationJobObject(job, 9, pointer, (uint)size)) {
                if (job != IntPtr.Zero) CloseHandle(job);
                throw new Exception("Unable to create the application process group.");
            }
            return job;
        } finally { Marshal.FreeHGlobal(pointer); }
    }
    [STAThread]
    static int Main(string[] args) {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string identity;
        using (SHA256 hash = SHA256.Create()) {
            identity = BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(root.ToUpperInvariant()))).Replace("-", "");
        }
        bool first;
        using (Mutex mutex = new Mutex(true, "Local\\VideoSubtitleExtraction-" + identity, out first)) {
            if (!first) {
                MessageBox.Show("这个文件夹的软件已经运行，请切换到已打开的窗口。", "VideoSubtitleExtraction");
                return 0;
            }
            IntPtr job = IntPtr.Zero;
            try {
                string python = Path.Combine(root, "runtime", "pythonw.exe");
                string script = Path.Combine(root, "desktop_launcher.py");
                if (!File.Exists(python) || !File.Exists(script))
                    throw new Exception("请完整解压软件文件夹后运行 EXE，不要单独移动 EXE 文件。");
                job = CreateLifetimeJob();
                ProcessStartInfo start = new ProcessStartInfo(python);
                start.Arguments = "\"" + script + "\"" + (Array.IndexOf(args, "--self-test") >= 0 ? " --self-test" : "");
                start.WorkingDirectory = root;
                start.UseShellExecute = false;
                start.CreateNoWindow = true;
                using (Process child = Process.Start(start)) {
                    if (!AssignProcessToJobObject(job, child.Handle)) {
                        child.Kill();
                        throw new Exception("无法创建软件进程组，请查看系统权限设置。");
                    }
                    child.WaitForExit();
                    return child.ExitCode;
                }
            } catch (Exception error) {
                MessageBox.Show(error.Message, "VideoSubtitleExtraction", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            } finally {
                if (job != IntPtr.Zero) CloseHandle(job);
                mutex.ReleaseMutex();
            }
        }
    }
}
