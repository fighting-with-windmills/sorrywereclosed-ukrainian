using Mono.Cecil;
using Mono.Cecil.Cil;

namespace AssemblyPatcher;

/// <summary>
/// Adds Ukrainian (index 6) to Sorry We're Closed's language menu.
///
/// Two tiny IL edits are made in Assembly-CSharp.dll:
///   LanguageSettings.LanguageChange()    -> if (languageSettings.language == 6)
///                                           DialogueManager.SetLanguage("uk");
///   LanguageSettings.GetDefaultLanguage() -> SystemLanguage.Ukrainian => 6
///
/// The original file is saved as Assembly-CSharp.dll.uk_backup.
/// </summary>
internal static class Program
{
    private const string LanguageCode = "uk";
    private const int UkrainianIndex = 6;
    private const int UkrainianSystemLanguageFallback = 38; // UnityEngine.SystemLanguage.Ukrainian

    private static int Main(string[] args)
    {
        string? input = null;
        string? managedDir = null;
        bool inPlace = false;
        bool check = false;
        bool restore = false;
        bool force = false;

        for (int i = 0; i < args.Length; i++)
        {
            switch (args[i])
            {
                case "--input":
                    input = args[++i];
                    break;
                case "--managed-dir":
                    managedDir = args[++i];
                    break;
                case "--in-place":
                    inPlace = true;
                    break;
                case "--check":
                    check = true;
                    break;
                case "--restore":
                    restore = true;
                    break;
                case "--force":
                    force = true;
                    break;
                case "-h":
                case "--help":
                    PrintHelp();
                    return 0;
                default:
                    Console.Error.WriteLine($"Unknown argument: {args[i]}");
                    PrintHelp();
                    return 2;
            }
        }

        string gameRoot = FindGameRoot();
        managedDir ??= Path.Combine(gameRoot, "Sorry We're Closed_Data", "Managed");
        input ??= Path.Combine(managedDir, "Assembly-CSharp.dll");
        input = Path.GetFullPath(input);

        if (!File.Exists(input))
        {
            Console.Error.WriteLine($"Assembly not found: {input}");
            Console.Error.WriteLine("Run this from the game folder or pass --input <path>.");
            return 2;
        }

        string backup = input + ".uk_backup";
        var resolver = CreateResolver(Path.GetDirectoryName(input)!, managedDir);

        if (restore)
        {
            if (!File.Exists(backup))
            {
                Console.Error.WriteLine($"No backup at {backup}");
                return 2;
            }
            File.Copy(backup, input, overwrite: true);
            Console.WriteLine($"Restored {input} from the backup.");
            return 0;
        }

        if (check)
        {
            return Check(input, resolver);
        }

        if (!inPlace)
        {
            Console.Error.WriteLine(
                "Nothing to do. Pass --in-place to patch, --check to verify or --restore to revert.");
            return 2;
        }

        var module = ModuleDefinition.ReadModule(input, ReaderParameters(resolver));
        var languageChange = FindMethod(module, "LanguageChange");
        if (languageChange is null)
        {
            module.Dispose();
            Console.Error.WriteLine("LanguageSettings.LanguageChange not found - wrong assembly?");
            return 2;
        }

        if (IsPatched(languageChange))
        {
            if (!force)
            {
                module.Dispose();
                Console.WriteLine("Assembly is already patched (use --force to redo it).");
                return 0;
            }
            module.Dispose();
            if (!File.Exists(backup))
            {
                Console.Error.WriteLine(
                    "Already patched but no .uk_backup exists; cannot rebuild. " +
                    "Use Steam 'verify integrity' or restore the original file.");
                return 2;
            }
            File.Copy(backup, input, overwrite: true);
            module = ModuleDefinition.ReadModule(input, ReaderParameters(resolver));
        }

        if (!File.Exists(backup))
        {
            File.Copy(input, backup);
            Console.WriteLine($"Backup: {backup}");
        }

        Patch(module, resolver);
        return 0;
    }

    private static void PrintHelp()
    {
        Console.WriteLine("""
            AssemblyPatcher - adds Ukrainian to Sorry We're Closed

              dotnet run --project tools\AssemblyPatcher -- --in-place
              dotnet run --project tools\AssemblyPatcher -- --check
              dotnet run --project tools\AssemblyPatcher -- --restore

            Options:
              --input <path>        Assembly-CSharp.dll to patch
              --managed-dir <path>  Folder containing the managed assemblies
              --force               Re-patch from the backup even if already patched
            """);
    }

    private static ReaderParameters ReaderParameters(IAssemblyResolver resolver) => new()
    {
        AssemblyResolver = resolver,
        ReadWrite = false,
        ReadingMode = ReadingMode.Deferred,
        InMemory = true,
    };

    private static DefaultAssemblyResolver CreateResolver(params string[] directories)
    {
        var resolver = new DefaultAssemblyResolver();
        foreach (var directory in directories.Where(Directory.Exists))
        {
            resolver.AddSearchDirectory(directory);
        }
        return resolver;
    }

    /// <summary>
    /// Locate the game folder even when dotnet run uses another working directory:
    /// walk up from the shell cwd and from the built binary until the game exe or
    /// the _Data folder shows up.
    /// </summary>
    private static string FindGameRoot()
    {
        foreach (var start in new[] { Directory.GetCurrentDirectory(), AppContext.BaseDirectory })
        {
            var directory = new DirectoryInfo(start);
            while (directory is not null)
            {
                if (File.Exists(Path.Combine(directory.FullName, "Sorry We're Closed.exe")) ||
                    Directory.Exists(Path.Combine(directory.FullName, "Sorry We're Closed_Data")))
                {
                    return directory.FullName;
                }
                directory = directory.Parent;
            }
        }
        return Directory.GetCurrentDirectory();
    }

    private static MethodDefinition? FindMethod(ModuleDefinition module, string name)
    {
        var type = module.GetType("LanguageSettings");
        return type?.Methods.FirstOrDefault(m => m.Name == name);
    }

    private static bool IsPatched(MethodDefinition method)
    {
        return method.Body.Instructions.Any(i =>
            i.OpCode == OpCodes.Ldstr &&
            string.Equals(i.Operand as string, LanguageCode, StringComparison.Ordinal));
    }

    private static int Check(string input, IAssemblyResolver resolver)
    {
        using var module = ModuleDefinition.ReadModule(input, ReaderParameters(resolver));
        var languageChange = FindMethod(module, "LanguageChange");
        var getDefault = FindMethod(module, "GetDefaultLanguage");
        bool languageOk = languageChange is not null && IsPatched(languageChange);
        bool defaultOk = getDefault is not null && getDefault.Body.Instructions.Any(i =>
            i.OpCode == OpCodes.Ldc_I4 && i.Operand is int value && value == UkrainianIndex);

        Console.WriteLine($"LanguageChange index 6 -> \"uk\" : {(languageOk ? "ok" : "MISSING")}");
        Console.WriteLine($"GetDefaultLanguage Ukrainian   : {(defaultOk ? "ok" : "MISSING")}");
        Console.WriteLine(languageOk && defaultOk
            ? "Assembly check: OK"
            : "Assembly check: NOT PATCHED");
        return languageOk && defaultOk ? 0 : 1;
    }

    private static void Patch(ModuleDefinition module, IAssemblyResolver resolver)
    {
        var type = module.GetType("LanguageSettings")
                   ?? throw new InvalidOperationException("LanguageSettings not found");
        var languageSettingsField = type.Fields.FirstOrDefault(f => f.Name == "languageSettings")
                                    ?? throw new InvalidOperationException("languageSettings field not found");
        var languageData = module.GetType("SettingsData/LanguageSettingsData")
                           ?? throw new InvalidOperationException("SettingsData/LanguageSettingsData not found");
        var languageField = languageData.Fields.FirstOrDefault(f => f.Name == "language")
                            ?? throw new InvalidOperationException("language field not found");

        PatchLanguageChange(type, languageSettingsField, languageField);
        PatchDefaultLanguage(type, module, resolver);

        string target = module.FileName;
        string temporary = target + ".uk_tmp";
        module.Write(temporary);
        module.Dispose();
        File.Copy(temporary, target, overwrite: true);
        File.Delete(temporary);
        Console.WriteLine("Assembly patched.");
    }

    private static void PatchLanguageChange(TypeDefinition type, FieldReference languageSettingsField,
        FieldReference languageField)
    {
        var method = type.Methods.First(m => m.Name == "LanguageChange");
        var body = method.Body;
        var il = body.GetILProcessor();

        if (IsPatched(method))
        {
            Console.WriteLine("  LanguageChange already contains the uk branch - skipped.");
            return;
        }

        var setLanguage = body.Instructions
            .Where(i => i.OpCode == OpCodes.Call || i.OpCode == OpCodes.Callvirt)
            .Select(i => i.Operand as MethodReference)
            .FirstOrDefault(m => m is not null && m.Name == "SetLanguage" &&
                                 m.DeclaringType.Name == "DialogueManager")
            ?? throw new InvalidOperationException("DialogueManager.SetLanguage call not found");

        // LanguageChange starts with
        //     languageSettings.language = languageDropDown.value;
        //     switch (languageSettings.language) { ... }
        // Insert the uk check right after the store, where the evaluation stack
        // is empty.  That keeps the switch (and its value) untouched, so no
        // branch retargeting is needed and the check runs for every index.
        var store = body.Instructions.FirstOrDefault(i =>
            i.OpCode == OpCodes.Stfld &&
            i.Operand is FieldReference field &&
            field.Name == "language" &&
            field.DeclaringType.Name.Contains("LanguageSettingsData"))
            ?? throw new InvalidOperationException(
                "could not find the languageSettings.language assignment");

        var insertBefore = store.Next
            ?? throw new InvalidOperationException("unexpected end of LanguageChange");

        var block = new[]
        {
            il.Create(OpCodes.Ldarg_0),
            il.Create(OpCodes.Ldfld, languageSettingsField),
            il.Create(OpCodes.Ldfld, languageField),
            il.Create(OpCodes.Ldc_I4, UkrainianIndex),
            il.Create(OpCodes.Bne_Un, insertBefore),
            il.Create(OpCodes.Ldstr, LanguageCode),
            il.Create(OpCodes.Call, setLanguage),
        };

        foreach (var instruction in block)
        {
            il.InsertBefore(insertBefore, instruction);
        }

        body.MaxStackSize = Math.Max(body.MaxStackSize, 8);
    }

    private static void PatchDefaultLanguage(TypeDefinition type, ModuleDefinition module,
        IAssemblyResolver resolver)
    {
        var method = type.Methods.First(m => m.Name == "GetDefaultLanguage");
        var body = method.Body;
        var il = body.GetILProcessor();

        if (body.Instructions.Any(i =>
                i.OpCode == OpCodes.Ldc_I4 && i.Operand is int value && value == UkrainianIndex))
        {
            Console.WriteLine("  GetDefaultLanguage already handles Ukrainian - skipped.");
            return;
        }

        var systemLanguageCall = body.Instructions.FirstOrDefault(i =>
            (i.OpCode == OpCodes.Call || i.OpCode == OpCodes.Callvirt) &&
            i.Operand is MethodReference methodRef &&
            methodRef.Name == "get_systemLanguage")
            ?? throw new InvalidOperationException("Application.get_systemLanguage not found");

        int ukrainianValue = ResolveUkrainianEnumValue(module, resolver);
        var first = body.Instructions[0];

        var block = new[]
        {
            il.Create(OpCodes.Call, (MethodReference)systemLanguageCall.Operand),
            il.Create(OpCodes.Ldc_I4, ukrainianValue),
            il.Create(OpCodes.Bne_Un, first),
            il.Create(OpCodes.Ldc_I4, UkrainianIndex),
            il.Create(OpCodes.Ret),
        };

        foreach (var instruction in block)
        {
            il.InsertBefore(first, instruction);
        }

        body.MaxStackSize = Math.Max(body.MaxStackSize, 8);
    }

    private static int ResolveUkrainianEnumValue(ModuleDefinition module, IAssemblyResolver resolver)
    {
        try
        {
            var reference = module.AssemblyReferences.FirstOrDefault(r => r.Name == "UnityEngine.CoreModule");
            if (reference is null)
            {
                return UkrainianSystemLanguageFallback;
            }
            var assembly = resolver.Resolve(reference);
            var enumType = assembly.MainModule.GetType("UnityEngine.SystemLanguage");
            var field = enumType?.Fields.FirstOrDefault(f => f.Name == "Ukrainian");
            if (field is { HasConstant: true })
            {
                return Convert.ToInt32(field.Constant);
            }
        }
        catch
        {
            // fall through to the known constant
        }
        return UkrainianSystemLanguageFallback;
    }
}
