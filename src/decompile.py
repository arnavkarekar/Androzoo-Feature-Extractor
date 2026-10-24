from androguard.misc import AnalyzeAPK
import os

apk_path = "/path/to/app.apk"
out_dir = os.path.splitext(os.path.basename(apk_path))[0] + "_decompiled"

a, dex_list, dx = AnalyzeAPK(apk_path)      # unzip + parse manifest + parse all DEX files

os.makedirs(out_dir, exist_ok=True)
with open(os.path.join(out_dir, "AndroidManifest.xml"), "wb") as f:
    f.write(a.get_android_manifest_axml().get_xml())   # binary AXML → readable XML

for dex in dex_list:
    for cls in dex.get_classes():
        path = os.path.join(out_dir, "src", cls.get_name()[1:-1] + ".java")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            source = cls.get_source()   # DEX → Java directly
        except Exception:
            continue
        with open(path, "w") as f:
            f.write(source)
