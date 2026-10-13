using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;

if (args.Length == 0)
{
    Console.Error.WriteLine("usage: winmdump <file.winmd> [...]");
    return 1;
}

foreach (var path in args)
{
    Console.WriteLine("### " + Path.GetFileName(path));
    try
    {
        using var fs = File.OpenRead(path);
        using var pe = new PEReader(fs);
        var md = pe.GetMetadataReader();
        foreach (var h in md.TypeDefinitions)
        {
            var td = md.GetTypeDefinition(h);
            var name = md.GetString(td.Name);
            var ns = md.GetString(td.Namespace);
            string guid = "";
            foreach (var caH in td.GetCustomAttributes())
            {
                var ca = md.GetCustomAttribute(caH);
                var attrType = "";
                switch (ca.Constructor.Kind)
                {
                    case HandleKind.MemberReference:
                        var mr = md.GetMemberReference((MemberReferenceHandle)ca.Constructor);
                        if (mr.Parent.Kind == HandleKind.TypeReference)
                        {
                            var tr = md.GetTypeReference((TypeReferenceHandle)mr.Parent);
                            attrType = md.GetString(tr.Name);
                        }
                        break;
                    case HandleKind.MethodDefinition:
                        var mdh = md.GetMethodDefinition((MethodDefinitionHandle)ca.Constructor);
                        var declTd = md.GetTypeDefinition(mdh.GetDeclaringType());
                        attrType = md.GetString(declTd.Name);
                        break;
                }
                if (attrType != "GuidAttribute") continue;
                var blob = md.GetBlobBytes(ca.Value);
                if (blob.Length < 20) continue;
                int o = 2; // prolog
                uint a = BitConverter.ToUInt32(blob, o); o += 4;
                ushort b = BitConverter.ToUInt16(blob, o); o += 2;
                ushort c = BitConverter.ToUInt16(blob, o); o += 2;
                guid = string.Format("{0:x8}-{1:x4}-{2:x4}-{3:x2}{4:x2}-{5}",
                    a, b, c, blob[o], blob[o + 1],
                    BitConverter.ToString(blob, o + 2, 6).Replace("-", "").ToLowerInvariant());
            }
            if (guid.Length > 0)
                Console.WriteLine($"{ns}.{name} = {guid}");

            if (name.StartsWith("I") && name.Length > 1 && char.IsUpper(name[1]))
            {
                var methods = new List<string>();
                foreach (var mh in td.GetMethods())
                {
                    var m = md.GetMethodDefinition(mh);
                    methods.Add(md.GetString(m.Name));
                }
                if (methods.Count > 0)
                    Console.WriteLine($"    METHODS {ns}.{name}: {string.Join(", ", methods)}");
            }
        }
    }
    catch (Exception e)
    {
        Console.WriteLine("ERR " + e.Message);
    }
}
return 0;
