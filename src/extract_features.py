import glob
import hashlib
import json
import os
import sys

from androguard.core.apk import APK
from androguard.core.dex import DEX
from lxml import etree

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
FEATURE_NAMES = [
    "resource.entry",
    "source.class.package",
    "manifest.permission",
    "manifest.activity",
    "manifest.action",
    "manifest.category",
    "manifest.feature",
    "source.method.name",
]


def get_manifest_features(a):
    manifest = a.get_android_manifest_xml()

    actions, categories = set(), set()
    for intent_filter in manifest.iter("intent-filter"):
        for el in intent_filter.iter("action"):
            actions.add(el.get(ANDROID_NS + "name"))
        for el in intent_filter.iter("category"):
            categories.add(el.get(ANDROID_NS + "name"))

    return {
        "manifest.permission": sorted(a.get_permissions()),
        "manifest.activity": sorted(a.get_activities()),
        "manifest.action": sorted(actions - {None}),
        "manifest.category": sorted(categories - {None}),
        "manifest.feature": sorted(a.get_features()),
    }


def get_source_features(a):
    packages, methods = set(), set()
    for dex_bytes in a.get_all_dex():
        for cls in DEX(dex_bytes).get_classes():
            class_name = cls.get_name()[1:-1]          # "Lcom/foo/Bar;" -> "com/foo/Bar"
            if "/" in class_name:                      # default-package classes have no package
                packages.add(class_name.rsplit("/", 1)[0].replace("/", "."))
            for method in cls.get_methods():
                methods.add(method.get_name())

    return {
        "source.class.package": sorted(packages),
        "source.method.name": sorted(methods),
    }


def get_resource_features(a):
    entries = set()
    resources = a.get_android_resources()
    if resources is not None:
        for package in resources.get_packages_names():
            public_xml = etree.fromstring(resources.get_public_resources(package))
            for el in public_xml.iter("public"):
                entries.add(f"{el.get('type')}/{el.get('name')}")

    return {"resource.entry": sorted(entries)}


def get_features(apk_path):
    a = APK(apk_path)
    features = {}
    features.update(get_resource_features(a))
    features.update(get_source_features(a))
    features.update(get_manifest_features(a))
    return features, a.get_package()


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()   # AndroZoo lists SHA256 in uppercase


def save_json(data, json_path):
    tmp_path = json_path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, json_path)   # never leave a half-written file behind


def add_apks_to_json(apk_paths, json_path="features.json"):
    data = {}
    if os.path.exists(json_path):
        with open(json_path) as f:
            data = json.load(f)

    try:
        for apk_path in apk_paths:
            sha256 = sha256_of(apk_path)
            if sha256 in data:
                print(f"skip  {apk_path} (already in {json_path})")
                continue
            try:
                features, package = get_features(apk_path)
            except Exception as e:
                print(f"fail  {apk_path}: {e}")
                continue

            data[sha256] = {"package": package, **{name: features[name] for name in FEATURE_NAMES}}
            print(f"done  {apk_path}")
    finally:
        save_json(data, json_path)


if __name__ == "__main__":
    # usage: python extract_features.py [apk files or folders ...]
    targets = sys.argv[1:] or ["."]
    apks = []
    for t in targets:
        if os.path.isdir(t):
            apks += sorted(glob.glob(os.path.join(t, "*.apk")))
        else:
            apks.append(t)
    add_apks_to_json(apks)
