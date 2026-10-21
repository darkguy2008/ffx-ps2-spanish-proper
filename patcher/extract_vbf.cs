using System;
using System.IO;
using System.Reflection;

static class ExtractVbf
{
    const string Ps2Folder = "ffx_ps2/";
    const string ProgressFd = "PROGRESS_FD";

    static int Main(string[] args)
    {
        var readerType = Assembly.LoadFrom(args[0]).GetType("VBFTool.VirtuosBigFileReader", true);
        var reader = Activator.CreateInstance(readerType, true);
        readerType.GetMethod("LoadBigFileFile").Invoke(reader, new object[] { args[1] });
        var extract = readerType.GetMethod("ExtractFileContents");
        var files = Array.FindAll((string[])readerType.GetMethod("ReadFileList").Invoke(reader, null), file => file.StartsWith(Ps2Folder));
        var failed = 0;
        using (var progress = new StreamWriter("/dev/fd/" + Environment.GetEnvironmentVariable(ProgressFd)) { AutoFlush = true })
        {
            progress.WriteLine(files.Length);
            foreach (var file in files)
            {
                var outPath = Path.Combine(args[2], file);
                Directory.CreateDirectory(Path.GetDirectoryName(outPath));
                if (!(bool)extract.Invoke(reader, new object[] { file, outPath }))
                {
                    failed++;
                    Console.Error.WriteLine("FAILED " + file);
                }
                progress.WriteLine(file);
            }
        }
        return failed == 0 ? 0 : 1;
    }
}
